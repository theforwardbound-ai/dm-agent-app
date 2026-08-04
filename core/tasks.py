"""Task registry (generic set for the Free Edition cycle; office merge
adds the full bank prompt inventory). Preconditions per ratified design:
gate requirements, QA-handoff lockout, CADP dependency guard."""
from dataclasses import dataclass
import json
from core import state

@dataclass(frozen=True)
class TaskSpec:
    prompt: str
    mode: str = "interactive"          # interactive | long
    tier: str = "frontier"
    per_source: bool = False
    requires: tuple = ()
    outputs_stage: str | None = None

TASKS: dict[str, TaskSpec] = {
 "stage0_data_product_planning": TaskSpec("stage0-data-product-planning",
      outputs_stage="stage0"),
 "parse_idra": TaskSpec("parse-idra", per_source=True, tier="standard",
      requires=("CONFIRM_DATA_PRODUCT_PLAN",)),
 "validate_idra": TaskSpec("validate-idra", per_source=True, tier="standard",
      requires=("CONFIRM_DATA_PRODUCT_PLAN",)),
 "stage1_conceptual_erd": TaskSpec("stage1-conceptual-erd", "long",
      per_source=True, requires=("CONFIRM_INPUT_PARSED",),
      outputs_stage="stage1"),
 "stage2_physical_model": TaskSpec("stage2-physical-model", "long",
      per_source=True, requires=("CONFIRM_STAGE1_FINAL",),
      outputs_stage="stage2"),
 "stage2_cadp": TaskSpec("stage2-cadp", "long", per_source=True,
      requires=("CONFIRM_STAGE1_FINAL",), outputs_stage="stage2"),
 "enhancement_delta": TaskSpec("enhancement-delta", "long", per_source=True,
      requires=("CONFIRM_STAGE2_FINAL",), outputs_stage="stage2"),
 "stm_walkthrough_pack": TaskSpec("stm-walkthrough-pack",
      requires=("CONFIRM_STAGE2_FINAL",), per_source=True),
 "unknowns_triage": TaskSpec("unknowns-triage", tier="standard"),
}
SLASH = {f"/{k.replace('_','-')}": k for k in TASKS}
ADVANCING = {"stage1_conceptual_erd", "stage2_physical_model", "stage2_cadp",
             "stm_walkthrough_pack"}

class Blocked(Exception): pass

def resolve(task_type: str) -> str:
    t = SLASH.get(task_type, task_type)
    if t not in TASKS:
        raise Blocked(f"unknown task '{task_type}'")
    return t

def check_preconditions(pid: str, task_type: str, source_id: str | None) -> TaskSpec:
    spec = TASKS[task_type]
    if spec.per_source and not source_id:
        raise Blocked(f"{task_type} is per-source; select a source")
    have = state.confirmed_gates(pid, source_id)
    missing = [g for g in spec.requires if g not in have]
    if missing:
        raise Blocked(f"gate(s) not confirmed: {', '.join(missing)}")
    src = state.source(pid, source_id) if source_id else None
    if (src and src["qa_status"] == "REQUIRED" and task_type in ADVANCING):
        raise Blocked("QA pending for this source — run the checker "
                      "(RUN_QA_GATE) or record a waiver before proceeding")
    if task_type == "stage2_cadp" and src:
        deps = src.get("depends_on")
        deps = json.loads(deps) if isinstance(deps, str) else (deps or [])
        for dep in deps:
            d = state.source(pid, dep)
            if not d or d["stage"] != "stage2_confirmed" or \
               d["qa_status"] not in ("PASSED", "WAIVED"):
                raise Blocked(f"CADP blocked: dependency '{dep}' is not "
                              "Stage-2 confirmed with QA passed/waived")
    return spec
