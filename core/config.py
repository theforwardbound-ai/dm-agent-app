"""Env-driven settings. Same code, three environments:
local dev (DuckDB + local fs + fake LLM), Databricks Free Edition
(Lakebase + UC volume + real endpoint), bank workspace (same as Free
with bank values)."""
import os

def _env(k, d=None):
    v = os.getenv(k, d)
    return v if v not in ("", None) else d

AGENT_VERSION   = _env("DM_AGENT_VERSION", "0.2.5-freeedition")

CATALOG         = _env("DM_CATALOG", "workspace")          # Free Edition default catalog
SCHEMA          = _env("DM_SCHEMA", "dm_agent")
FILES_VOLUME    = _env("DM_FILES_VOLUME")            # explicit opt-in

DATABASE_URL    = _env("DM_DATABASE_URL", "duckdb:////tmp/dm_dev.duckdb")
LAKEBASE_INSTANCE = _env("DM_LAKEBASE_INSTANCE")           # set on platform -> auto-cred

LOCAL_FS_ROOT   = _env("DM_LOCAL_FS_ROOT")
if not LOCAL_FS_ROOT and not FILES_VOLUME:
    LOCAL_FS_ROOT = "/tmp/dm_workspace"   # first-light store (ephemeral)
PROMPT_DIR      = _env("DM_PROMPT_DIR", "./prompts_local")

# Defaults are what this Free Edition workspace actually serves. Claude is NOT
# a foundation-model endpoint here; the bank workspace overrides these with
# DM_MODEL_FRONTIER / DM_MODEL_STANDARD and should point frontier at Claude.
#
# Measured on a 66-field IDRA (see scripts/probe_models.py, and the run log):
#   gpt-oss-120b        usable — reads progressively, escalates max_rows on
#                       truncation, produces a correct stage-1 model
#   llama-4-maverick    NOT usable — degrades into emitting tool calls as
#                       prose within 2-3 turns and cannot recover from a tool
#                       error. Passes a 2-turn probe; fails a real loop.
MODEL_FRONTIER  = _env("DM_MODEL_FRONTIER", "databricks-gpt-oss-120b")
MODEL_STANDARD  = _env("DM_MODEL_STANDARD", "databricks-gpt-oss-120b")
FAKE_LLM        = _env("DM_FAKE_LLM", "1") == "1"
DBX_HOST        = _env("DM_DATABRICKS_HOST")               # local real-call path
DBX_TOKEN       = _env("DM_DATABRICKS_TOKEN")
THINKING_BUDGET = int(_env("DM_THINKING_BUDGET", "0"))     # 0 = off (see runbook)

LOOP_ITERS_LONG = int(_env("DM_LOOP_ITERS_LONG", "20"))    # ADR 14 budgets
LOOP_ITERS_CHAT = int(_env("DM_LOOP_ITERS_INTERACTIVE", "8"))
LOOP_READ_BUDGET = int(_env("DM_LOOP_READ_BUDGET", "60000"))
# 8192 is the ceiling on this workspace's Llama/gpt-oss endpoints; Claude on
# the bank workspace accepts more, so raise DM_MAX_TOKENS there.
MAX_TOKENS_OUT  = int(_env("DM_MAX_TOKENS", "8192"))

DEV_USER        = _env("DM_DEV_USER", "maker@local.dev")
MAKER_EMAILS    = [e.strip().lower() for e in _env("DM_MAKER_EMAILS", DEV_USER or "").split(",") if e.strip()]
ACTIVE_PROJECT  = _env("DM_ACTIVE_PROJECT")                # optional pin; else most recent

WORKER_THREADS  = int(_env("DM_WORKER_THREADS", "2"))      # runs execute here
WORKER_RESUME   = _env("DM_WORKER_RESUME", "1") == "1"     # requeue on boot

SERVER_PORT     = int(_env("DATABRICKS_APP_PORT", _env("DM_SERVER_PORT", "8000")))
TRACING         = _env("DM_TRACING", "1") == "1"
MLFLOW_EXPERIMENT = _env("MLFLOW_EXPERIMENT", "dm-agent-free")

def model_for(tier: str) -> str:
    return MODEL_FRONTIER if tier == "frontier" else MODEL_STANDARD
