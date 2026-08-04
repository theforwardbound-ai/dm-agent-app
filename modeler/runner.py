"""Transitory-agent runner with the Investigation Loop (ADR 14).
Manifest-first context; the model pulls what it needs through tools;
Discuss grows the thread with zero artifacts; Generate emits one bundled
version (ADR 11) of every artifact."""
import json
from core import config, state, tasks, gates, tracing, prompts
from core.workspace import ProjectWorkspace
from modeler import agent_tools
from modeler import generators

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

def _loop(llm, model, sys_prompt, user_prompt, dispatcher, max_iters,
          tool_log: list):
    messages = [{"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}]
    tin = tout = 0
    for _ in range(max_iters):
        msg, usage = llm.chat(model, messages, agent_tools.TOOL_SCHEMAS)
        tin += usage["in"]; tout += usage["out"]
        if not msg.get("tool_calls"):
            return (msg.get("content") or "").strip(), tin, tout
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
            with tracing.span(f"tool:{t['name']}", {"args": str(args)[:400]}):
                try:
                    result = fn(**args) if fn else f"unknown tool {t['name']}"
                except Exception as e:
                    result = f"[tool error] {e}"
            tool_log.append(f"### {t['name']}({json.dumps(args)})\n"
                            f"{str(result)[:1200]}\n")
            messages.append({"role": "tool", "tool_call_id": t["id"],
                             "content": str(result)[:12000]})
    # iteration cap reached — force a conclusion
    messages.append({"role": "user", "content":
        "Iteration budget reached. Conclude NOW with your best complete "
        "deliverable from what you have verified; list anything unverified "
        "as an open unknown."})
    msg, usage = llm.chat(model, messages, None)
    tin += usage["in"]; tout += usage["out"]
    return (msg.get("content") or "").strip(), tin, tout

def run_task(pid: str, task_type: str, user: str, source_id: str | None = None,
             user_message: str = "", chat: bool = False,
             llm: agent_tools.LLM | None = None) -> dict:
    state.require_member(pid, user, "EDITOR")
    task_type = tasks.resolve(task_type)
    spec = tasks.check_preconditions(pid, task_type, source_id)
    rid = state.claim_run(pid, task_type, user, source_id)
    ws = ProjectWorkspace(pid)
    thread_key = spec.outputs_stage or task_type
    llm = llm or agent_tools.LLM()
    budget = agent_tools.ToolBudget()
    dispatcher = agent_tools.make_dispatcher(ws, pid, source_id, budget)
    tool_log: list[str] = []
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
                                   dispatcher, max_iters, tool_log)
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
                p = ws.upload(f"{base}/{spec.prompt}-response.md",
                              out.encode("utf-8"))
                state.add_deliverable(pid, source_id or "", spec.outputs_stage,
                                      "response_md", v, p, user)
                paths.append(p)
                if spec.outputs_stage == "stage2":
                    proj = state.get_project(pid)
                    for name, fn, fname in generators.STAGE2_SET:
                        try:
                            data = fn(out, proj, source_id or "")
                            pp = ws.upload(f"{base}/{fname}", data)
                            state.add_deliverable(pid, source_id or "",
                                                  "stage2", name, v, pp, user)
                            paths.append(pp)
                        except generators.SpecMissing as e:
                            paths.append(f"[skipped {name}: {e}]")
            elif not chat:
                p = ws.upload(f"tracking/agent-log/{rid[:8]}-{task_type}"
                              "-note.md", out.encode("utf-8"))
                paths.append(p)
            state.finish_run(rid, "SUCCEEDED", output_paths=paths,
                             trace_id=trace_id, tokens_in=tin,
                             tokens_out=tout,
                             prompt_versions={"source": "local",
                                              "prompt": spec.prompt})
            return {"run_id": rid, "status": "SUCCEEDED", "assistant": out,
                    "outputs": paths, "tokens_in": tin, "tokens_out": tout}
    except Exception as e:
        state.finish_run(rid, "FAILED", error=str(e))
        raise
