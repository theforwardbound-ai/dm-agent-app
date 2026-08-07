"""Async-run proof — the Copilot-shaped behaviour, over HTTP, for real.

Boots the actual server, drives it only through its JSON routes, and runs
stage1_conceptual_erd against a LIVE serving endpoint. What it proves:

  * POST /api/send returns 202 immediately instead of blocking for the loop
  * the run keeps going after the request is done
  * GET /api/run/events tails tool calls and results AS THEY HAPPEN
  * the run reaches a terminal state and drops its resume checkpoint
  * artifacts land in the project workspace

Run:  python scripts/smoke_async.py            (live model)
      DM_FAKE_LLM=1 python scripts/smoke_async.py   (plumbing only)
"""
import base64
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

TMP = tempfile.mkdtemp(prefix="dm_async_")
PORT = int(os.environ.get("DM_SMOKE_PORT", "8765"))
os.environ.setdefault("DM_FAKE_LLM", "0")      # live endpoint by default
os.environ.update({
    "DM_TRACING": os.environ.get("DM_TRACING", "0"),
    "DM_LOCAL_FS_ROOT": f"{TMP}/ws",
    "DM_DATABASE_URL": f"duckdb:///{TMP}/state.duckdb",
    "DM_DEV_USER": "maker@local.dev",
    "DM_MAKER_EMAILS": "maker@local.dev",
    "DM_SERVER_PORT": str(PORT),
})
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import ThreadingHTTPServer            # noqa: E402
from core import config, state, worker                 # noqa: E402
from ui.server import H                                # noqa: E402
from scripts.make_synthetic_idra import build as build_idra   # noqa: E402

BASE = f"http://127.0.0.1:{PORT}"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "X-Forwarded-Email": "maker@local.dev"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def render(ev):
    kind, name = ev["kind"], ev["name"] or ""
    try:
        p = json.loads(ev["payload"]) if ev["payload"] else {}
    except (json.JSONDecodeError, TypeError):
        p = {"raw": ev["payload"]}
    if kind == "iteration":
        return f"  ── iteration {p.get('iteration')}/{p.get('max')}"
    if kind == "tool_call":
        return f"  → {name}({json.dumps(p.get('args', {}))[:90]})"
    if kind == "tool_result":
        flag = "ok" if p.get("ok") else "ERR"
        return (f"  ← {name} [{flag}, {p.get('chars', 0)} chars] "
                f"{str(p.get('preview', ''))[:90]!r}")
    if kind == "assistant":
        return f"  💬 {name}: {str(p.get('preview', ''))[:120]!r}"
    if kind == "artifact":
        return f"  📦 {name}: {p.get('path') or p.get('skipped')}"
    if kind == "status":
        return f"  ▸ {name}: {str(p)[:120]}"
    if kind == "budget":
        return f"  ⚠ {name}: {p}"
    return f"  · {kind}/{name}"


def main():
    state.init_db()
    worker.start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"server up on {BASE}  fake_llm={config.FAKE_LLM}  "
          f"model={config.MODEL_FRONTIER}")

    code, proj = call("POST", "/api/project",
                      {"name": "Async Proof", "tenant": "demo-team",
                       "data_product": "retail_core", "dp_type": "SADP",
                       "target_catalog": "workspace",
                       "schema_naming": "dm_demo",
                       "primary_input_type": "IDRA"})
    assert code == 200, (code, proj)
    pid = proj["project_id"]
    call("POST", "/api/source", {"project_id": pid, "source_id": "RCB",
                                 "modelling_profile": "B"})

    idra = f"{TMP}/idra.xlsx"
    build_idra(idra)
    call("POST", "/api/upload",
         {"folder": "input/idra", "filename": "RCB_IDRA.xlsx",
          "b64": base64.b64encode(open(idra, "rb").read()).decode()})

    code, r = call("POST", "/api/send",
                   {"source": "RCB", "task": "parse_idra",
                    "message": "CONFIRM_INPUT_PARSED"})
    assert code == 200 and r.get("kind") == "gate", (code, r)
    print(f"gate recorded: {r['gate']}")

    # ---- the actual claim: this returns at once, the run keeps going ----
    t0 = time.time()
    code, r = call("POST", "/api/send",
                   {"source": "RCB", "task": "stage1_conceptual_erd",
                    "message": "Produce the conceptual ERD from the IDRA."})
    dt = time.time() - t0
    assert code == 202, f"expected 202 accepted, got {code}: {r}"
    rid = r["run_id"]
    print(f"\nPOST /api/send returned {code} in {dt:.2f}s  "
          f"run={rid[:8]} status={r['status']}")
    assert dt < 5, f"request blocked for {dt:.1f}s — not detached"

    print("\n--- tailing /api/run/events ---")
    since, done, deadline = 0, False, time.time() + 900
    while not done and time.time() < deadline:
        code, page = call("GET", f"/api/run/events?id={rid}&since={since}")
        if code != 200:
            print(f"[events {code}] {page}")
            break
        for ev in page["events"]:
            print(render(ev))
        since = page["cursor"]
        done = page["done"]
        if not done:
            time.sleep(1.0)

    code, run = call("GET", f"/api/run?id={rid}")
    print(f"\nfinal: status={run['status']} tokens_in={run['tokens_in']} "
          f"tokens_out={run['tokens_out']} elapsed={time.time()-t0:.1f}s")
    if run.get("error"):
        print(f"error: {run['error']}")

    assert state.load_checkpoint(rid) is None, \
        "checkpoint should be cleared on a terminal run"

    outs = json.loads(run["output_paths"] or "[]")
    print(f"outputs ({len(outs)}):")
    for p in outs:
        print(f"  {p}")

    assert run["status"] == "SUCCEEDED", f"run ended {run['status']}"
    assert outs, "no artifacts written"
    print("\nASYNC PROOF PASSED ✅")


if __name__ == "__main__":
    main()
