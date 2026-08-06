"""Independent checker. Protocol: RUN_QA_GATE (blocks on CRITICAL/HIGH),
RUN_QA_AUDIT (report only), single-artifact; CONFIRM_QA_PASS closes;
owner waiver with recorded reason. Reads inputs + stage-2 only; writes
qa/ + defects only; never touches modeler prompts."""
import datetime as dt, re
from core import state
from core.workspace import ProjectWorkspace
from checker import checks

BLOCKING = {"CRITICAL", "HIGH"}

def _latest_stage2(ws, source_id) -> tuple[int, dict[str, bytes]]:
    files = ws.listdir(f"output/stage2/{source_id}")
    vs = set()
    for f in files:
        for part in f["path"].split("/"):
            if re.fullmatch(r"v\d+", part):
                vs.add(int(part[1:]))
    if not vs:
        return 0, {}
    v = max(vs)
    out = {}
    for f in files:
        if f"/v{v}/" in "/" + f["path"]:
            try:
                out[f["path"].split("/")[-1]] = ws.download(f["path"])
            except Exception:
                pass
    return v, out

def run_qa(pid, user, mode="GATE", source_id=None, artifact=None) -> dict:
    state.require_member(pid, user)
    srcs = ([state.source(pid, source_id)] if source_id else
            [s for s in state.sources(pid) if s["qa_status"] == "REQUIRED"])
    srcs = [s for s in srcs if s]
    if not srcs:
        return {"verdict": "NOTHING_TO_CHECK",
                "detail": "no source with qa_status=REQUIRED — QA reviews "
                          "locked Stage-2 deliverables; confirm Stage 2 first"}
    ws = ProjectWorkspace(pid)
    rid = state.claim_run(pid, f"qa_{mode.lower()}", user,
                          source_id=srcs[0]["source_id"])
    try:
        all_ds, lines = [], []
        for s in srcs:
            sid = s["source_id"]
            state.supersede_open_defects(pid, sid)
            v, arts = _latest_stage2(ws, sid)
            ds = checks.run_static(arts, only=artifact)
            for d in ds:
                state.add_defect(pid, sid, rid, d.severity, d.artifact,
                                 d.description)
            all_ds += ds
            lines.append(f"## Source `{sid}` (stage-2 v{v}) — "
                         f"{len(ds)} finding(s)")
            lines += [f"- **{d.severity}** [{d.artifact}] {d.description}"
                      for d in ds]
        blocking = [d for d in all_ds if d.severity in BLOCKING]
        verdict = ("BLOCKED" if (mode == "GATE" and blocking) else
                   "RECOMMEND_SIGN_OFF" if mode == "GATE" else "REPORTED")
        stamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        qv = state.next_stage_version(pid, srcs[0]["source_id"], "qa")
        report = (f"# QA Report v{qv} — {stamp}\nMode: RUN_QA_{mode}"
                  f"{' ' + artifact if artifact else ''}\n"
                  f"Verdict: **{verdict}**\n\n" + "\n".join(lines) +
                  ("\n\n> Checker recommends sign-off. Type CONFIRM_QA_PASS "
                   "in the QA surface to close."
                   if verdict == "RECOMMEND_SIGN_OFF" else
                   "\n\n> CRITICAL/HIGH defects block sign-off. "
                   "REQUEST_REVISION with defect ids, or owner waiver."))
        p = ws.upload(f"qa/v{qv}/qa-report-v{qv}.md", report.encode())
        state.add_deliverable(pid, srcs[0]["source_id"], "qa", "qa_report",
                              qv, p, user)
        state.finish_run(rid, "SUCCEEDED", output_paths=[p])
        return {"run_id": rid, "verdict": verdict, "report": report,
                "defects": len(all_ds), "blocking": len(blocking),
                "report_path": p}
    except Exception as e:
        state.finish_run(rid, "FAILED", error=str(e))
        raise

def confirm_pass(pid, source_id, user) -> dict:
    state.require_member(pid, user, "EDITOR")
    qa_runs = [r for r in state.list_runs(pid, limit=200)
               if str(r.get("task_type", "")).startswith("qa_")
               and r.get("status") == "SUCCEEDED"
               and r.get("source_id") == source_id]
    if not qa_runs:
        raise state.Conflict("no checker run on record for this source - "
                             "run the checker (RUN_QA_GATE) before sign-off")
    open_blocking = [d for d in state.list_defects(pid, source_id, "OPEN")
                     if d["severity"] in BLOCKING]
    if open_blocking:
        raise state.Conflict(f"{len(open_blocking)} open CRITICAL/HIGH "
                             "defect(s) — resolve or waive first")
    state.add_gate(pid, "CONFIRM_QA_PASS", user, source_id=source_id)
    state.set_qa(pid, source_id, "PASSED")
    return {"source_id": source_id, "qa_status": "PASSED"}

def waive(pid, source_id, reason, user) -> dict:
    state.require_member(pid, user, "OWNER")
    if not reason or len(reason.strip()) < 10:
        raise state.Conflict("waiver requires a substantive reason "
                             "(at least 10 characters, recorded)")
    state.waive_defects(pid, source_id, reason)
    state.add_gate(pid, "CONFIRM_QA_PASS", user, source_id=source_id,
                   decision="WAIVED", comment=reason)
    state.set_qa(pid, source_id, "WAIVED")
    return {"source_id": source_id, "qa_status": "WAIVED"}
