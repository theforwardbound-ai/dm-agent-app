"""Prompt loaders. Local files in this phase; MLflow Prompt Registry at
@production when DM_PROMPT_SOURCE=registry (office/bank phase)."""
import functools, os, pathlib
from core import config

@functools.lru_cache(maxsize=128)
def prompt(name: str) -> str:
    f = pathlib.Path(config.PROMPT_DIR, f"{name}.prompt.md")
    if f.exists():
        return f.read_text(encoding="utf-8")
    return (f"[PROMPT STUB '{name}'] Perform the task named {name} for this "
            "data-modeling project using the project context and tools.")

@functools.lru_cache(maxsize=8)
def system(which: str) -> str:
    d = pathlib.Path("modeler/system_prompts" if which == "modeler"
                     else "checker/system_prompts")
    f = d / f"{which}_system.md"
    return f.read_text(encoding="utf-8") if f.exists() else f"[{which} system]"
