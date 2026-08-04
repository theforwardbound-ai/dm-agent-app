"""MLflow tracing with graceful degradation (ADR 9). With mlflow absent
or DM_TRACING=0, every call is a no-op and the app runs identically."""
import contextlib, os
from core import config

_ENABLED = None

def enabled() -> bool:
    global _ENABLED
    if _ENABLED is not None:
        return _ENABLED
    if not config.TRACING:
        _ENABLED = False; return False
    try:
        import mlflow
        if os.getenv("MLFLOW_TRACKING_URI"):
            mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))
        try:
            mlflow.set_experiment(config.MLFLOW_EXPERIMENT)
        except Exception:
            pass
        _ENABLED = True
    except Exception:
        _ENABLED = False
    return _ENABLED

def span(name: str, attributes: dict | None = None):
    if not enabled():
        return contextlib.nullcontext()
    import mlflow
    return mlflow.start_span(name=name, attributes=attributes or {})

def current_trace_id() -> str | None:
    if not enabled():
        return None
    try:
        import mlflow
        s = mlflow.get_current_active_span()
        return getattr(s, "request_id", None) or getattr(s, "trace_id", None)
    except Exception:
        return None
