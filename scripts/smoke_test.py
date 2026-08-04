"""Headless golden path — proves the engine before any browser opens.
Fake-LLM scripted turns exercise: the Investigation Loop's tool-calling
mechanics, chat-vs-generate, gates as chat commands, ADR-11 bundled
versions, the QA handoff lockout, checker verdicts, pass and waiver."""
import base64, io, json, os, sys, tempfile

TMP = tempfile.mkdtemp(prefix="dm_smoke_")
os.environ.update({
    "DM_FAKE_LLM": "1", "DM_TRACING": "0",
    "DM_LOCAL_FS_ROOT": f"{TMP}/ws",
    "DM_DATABASE_URL": f"duckdb:///{TMP}/state.duckdb",
    "DM_DEV_USER": "maker@local.dev",
    "DM_MAKER_EMAILS": "maker@local.dev",
})
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import state
from modeler.agent_tools import LLM
from ui.backend import LocalBackend, UiError
from scripts.make_synthetic_idra import build as build_idra

def expect_error(kind, fn, *a, **k):
    try:
        fn(*a, **k)
    except UiError as e:
        assert e.kind == kind, f"wanted {kind}, got {e.kind}: {e}"
        return str(e)
    raise AssertionError(f"expected UiError({kind})")

STAGE1_MD = ("# Conceptual model\nEntities: customer, account, transaction.\n"
             "customer: One row per customer. account: One row per account. "
             "transaction: One row per posted transaction.")
SPEC = {"grain": {"dim_customer": "One row per customer",
                  "fct_transaction": "One row per posted transaction"},
        "tables": [
          {"name": "dim_customer", "columns": [
             {"name": "cust_id", "type": "STRING", "nullable": False,
              "pk": True, "privacy": "INTERNAL", "source_field": "CUST_ID"},
             {"name": "cust_full_name", "type": "STRING", "nullable": True,
              "privacy": "CONFIDENTIAL", "source_field": "CUST_FULL_NAME"},
             {"name": "cust_segment_cd", "type": "STRING", "nullable": True,
              "privacy": "INTERNAL", "source_field": "CUST_SEGMENT_CD"}]},
          {"name": "fct_transaction", "columns": [
             {"name": "txn_id", "type": "STRING", "nullable": False,
              "pk": True, "privacy": "INTERNAL", "source_field": "TXN_ID"},
             {"name": "acct_id", "type": "STRING", "nullable": False,
              "privacy": "INTERNAL", "source_field": "TXN_ACCT_ID"},
             {"name": "txn_amt", "type": "DECIMAL(18,2)", "nullable": False,
              "privacy": "INTERNAL", "source_field": "TXN_AMT"}]}]}
STAGE2_MD = ("# Physical model\nOne row per customer for dim_customer; "
             "One row per posted transaction for fct_transaction.\n"
             "```json MODEL_SPEC\n" + json.dumps(SPEC) + "\n```")

def main():
    state.init_db()
    b = LocalBackend("maker@local.dev")

    # tenant is mandatory
    expect_error("conflict", b.create_project, {"name": "NoTenant"})
    p = b.create_project({"name": "Synthetic Card Vault", "tenant": "demo-team",
                          "data_product": "retail_core", "dp_type": "SADP",
                          "target_catalog": "workspace",
                          "schema_naming": "dm_demo",
                          "primary_input_type": "IDRA"})
    pid = p["project_id"]
    b.register_source(pid, {"source_id": "RCB", "modelling_profile": "B"})
    b.register_source(pid, {"source_id": "RCB2", "modelling_profile": "B"})

    # upload the synthetic IDRA through the seam (base64 path)
    buf = f"{TMP}/idra.xlsx"; build_idra(buf)
    b.upload_b64("input/idra", "RCB_IDRA.xlsx",
                 base64.b64encode(open(buf, "rb").read()).decode())

    # blocked before gates — verbatim message names the gate
    msg = expect_error("blocked", b.send, "RCB", "stage2_physical_model",
                       "go", False)
    assert "CONFIRM_STAGE1_FINAL" in msg

    # loop mechanics: scripted tool-calls then a final answer
    scripted = LLM(scripted=[
        {"tool_calls": [{"id": "t1", "name": "list_files",
                         "arguments": "{}"}]},
        {"tool_calls": [{"id": "t2", "name": "read_sheet",
                         "arguments": json.dumps(
                             {"path": "input/idra/RCB_IDRA.xlsx",
                              "max_rows": 5})}]},
        {"content": "Plan drafted after inspecting the IDRA. "
                    "Profile B recommended for RCB."},
    ])
    r = b.send(None, "stage0_data_product_planning",
               "plan the product", False, llm=scripted)
    assert r["kind"] == "run" and "Profile B" in r["assistant"]
    logs = [f for f in b.tree() if "agent-log" in f["path"]]
    assert logs, "investigation log missing — tool loop did not record"

    # gates as chat commands (project-level then per-source)
    assert b.send("RCB", "stage0_data_product_planning",
                  "CONFIRM_DATA_PRODUCT_PLAN", False)["kind"] == "gate"
    b.send("RCB", "parse_idra", "CONFIRM_INPUT_PARSED", False)

    # discuss twice: thread grows, zero deliverables
    before = len(state.list_deliverables(pid))
    for q in ("what grain should transactions use?",
              "any concerns with segment codes?"):
        b.send("RCB", "stage1_conceptual_erd", q, True,
               llm=LLM(scripted=[{"content": "Discussed: " + q}]))
    t = b.thread("RCB", "stage1")
    assert len(t) == 4, f"thread rows {len(t)}"
    assert len(state.list_deliverables(pid)) == before, "chat made artifacts!"

    # generate stage 1, confirm; generate stage 2 (good spec), confirm
    b.send("RCB", "stage1_conceptual_erd", "produce it", False,
           llm=LLM(scripted=[{"content": STAGE1_MD}]))
    b.send("RCB", "stage1_conceptual_erd", "CONFIRM_STAGE1_FINAL", False)
    b.send("RCB", "stage2_physical_model", "produce it", False,
           llm=LLM(scripted=[{"content": STAGE2_MD}]))
    dels = [d for d in state.list_deliverables(pid, "RCB")
            if d["stage"] == "stage2"]
    kinds = {d["artifact_type"] for d in dels}
    assert {"response_md", "ddl", "yaml", "stm_xlsx", "erd_html",
            "lddm_md", "construction_notebook"} <= kinds, kinds
    assert {d["version"] for d in dels} == {1}, "ADR-11 bundling broken"
    b.send("RCB", "stage2_physical_model", "CONFIRM_STAGE2_FINAL", False)
    assert state.source(pid, "RCB")["qa_status"] == "REQUIRED"

    # QA handoff lockout — verbatim
    msg = expect_error("blocked", b.send, "RCB", "stm_walkthrough_pack",
                       "walk", False)
    assert "QA pending" in msg
    # checker gate on good artifacts -> recommend, then pass
    r = b.qa_run("GATE", "RCB", None)
    assert r["verdict"] == "RECOMMEND_SIGN_OFF", r
    b.qa_pass("RCB")
    assert state.source(pid, "RCB")["qa_status"] == "PASSED"
    b.send("RCB", "stm_walkthrough_pack", "walk", False,
           llm=LLM(scripted=[{"content": "Walkthrough narrative."}]))

    # second source: bad stage-2 (no MODEL_SPEC) -> blocked -> owner waiver
    b.send("RCB2", "parse_idra", "CONFIRM_INPUT_PARSED", False)
    b.send("RCB2", "stage1_conceptual_erd", "CONFIRM_STAGE1_FINAL", False)
    b.send("RCB2", "stage2_physical_model", "produce it", False,
           llm=LLM(scripted=[{"content": "One row per thing. (spec omitted)"}]))
    b.send("RCB2", "stage2_physical_model", "CONFIRM_STAGE2_FINAL", False)
    r = b.qa_run("GATE", "RCB2", None)
    assert r["verdict"] == "BLOCKED" and r["blocking"] >= 1, r
    expect_error("conflict", b.qa_pass, "RCB2")
    expect_error("conflict", b.qa_waive, "RCB2", "no")     # short reason
    b.qa_waive("RCB2", "demo waiver: synthetic cycle, defects acknowledged")
    assert state.source(pid, "RCB2")["qa_status"] == "WAIVED"

    # one-active-run guard
    rid = state.claim_run(pid, "manual_hold", "maker@local.dev", "RCB")
    m = expect_error("conflict", b.send, "RCB", "unknowns_triage", "x", True)
    assert "one active run" in m
    state.finish_run(rid, "SUCCEEDED")

    print("SMOKE TEST PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
