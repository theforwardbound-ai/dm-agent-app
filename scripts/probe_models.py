"""Probe serving endpoints for Investigation-Loop fitness.

The loop in modeler/runner.py needs three things from a model:
  1. emit a tool_call when tools are offered
  2. accept a `tool` role message back and keep going
  3. eventually stop calling tools and produce prose

A model that fails 1 or 2 cannot drive the loop at all, so run this before
pointing DM_MODEL_FRONTIER / DM_MODEL_STANDARD at anything new.

    python scripts/probe_models.py [endpoint ...]

With no arguments it probes the endpoints this workspace serves. Requires
Databricks auth (a CLI profile locally, app SP identity on platform).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databricks.sdk import WorkspaceClient
from modeler.agent_tools import TOOL_SCHEMAS

DEFAULT_MODELS = [
    "databricks-llama-4-maverick",
    "databricks-gpt-oss-120b",
    "databricks-gpt-oss-20b",
    "databricks-qwen3-next-80b-a3b-instruct",
    "databricks-qwen35-122b-a10b",
    "databricks-meta-llama-3-3-70b-instruct",
]

SYSTEM = ("You are a data modeling agent. You investigate the project "
          "workspace using tools before answering. Never guess at file "
          "contents — read them.")
USER = ("Before you answer: what source files exist under the project's "
        "input/ folder, and what is in the first one? Use your tools.")
STUB_RESULT = ("input/customer_idra.xlsx  (48213 B)\n"
               "input/account_idra.xlsx  (31002 B)")


def probe(client, model: str) -> dict:
    out = {}
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER}]

    try:
        r = client.chat.completions.create(
            model=model, messages=msgs, tools=TOOL_SCHEMAS, max_tokens=1024)
    except Exception as e:
        return {"turn1": f"ERROR {type(e).__name__}: {str(e)[:180]}"}

    m = r.choices[0].message
    calls = getattr(m, "tool_calls", None)
    if not calls:
        return {"turn1": "NO TOOL CALL (returned prose)",
                "sample": (m.content or "")[:120]}

    first = calls[0]
    try:
        args = json.dumps(json.loads(first.function.arguments or "{}"))
        argfmt = "parseable"
    except Exception:
        args, argfmt = str(first.function.arguments)[:80], "UNPARSEABLE JSON"
    out["turn1"] = f"{first.function.name}({args[:80]}) args={argfmt}"
    out["n_calls_turn1"] = len(calls)

    msgs.append({"role": "assistant", "content": m.content or "",
                 "tool_calls": [{"id": t.id, "type": "function",
                                 "function": {"name": t.function.name,
                                              "arguments": t.function.arguments}}
                                for t in calls]})
    for t in calls:
        msgs.append({"role": "tool", "tool_call_id": t.id,
                     "content": STUB_RESULT})

    try:
        r2 = client.chat.completions.create(
            model=model, messages=msgs, tools=TOOL_SCHEMAS, max_tokens=1024)
    except Exception as e:
        out["turn2"] = f"ERROR {type(e).__name__}: {str(e)[:180]}"
        return out

    m2 = r2.choices[0].message
    calls2 = getattr(m2, "tool_calls", None)
    if calls2:
        out["turn2"] = f"continued -> {calls2[0].function.name}(...)"
    else:
        out["turn2"] = "concluded with prose"
        out["sample"] = (m2.content or "")[:120]
    u = getattr(r2, "usage", None)
    out["tokens"] = (f"in={getattr(u, 'prompt_tokens', 0)} "
                     f"out={getattr(u, 'completion_tokens', 0)}")
    return out


def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    client = WorkspaceClient().serving_endpoints.get_open_ai_client()
    fit = []
    for model in models:
        res = probe(client, model)
        print(f"\n=== {model} ===")
        for k, v in res.items():
            print(f"  {k:14} {v}")
        if "continued" in res.get("turn2", "") or \
           "concluded" in res.get("turn2", ""):
            fit.append(model)
    print(f"\nloop-capable: {', '.join(fit) if fit else '(none)'}")


if __name__ == "__main__":
    main()
