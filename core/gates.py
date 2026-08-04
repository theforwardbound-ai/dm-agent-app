"""Gate catalogue (generic build — office merge replaces effect text with
the bank repo's exact table). Gates are durable state transitions."""
GATE_EFFECTS = {
 "CONFIRM_DATA_PRODUCT_PLAN": "Lock Stage 0 plan; enable parse and stage prompts",
 "CONFIRM_INPUT_PARSED":      "Lock extraction; enable Stage 1",
 "CONFIRM_STAGE1_FINAL":      "Lock conceptual ERD; enable Stage 2",
 "CONFIRM_STAGE2_FINAL":      "Lock physical model + STM; QA becomes REQUIRED",
 "CONFIRM_AADP_STAGE1_FINAL": "Lock AADP conceptual model",
 "CONFIRM_AADP_STAGE2_FINAL": "Lock AADP physical model + STM; QA REQUIRED",
 "CONFIRM_CADP_STAGE2_FINAL": "Lock CADP physical model + STM; QA REQUIRED",
 "CONFIRM_SCOPE_RECONCILED":  "Lock BRD/SRD scope reconciliation",
 "CONFIRM_DELTA_FINAL":       "Lock enhancement delta",
 "CONFIRM_WALKTHROUGH_PACK":  "Lock walkthrough deck",
 "MARK_GAP_RESOLVED":         "Resolve a triaged gap",
 "REQUEST_REVISION":          "User specifies changes; iterate on current stage",
 "ADD_INPUT":                 "New input documents to incorporate",
 "CONFIRM_QA_PASS":           "Checker sign-off accepted; closes QA for the source",
}
ALIASES = {"CONFIRM_IDRA_PARSED": "CONFIRM_INPUT_PARSED", "ADD_IDRA": "ADD_INPUT"}
MODELER_GATES = set(GATE_EFFECTS) - {"CONFIRM_QA_PASS"}
PROJECT_GATES = {"CONFIRM_DATA_PRODUCT_PLAN", "CONFIRM_SCOPE_RECONCILED"}

def canonical(name: str) -> str:
    n = name.strip().upper()
    n = ALIASES.get(n, n)
    if n not in GATE_EFFECTS:
        raise ValueError(f"unknown gate '{name}'")
    return n

def gate_in_text(text: str) -> str | None:
    """Chat-command detection: a message that IS a gate command."""
    t = (text or "").strip().upper()
    head = t.split()[0] if t else ""
    try:
        return canonical(head)
    except ValueError:
        return None

def next_gate(src: dict, gates_confirmed: set[str]) -> str | None:
    """Advisory only: what the status rail displays."""
    if src["qa_status"] == "REQUIRED":
        return "CONFIRM_QA_PASS (checker surface)"
    order = ["CONFIRM_DATA_PRODUCT_PLAN", "CONFIRM_INPUT_PARSED",
             "CONFIRM_STAGE1_FINAL", "CONFIRM_STAGE2_FINAL"]
    for g in order:
        if g not in gates_confirmed:
            return g
    return None
