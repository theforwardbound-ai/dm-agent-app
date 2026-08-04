# dm-agent-app — Free Edition build

Platform-shaped implementation of the ratified backend design (v1.0,
2026-08-04, §12 defaults + ADR 11 version bundling + ADR 14
Investigation Loop). Synthetic content only — no bank IP; the office
merge later swaps in real prompts, agent bodies, and generators behind
the same seams.

Run locally:  cp .env.example .env (optional) → `python -m ui.server`
→ open http://localhost:8000 (fake LLM on by default).
Verify:       `python scripts/check.py`  (purity + full golden path)
Deploy:       see FREE_EDITION_DEPLOY.md

## Verified in this build (offline)
- Tenant-mandatory projects; membership roles; maker override
- Gates as durable rows with side-effects; gates typed as chat commands
- One active run per project (code-enforced; index in sql/ for Lakebase)
- Investigation Loop mechanics: tool calls, jailed workspace tools,
  budgets, investigation log per run (scripted LLM)
- Discuss vs Generate: threads grow, artifacts only on Generate
- ADR-11 bundling: every stage-2 artifact shares one version folder
- Working generators from the MODEL_SPEC contract (STM xlsx, DDL, YAML,
  ERD html, LDDM, construction notebook)
- Checker: parity + grain + privacy rules; GATE/AUDIT verdicts;
  CONFIRM_QA_PASS blocked on open CRITICAL/HIGH; owner waiver ≥10 chars
- Seam error model over HTTP: blocked→422 verbatim, forbidden→403,
  conflict→409; Apps identity header end-to-end

## Pending platform proof (Phase B/C on your Free workspace)
Lakebase branch (auto-credential), UC Volume Files API branch, live
MLflow traces with tool spans, real Claude tool-calling + thinking,
Apps-injected identity, 24h auto-stop → resume durability.
