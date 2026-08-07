"""Background run worker — the piece that decouples a run from the request
that started it.

Without this, a 20-iteration Investigation Loop executes inside one HTTP
handler: the browser blocks for minutes, sees nothing until the end, and any
proxy timeout or the Free Edition 24h auto-stop destroys the work. Here the
request only claims the run and returns; these threads advance it, and every
iteration is checkpointed so a restart resumes instead of restarting.
"""
import queue
import threading
import traceback

from core import config, state

_q: "queue.Queue[str]" = queue.Queue()
_lock = threading.Lock()
_started = False


def submit(rid: str) -> None:
    """Hand a claimed run to the pool."""
    _q.put(rid)


def _drain(worker_name: str) -> None:
    while True:
        rid = _q.get()
        try:
            # imported lazily so core/ carries no dependency on modeler/
            from modeler import runner
            runner.execute_run(rid)
        except Exception:
            # execute_run already marked the run FAILED and emitted the event;
            # swallow here so one bad run cannot kill the worker thread.
            traceback.print_exc()
        finally:
            _q.task_done()


def requeue_orphans() -> list[str]:
    """Re-submit runs left QUEUED/RUNNING by a previous process. Only safe at
    boot, before this process has any run in flight."""
    revived = []
    for r in state.resumable_runs():
        rid = r["run_id"]
        try:
            state.append_event(rid, "status", "REQUEUED",
                               "picked up after restart",
                               pid=r.get("project_id"))
        except Exception:
            pass
        submit(rid)
        revived.append(rid)
    return revived


def start(resume: bool | None = None) -> None:
    """Idempotent: start the pool once per process."""
    global _started
    with _lock:
        if _started:
            return
        for i in range(max(1, config.WORKER_THREADS)):
            name = f"dm-worker-{i}"
            threading.Thread(target=_drain, args=(name,), name=name,
                             daemon=True).start()
        _started = True
    if config.WORKER_RESUME if resume is None else resume:
        revived = requeue_orphans()
        if revived:
            print(f"[worker] requeued {len(revived)} orphaned run(s): "
                  + ", ".join(r[:8] for r in revived))


def depth() -> int:
    return _q.qsize()
