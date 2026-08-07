"""Drive the Northbeam Bank Lending data product through the agent.

Talks to a running dm-agent over HTTP exactly as the browser does, so the run
is watchable in the UI while this script narrates it. Sequence:

    stage0 plan -> CONFIRM_DATA_PRODUCT_PLAN -> CONFIRM_INPUT_PARSED
    -> stage1 conceptual ERD -> CONFIRM_STAGE1_FINAL
    -> stage2 physical model (+ all six generators)

    python scripts/run_lending_model.py [base_url]
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.bank_sources import SYSTEMS, build_idra, BANK_NAME  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
USER = os.environ.get("DM_DEV_USER", "maker@local.dev")
IDRA_DIR = os.environ.get("DM_IDRA_DIR", "./.local/idra")
PRIMARY = "LND"
SHARED = "CMD"


def call(method, path, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json",
                 "X-Forwarded-Email": USER})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def render(ev):
    try:
        p = json.loads(ev["payload"]) if ev["payload"] else {}
    except (json.JSONDecodeError, TypeError):
        p = {"raw": ev["payload"]}
    k, n = ev["kind"], ev["name"] or ""
    if k == "iteration":
        return f"    ── iteration {p.get('iteration')}/{p.get('max')}"
    if k == "tool_call":
        return f"    → {n}({json.dumps(p.get('args', {}))[:100]})"
    if k == "tool_result":
        return (f"    ← {n} [{'ok' if p.get('ok') else 'ERR'}, "
                f"{p.get('chars', 0)} chars]")
    if k == "assistant":
        return f"    💬 {n}: {str(p.get('preview', ''))[:100]!r}"
    if k == "artifact":
        return f"    📦 {n}: {os.path.basename(str(p.get('path') or ''))}" \
               + (f"  SKIPPED: {p['skipped']}" if p.get("skipped") else "")
    if k == "status":
        return f"    ▸ {n}"
    if k == "budget":
        return f"    ⚠ {n}"
    return None


def gate(source, task, name):
    code, r = call("POST", "/api/send",
                   {"source": source, "task": task, "message": name})
    assert code == 200 and r.get("kind") == "gate", f"gate {name}: {code} {r}"
    print(f"  gate {name} — {r['effect']}")


def run(source, task, message, budget_s=1200):
    code, r = call("POST", "/api/send",
                   {"source": source, "task": task, "message": message})
    assert code == 202, f"{task}: expected 202, got {code} {r}"
    rid = r["run_id"]
    print(f"  run {task} ({rid[:8]})")
    since, done, deadline = 0, False, time.time() + budget_s
    while not done and time.time() < deadline:
        c, page = call("GET", f"/api/run/events?id={rid}&since={since}")
        if c != 200:
            print(f"    [events {c}] {page}")
            break
        for ev in page["events"]:
            line = render(ev)
            if line:
                print(line)
        since, done = page["cursor"], page["done"]
        if not done:
            time.sleep(1.5)
    _, run_row = call("GET", f"/api/run?id={rid}")
    print(f"    status={run_row['status']} "
          f"tokens={run_row['tokens_in']}+{run_row['tokens_out']}")
    if run_row.get("error"):
        print(f"    error: {run_row['error']}")
    assert run_row["status"] == "SUCCEEDED", f"{task} ended {run_row['status']}"
    return json.loads(run_row["output_paths"] or "[]")


def main():
    code, health = call("GET", "/healthz")
    assert code == 200 and health.get("ok"), f"server not healthy: {health}"
    print(f"{BANK_NAME} — Lending data product\nagent: {BASE}\n")

    os.makedirs(IDRA_DIR, exist_ok=True)
    for c in SYSTEMS:
        build_idra(c, os.path.join(IDRA_DIR, f"{c}_IDRA.xlsx"))
    print(f"IDRAs written for {', '.join(SYSTEMS)}\n")

    code, proj = call("POST", "/api/project", {
        "name": "Northbeam Lending Data Product",
        "tenant": "lending-analytics",
        "data_product": "lending_core",
        "dp_type": "SADP",
        "target_catalog": "workspace",
        "schema_naming": "dm_lending",
        "primary_input_type": "IDRA"})
    assert code == 200, (code, proj)
    pid = proj["project_id"]
    print(f"project {pid[:8]} — lending_core -> workspace.dm_lending")

    call("POST", "/api/source", {"project_id": pid, "source_id": PRIMARY,
                                 "modelling_profile": "B"})
    call("POST", "/api/source", {"project_id": pid, "source_id": SHARED,
                                 "modelling_profile": "B",
                                 "is_shared_dimension": True})
    print(f"sources: {PRIMARY} (primary), {SHARED} (shared dimension)\n")

    for c in SYSTEMS:
        with open(os.path.join(IDRA_DIR, f"{c}_IDRA.xlsx"), "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        call("POST", "/api/upload", {"folder": "input/idra",
                                     "filename": f"{c}_IDRA.xlsx", "b64": b64})
    print(f"uploaded {len(SYSTEMS)} IDRAs to input/idra/\n")

    print("STAGE 0 — data product planning")
    run(None, "stage0_data_product_planning",
        "Plan the Lending data product. The primary source is LND (the "
        "lending system); CMD is the customer MDM shared dimension. Read the "
        "IDRAs in input/idra before planning.")
    gate(None, "stage0_data_product_planning", "CONFIRM_DATA_PRODUCT_PLAN")
    gate(PRIMARY, "parse_idra", "CONFIRM_INPUT_PARSED")

    print("\nSTAGE 1 — conceptual ERD")
    run(PRIMARY, "stage1_conceptual_erd",
        "Produce the conceptual ERD for the Lending data product. Read "
        "input/idra/LND_IDRA.xlsx and input/idra/CMD_IDRA.xlsx. Use the "
        "Entity Hint column to separate entities, state the grain of each, "
        "and identify the relationships between them.")
    gate(PRIMARY, "stage1_conceptual_erd", "CONFIRM_STAGE1_FINAL")

    print("\nSTAGE 2 — physical model")
    outs = run(PRIMARY, "stage2_physical_model",
               "Produce the physical model for the Lending data product "
               "targeting workspace.dm_lending. Read the LND and CMD IDRAs "
               "for exact field names, types and PII flags. End with the "
               "MODEL_SPEC json block covering every table.")

    print("\nARTIFACTS")
    skipped = [p for p in outs if p.startswith("[skipped")]
    for p in outs:
        print(f"  {os.path.basename(p) if not p.startswith('[') else p}")
    print(f"\n{len(outs) - len(skipped)} artifact(s) written, "
          f"{len(skipped)} skipped")
    if skipped:
        print("MODEL_SPEC likely missing or malformed — generators skipped:")
        for s in skipped:
            print(f"  {s}")
        return 1
    print("\nLENDING MODEL COMPLETE ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
