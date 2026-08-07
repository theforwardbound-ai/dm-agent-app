"""THE SEAM (ADR 3). Every interface — the minimal HTML shell now, a
developer-built UI later — talks only to this class. No HTTP, no HTML
here. Domain errors wrap into UiError(kind, message)."""
import base64
from core import config, state, gates, tasks, worker
from core.workspace import ProjectWorkspace
from modeler import runner
from checker import qa as checker_qa

class UiError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind          # blocked | forbidden | conflict | notfound

def _wrap(fn):
    def inner(*a, **k):
        try:
            return fn(*a, **k)
        except tasks.Blocked as e:
            raise UiError("blocked", str(e))
        except state.Forbidden as e:
            raise UiError("forbidden", str(e))
        except state.Conflict as e:
            raise UiError("conflict", str(e))
        except state.NotFound as e:
            raise UiError("notfound", str(e))
        except ValueError as e:
            raise UiError("blocked", str(e))
    return inner

class LocalBackend:
    def __init__(self, user_email: str):
        self.user = (user_email or "").lower()
        if not self.user:
            raise UiError("forbidden", "no acting identity")

    def role(self) -> str:
        return "maker" if self.user in config.MAKER_EMAILS else "user"

    # ---------- projects ----------
    @_wrap
    def create_project(self, payload: dict) -> dict:
        p = state.create_project(payload, self.user)
        ProjectWorkspace(p["project_id"]).ensure_skeleton()
        return p

    @_wrap
    def register_source(self, pid: str, payload: dict) -> dict:
        state.require_member(pid, self.user, "EDITOR")
        state.upsert_source(pid, payload["source_id"],
                            modelling_profile=payload.get("modelling_profile"),
                            depends_on=payload.get("depends_on") or [],
                            is_shared_dimension=bool(
                                payload.get("is_shared_dimension")))
        return state.source(pid, payload["source_id"])

    @_wrap
    def status_bundle(self) -> dict:
        """The single call the minimal UI paints from."""
        proj = state.active_project(self.user)
        if not proj:
            return {"project": None, "user": self.user,
                    "role": self.role()}
        pid = proj["project_id"]
        state.require_member(pid, self.user)
        srcs = state.sources(pid)
        out_sources = []
        for s in srcs:
            g = state.confirmed_gates(pid, s["source_id"])
            out_sources.append({**{k: s.get(k) for k in
                ("source_id", "modelling_profile", "stage", "qa_status")},
                "open_defects": len(state.list_defects(pid, s["source_id"],
                                                       "OPEN")),
                "next_gate": gates.next_gate(s, g)})
        runs = state.list_runs(pid, limit=1)
        return {"project": {k: str(v) for k, v in proj.items()},
                "user": self.user, "role": self.role(),
                "sources": out_sources,
                "tasks": {k: {"slash": f"/{k.replace('_','-')}",
                              "mode": v.mode, "per_source": v.per_source,
                              "requires": list(v.requires)}
                          for k, v in tasks.TASKS.items()},
                "gates": gates.GATE_EFFECTS,
                "last_run": ({k: str(v) for k, v in runs[0].items()}
                             if runs else None),
                "open_unknowns": len(state.list_unknowns(pid, status="OPEN"))}

    # ---------- files ----------
    @_wrap
    def tree(self) -> list[dict]:
        proj = state.active_project(self.user)
        if not proj: return []
        state.require_member(proj["project_id"], self.user)
        return ProjectWorkspace(proj["project_id"]).listdir("")

    @_wrap
    def file_bytes(self, rel: str) -> bytes:
        proj = state.active_project(self.user)
        state.require_member(proj["project_id"], self.user)
        return ProjectWorkspace(proj["project_id"]).download(rel)

    @_wrap
    def upload_b64(self, rel_folder: str, filename: str, b64: str) -> str:
        proj = state.active_project(self.user)
        state.require_member(proj["project_id"], self.user, "EDITOR")
        allowed = ("input/", "tracking/")
        if not any(rel_folder.startswith(a) for a in allowed):
            raise state.Forbidden("uploads land under input/ only")
        data = base64.b64decode(b64.encode())
        return ProjectWorkspace(proj["project_id"]).upload(
            f"{rel_folder.rstrip('/')}/{filename}", data)

    # ---------- conversation ----------
    @_wrap
    def thread(self, source_id: str | None, stage_or_task: str) -> list[dict]:
        proj = state.active_project(self.user)
        state.require_member(proj["project_id"], self.user)
        rows = state.list_messages(proj["project_id"], stage_or_task,
                                   source_id, limit=50)
        return [{k: str(v) for k, v in r.items()} for r in rows]

    @_wrap
    def send(self, source_id: str | None, task_type: str, message: str,
             chat: bool = False, llm=None, wait: bool = True) -> dict:
        """Gate-or-task routing: a message that IS a gate command records
        the gate; anything else runs the selected task.

        wait=True executes the run inline and returns the finished result —
        the path scripts and the golden-path smoke test use. wait=False (what
        the HTTP layer passes) claims the run, hands it to the worker, and
        returns immediately so the caller can tail /api/run/events."""
        proj = state.active_project(self.user)
        pid = proj["project_id"]
        g = gates.gate_in_text(message)
        if g:
            state.require_member(pid, self.user, "EDITOR")
            if g not in gates.MODELER_GATES:
                raise state.Forbidden(
                    f"{g} belongs to the checker surface — use the QA panel")
            comment = message.strip()[len(g):].strip() or None
            sid = None if g in gates.PROJECT_GATES else source_id
            state.add_gate(pid, g, self.user, source_id=sid,
                           comment=comment)
            return {"kind": "gate", "gate": g,
                    "effect": gates.GATE_EFFECTS[g]}
        msg = (message or "").strip()
        if msg.startswith("/"):
            head, _, rest = msg.partition(" ")
            task_type = tasks.resolve(head)
            message = rest.strip()
        if wait:
            r = runner.run_task(pid, task_type, self.user, source_id=source_id,
                                user_message=message, chat=chat, llm=llm)
            return {"kind": "run", **r}
        rid = runner.enqueue_task(pid, task_type, self.user,
                                  source_id=source_id, user_message=message,
                                  chat=chat)
        worker.submit(rid)
        return {"kind": "run", "run_id": rid, "status": "QUEUED"}

    # ---------- run observation (what makes a long run watchable) ----------
    def _own_run(self, rid: str, min_role: str = "VIEWER") -> dict:
        run = state.get_run(rid)
        state.require_member(run["project_id"], self.user, min_role)
        return run

    @_wrap
    def run_status(self, rid: str) -> dict:
        run = self._own_run(rid)
        return {k: str(v) if v is not None else None for k, v in run.items()}

    @_wrap
    def run_events(self, rid: str, since: int = 0, limit: int = 500) -> dict:
        run = self._own_run(rid)
        evs = state.list_events(rid, since=since, limit=limit)
        return {"run_id": rid, "status": run["status"],
                "tokens_in": run.get("tokens_in"),
                "tokens_out": run.get("tokens_out"),
                "cursor": evs[-1]["seq"] if evs else since,
                "done": run["status"] in state.TERMINAL_RUN_STATES,
                "events": [{"seq": e["seq"], "kind": e["kind"],
                            "name": e["name"], "payload": e["payload"],
                            "at": str(e["created_at"])} for e in evs]}

    @_wrap
    def cancel_run(self, rid: str) -> dict:
        run = self._own_run(rid, "EDITOR")
        if run["status"] in state.TERMINAL_RUN_STATES:
            return {"run_id": rid, "status": run["status"],
                    "note": "already finished"}
        state.set_run_status(rid, "CANCELLED")
        state.append_event(rid, "status", "CANCELLED",
                           f"cancelled by {self.user}",
                           pid=run["project_id"])
        return {"run_id": rid, "status": "CANCELLED"}

    # ---------- QA (checker surface) ----------
    @_wrap
    def qa_run(self, mode: str, source_id: str | None, artifact: str | None):
        proj = state.active_project(self.user)
        return checker_qa.run_qa(proj["project_id"], self.user,
                                 mode=(mode or "GATE").upper(),
                                 source_id=source_id, artifact=artifact)

    @_wrap
    def qa_pass(self, source_id: str):
        proj = state.active_project(self.user)
        return checker_qa.confirm_pass(proj["project_id"], source_id,
                                       self.user)

    @_wrap
    def qa_waive(self, source_id: str, reason: str):
        proj = state.active_project(self.user)
        return checker_qa.waive(proj["project_id"], source_id, reason,
                                self.user)

    @_wrap
    def defects(self, source_id: str | None = None):
        proj = state.active_project(self.user)
        state.require_member(proj["project_id"], self.user)
        rows = state.list_defects(proj["project_id"], source_id)
        return [{k: str(v) for k, v in r.items()} for r in rows]

def resolve_user(headers: dict) -> str:
    for h in ("x-forwarded-email", "x-forwarded-preferred-username",
              "x-forwarded-user"):
        if headers.get(h):
            return headers[h]
    return config.DEV_USER or ""
