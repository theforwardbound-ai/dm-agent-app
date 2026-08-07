"""Transitory-agent runner with the Investigation Loop (ADR 14).
Manifest-first context; the model pulls what it needs through tools;
Discuss grows the thread with zero artifacts; Generate emits one bundled
version (ADR 11) of every artifact.

A run is durable and outlives the request that started it. Every loop
iteration appends run_events (what the UI tails, and what the audit trail
keeps) and writes a checkpoint, so an app restart or the Free Edition 24h
auto-stop resumes mid-loop instead of losing the work.
"""
import json
from core import config, state, tasks, gates, tracing, prompts
from core.workspace import ProjectWorkspace
from modeler import agent_tools
from modeler import generators

class Cancelled(Exception): pass

def _manifest(ws, pid, source_id) -> str:
    proj = state.get_project(pid)
    files = ws.listdir("")
    listing = "\n".join(f"- {f['path']} ({f['size']} B)" for f in files[:150])
    return (
        "## Project\n" + json.dumps({k: str(proj.get(k)) for k in
        ("name", "tenant", "node_name", "domain", "data_product", "dp_type",
         "target_catalog", "primary_input_type")}, indent=1) +
        "\n\n## Confirmed gates\n" +
        ("\n".join(sorted(state.confirmed_gates(pid, source_id))) or "(none)") +
        "\n\n## Sources\n" + json.dumps(state.sources(pid), indent=1,
                                        default=str) +
        "\n\n## Workspace files (read what you need via tools)\n" +
        (listing or "(no files yet)"))

def _thread(pid, thread_key, source_id) -> str:
    msgs = state.list_messages(pid, thread_key, source_id, limit=20)
    if not msgs:
        return "(no prior conversation this stage)"
    body, total = [], 0
    for m in msgs:
        line = f"{m['role']}: {m['content']}"
        total += len(line)
        if total > 15000:
            body.append("[...older turns trimmed]")
            break
        body.append(line)
    return "\n".join(body)

def _emit(rid, pid, kind, name=None, payload=None):
    """Best-effort event append; never let telemetry break a run."""
    if not rid:
        return
    try:
        state.append_event(rid, kind, name, payload, pid=pid)
    except Exception:
        pass

def _cancel_requested(rid) -> bool:
    if not rid:
        return False
    try:
        return state.get_run(rid)["status"] == "CANCELLED"
    except Exception:
        return False

def _loop(llm, model, sys_prompt, user_prompt, dispatcher, max_iters,
          tool_log: list, rid=None, pid=None, resume: dict | None = None):
    if resume:
        messages = resume["messages"]
        start = int(resume["loop_iter"] or 0)
        tin, tout = int(resume["tokens_in"] or 0), int(resume["tokens_out"] or 0)
        tool_log.extend(resume["tool_log"])
        _emit(rid, pid, "status", "RESUMED", f"resuming at iteration {start}")
    else:
        messages = [{"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}]
        start, tin, tout = 0, 0, 0

    for i in range(start, max_iters):
        if _cancel_requested(rid):
            raise Cancelled(f"run cancelled at iteration {i}")
        _emit(rid, pid, "iteration", str(i + 1),
              {"iteration": i + 1, "max": max_iters, "model": model})

        msg, usage = llm.chat(model, messages, agent_tools.TOOL_SCHEMAS)
        tin += usage["in"]; tout += usage["out"]

        if not msg.get("tool_calls"):
            content = (msg.get("content") or "").strip()
            _emit(rid, pid, "assistant", "final",
                  {"preview": content[:600], "tokens_in": tin,
                   "tokens_out": tout})
            if rid:
                state.save_checkpoint(rid, pid, i + 1, messages, tool_log,
                                      tin, tout)
            return content, tin, tout

        if msg.get("content"):
            _emit(rid, pid, "assistant", "thinking",
                  {"preview": msg["content"][:600]})

        messages.append({"role": "assistant",
                         "content": msg.get("content") or "",
                         "tool_calls": [
                             {"id": t["id"], "type": "function",
                              "function": {"name": t["name"],
                                           "arguments": t["arguments"]}}
                             for t in msg["tool_calls"]]})
        for t in msg["tool_calls"]:
            fn = dispatcher.get(t["name"])
            try:
                args = json.loads(t["arguments"] or "{}")
            except Exception:
                args = {}
            _emit(rid, pid, "tool_call", t["name"], {"args": args})
            with tracing.span(f"tool:{t['name']}", {"args": str(args)[:400]}):
                try:
                    result = fn(**args) if fn else f"unknown tool {t['name']}"
                    ok = True
                except Exception as e:
                    result = f"[tool error] {e}"
                    ok = False
            _emit(rid, pid, "tool_result", t["name"],
                  {"ok": ok, "preview": str(result)[:800],
                   "chars": len(str(result))})
            tool_log.append(f"### {t['name']}({json.dumps(args)})\n"
                            f"{str(result)[:1200]}\n")
            messages.append({"role": "tool", "tool_call_id": t["id"],
                             "content": str(result)[:12000]})

        if rid:
            state.save_checkpoint(rid, pid, i + 1, messages, tool_log,
                                  tin, tout)

    # iteration cap reached — force a conclusion
    _emit(rid, pid, "budget", "iterations_exhausted",
          {"max": max_iters, "note": "forcing conclusion"})
    messages.append({"role": "user", "content":
        "Iteration budget reached. Conclude NOW with your best complete "
        "deliverable from what you have verified; list anything unverified "
        "as an open unknown."})
    msg, usage = llm.chat(model, messages, None)
    tin += usage["in"]; tout += usage["out"]
    content = (msg.get("content") or "").strip()
    _emit(rid, pid, "assistant", "final",
          {"preview": content[:600], "tokens_in": tin, "tokens_out": tout})
    return content, tin, tout


_SPEC_ONLY_SYSTEM = (
    "You emit exactly one fenced code block and nothing else: ```json "
    "MODEL_SPEC followed by the JSON and a closing fence. No prose, no "
    "explanation, no second block.")

_SPEC_ONLY_USER = (
    "Below is a physical model you produced. Its machine-readable "
    "MODEL_SPEC block is missing or was cut off.\n\n"
    "Emit the MODEL_SPEC block for it now, covering EVERY table described.\n"
    "Shape:\n"
    '```json MODEL_SPEC\n'
    '{{\"grain\": {{\"<table>\": \"One row per ...\"}}, \"tables\": '
    '[{{\"name\": \"...\", \"columns\": [{{\"name\": \"...\", \"type\": '
    '\"STRING\", \"nullable\": true, \"pk\": false, \"privacy\": '
    '\"PUBLIC|INTERNAL|CONFIDENTIAL\", \"source_field\": \"...\"}}]}}]}}\n'
    "```\n\n"
    "Write the JSON COMPACTLY — no indentation, no newlines inside the "
    "JSON, shortest valid form. The whole block must fit in one response, "
    "so compactness matters more than readability.\n\n"
    "--- physical model ---\n{body}")


def _ensure_model_spec(llm, model, out: str, tin: int, tout: int, rid, pid):
    """Stage 2's six generators all key off one fenced MODEL_SPEC block.

    A full physical model plus that block routinely exceeds the endpoint's
    output-token ceiling, and the block sits at the END — so truncation drops
    exactly the machine-readable part while leaving prose that looks fine.
    When it is missing, ask for the spec ALONE and compact, so the entire
    budget goes to JSON."""
    try:
        generators.extract_spec(out)
        return out, tin, tout
    except generators.SpecMissing as e:
        _emit(rid, pid, "budget", "model_spec_missing",
              {"reason": str(e), "note": "requesting spec-only completion"})

    msgs = [{"role": "system", "content": _SPEC_ONLY_SYSTEM},
            {"role": "user", "content": _SPEC_ONLY_USER.format(body=out)}]
    try:
        msg, usage = llm.chat(model, msgs, None)
    except Exception as exc:
        _emit(rid, pid, "budget", "model_spec_retry_failed", {"error": str(exc)})
        return out, tin, tout
    tin += usage["in"]; tout += usage["out"]
    block = (msg.get("content") or "").strip()

    merged = out + "\n\n" + block
    try:
        spec = generators.extract_spec(merged)
    except generators.SpecMissing as e:
        _emit(rid, pid, "budget", "model_spec_retry_failed", {"reason": str(e)})
        return out, tin, tout
    _emit(rid, pid, "budget", "model_spec_recovered",
          {"tables": len(spec.get("tables") or [])})
    return merged, tin, tout


def enqueue_task(pid: str, task_type: str, user: str,
                 source_id: str | None = None, user_message: str = "",
                 chat: bool = False) -> str:
    """Claim a durable run and park it for the worker. Preconditions are
    checked here so the caller still gets 422/403/409 synchronously."""
    state.require_member(pid, user, "EDITOR")
    task_type = tasks.resolve(task_type)
    tasks.check_preconditions(pid, task_type, source_id)
    rid = state.claim_run(pid, task_type, user, source_id, status="QUEUED")
    state.append_event(rid, "params", task_type,
                       {"project_id": pid, "task_type": task_type,
                        "user": user, "source_id": source_id,
                        "user_message": user_message, "chat": chat}, pid=pid)
    state.append_event(rid, "status", "QUEUED",
                       f"{task_type} queued", pid=pid)
    return rid


def _params_of(rid: str) -> dict:
    for ev in state.list_events(rid, since=0, limit=50):
        if ev["kind"] == "params":
            return json.loads(ev["payload"])
    raise state.NotFound(f"run {rid} has no params event")


def execute_run(rid: str, llm: agent_tools.LLM | None = None) -> dict:
    """Advance a claimed run to a terminal state. Safe to call again after a
    crash: it picks up from the last checkpoint."""
    p = _params_of(rid)
    pid, task_type = p["project_id"], p["task_type"]
    source_id, user = p.get("source_id"), p["user"]
    user_message, chat = p.get("user_message", ""), bool(p.get("chat"))

    spec = tasks.TASKS[task_type]
    ws = ProjectWorkspace(pid)
    thread_key = spec.outputs_stage or task_type
    llm = llm or agent_tools.LLM()
    budget = agent_tools.ToolBudget()
    dispatcher = agent_tools.make_dispatcher(ws, pid, source_id, budget)
    resume = state.load_checkpoint(rid)
    tool_log: list[str] = []

    state.set_run_status(rid, "RUNNING")
    _emit(rid, pid, "status", "RUNNING",
          f"{'resumed' if resume else 'started'} — {task_type}")
    try:
        attrs = {"project_id": pid, "tenant": state.project_tenant(pid),
                 "source_id": source_id or "", "task_type": task_type,
                 "run_id": rid, "agent_version": config.AGENT_VERSION,
                 "mode": "discuss" if chat else "generate",
                 "fake_llm": config.FAKE_LLM}
        with tracing.span(f"task:{task_type}", attrs):
            trace_id = tracing.current_trace_id()
            user_prompt = (
                f"# Task prompt\n{prompts.prompt(spec.prompt)}\n\n"
                f"# Project manifest\n{_manifest(ws, pid, source_id)}\n\n"
                f"# Conversation so far (this stage)\n"
                f"{_thread(pid, thread_key, source_id)}\n\n"
                f"# User message\n{user_message or '(none)'}\n\n"
                f"# Mode\n"
                + ("DISCUSS: answer/advise in the thread; do NOT produce the "
                   "final deliverable document." if chat else
                   "GENERATE: investigate with tools as needed, then produce "
                   "the complete deliverable markdown."))
            max_iters = (config.LOOP_ITERS_LONG if spec.mode == "long" and
                         not chat else config.LOOP_ITERS_CHAT)
            out, tin, tout = _loop(llm, config.model_for(spec.tier),
                                   prompts.system("modeler"), user_prompt,
                                   dispatcher, max_iters, tool_log,
                                   rid=rid, pid=pid, resume=resume)
            if not chat and spec.outputs_stage == "stage2":
                out, tin, tout = _ensure_model_spec(
                    llm, config.model_for(spec.tier), out, tin, tout, rid, pid)
            if user_message:
                state.add_message(pid, thread_key, "user", user_message, user,
                                  source_id, rid)
            state.add_message(pid, thread_key, "assistant", out, user,
                              source_id, rid)
            paths: list[str] = []
            if tool_log:
                paths.append(ws.upload(
                    f"tracking/agent-log/{rid[:8]}-{task_type}.md",
                    ("# Investigation log\n\n" + "\n".join(tool_log))
                    .encode("utf-8")))
            if not chat and spec.outputs_stage:
                sub = f"output/{spec.outputs_stage}"
                if spec.per_source and source_id:
                    sub += f"/{source_id}"
                v = state.next_stage_version(pid, source_id or "",
                                             spec.outputs_stage)
                base = f"{sub}/v{v}"
                pth = ws.upload(f"{base}/{spec.prompt}-response.md",
                                out.encode("utf-8"))
                state.add_deliverable(pid, source_id or "", spec.outputs_stage,
                                      "response_md", v, pth, user)
                paths.append(pth)
                _emit(rid, pid, "artifact", "response_md", {"path": pth})
                if spec.outputs_stage == "stage2":
                    proj = state.get_project(pid)
                    for name, fn, fname in generators.STAGE2_SET:
                        try:
                            data = fn(out, proj, source_id or "")
                            pp = ws.upload(f"{base}/{fname}", data)
                            state.add_deliverable(pid, source_id or "",
                                                  "stage2", name, v, pp, user)
                            paths.append(pp)
                            _emit(rid, pid, "artifact", name, {"path": pp})
                        except generators.SpecMissing as e:
                            paths.append(f"[skipped {name}: {e}]")
                            _emit(rid, pid, "artifact", name,
                                  {"skipped": str(e)})
            elif not chat:
                pth = ws.upload(f"tracking/agent-log/{rid[:8]}-{task_type}"
                                "-note.md", out.encode("utf-8"))
                paths.append(pth)
            state.finish_run(rid, "SUCCEEDED", output_paths=paths,
                             trace_id=trace_id, tokens_in=tin,
                             tokens_out=tout,
                             prompt_versions={"source": "local",
                                              "prompt": spec.prompt})
            state.clear_checkpoint(rid)
            _emit(rid, pid, "status", "SUCCEEDED",
                  {"outputs": paths, "tokens_in": tin, "tokens_out": tout})
            return {"run_id": rid, "status": "SUCCEEDED", "assistant": out,
                    "outputs": paths, "tokens_in": tin, "tokens_out": tout}
    except Cancelled as e:
        state.finish_run(rid, "CANCELLED", error=str(e))
        state.clear_checkpoint(rid)
        _emit(rid, pid, "status", "CANCELLED", str(e))
        return {"run_id": rid, "status": "CANCELLED", "error": str(e)}
    except Exception as e:
        state.finish_run(rid, "FAILED", error=str(e))
        _emit(rid, pid, "status", "FAILED", str(e))
        raise


def run_task(pid: str, task_type: str, user: str, source_id: str | None = None,
             user_message: str = "", chat: bool = False,
             llm: agent_tools.LLM | None = None) -> dict:
    """Synchronous enqueue+execute. Kept for scripts, tests and the golden
    path; the app enqueues and lets the worker drive instead."""
    rid = enqueue_task(pid, task_type, user, source_id, user_message, chat)
    return execute_run(rid, llm=llm)
