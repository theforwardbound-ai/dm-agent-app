# Phase B — Deploy to Databricks Free Edition (~40 min of clicks)

Rule in force: SYNTHETIC CONTENT ONLY on personal infrastructure.

## B0. Push this package to your personal GitHub (on this machine)
    cd dm-agent-app
    git init && git add -A && git commit -m "dm-agent free edition build"
    git branch -M main
    git remote add origin https://github.com/<you>/dm-agent-app.git
    git push -u origin main

## B1. Probe #1 — which models exist (2 min)
Workspace → **Playground**: note the exact model names in the picker
(e.g. a Claude, Llama, or GPT-OSS entry). Pick the strongest with tool
support; that string becomes DM_MODEL_FRONTIER.

## B2. Catalog objects (3 min) — SQL editor, default warehouse
    CREATE SCHEMA IF NOT EXISTS workspace.dm_agent;
    CREATE VOLUME IF NOT EXISTS workspace.dm_agent.files;

## B3. Lakebase (5 min)
Compute → **Database instances** (Lakebase) → Create → name `dm-agent-db`
(smallest size). When running, open its **SQL editor** (or any Postgres
client with the shown connection) and paste `sql/lakebase_schema.sql`.
Confirm `one_active_run_per_project` index exists.

## B4. Git folder (2 min)
Workspace → Repos/Git folders → Add → your repo URL → main.

## B5. Create the App (10 min)
Compute → **Apps** → Create app → Custom → source = the Git folder root.
Resources: **add the Lakebase database instance** (grants the app
service principal access). App → Environment:

| variable | value |
|---|---|
| DM_LAKEBASE_INSTANCE | dm-agent-db |
| DM_FILES_VOLUME | /Volumes/workspace/dm_agent/files |
| DM_FAKE_LLM | 1  (first boot; flip to 0 after B7) |
| DM_MODEL_FRONTIER | <from B1> |
| DM_MAKER_EMAILS | <your login email> |
| MLFLOW_EXPERIMENT | /Users/<your email>/dm-agent-free |
| DM_TRACING | 1 |

Deploy. Open the app URL → `/healthz` should show `"ok": true`.
If db shows an error: instance name typo, instance stopped, or the
Lakebase resource wasn't attached.

## B6. Volume + identity check (5 min)
In the app UI: your login email should appear as acting user
automatically (Apps injects X-Forwarded-Email — the box is only a
fallback). Create a demo project (tenant e.g. `demo-team`), register
source `RCB`. In Catalog → workspace.dm_agent.files you should now see
`p_<id>/input/...` folders — that is the Files API branch working.
Upload `scripts/make_synthetic_idra.py`'s output (run it locally,
upload RCB_IDRA.xlsx via Catalog Explorer into
p_<id>/input/idra/, or use the app once an upload affordance is added).

## B7. First real model call (10 min)
Set DM_FAKE_LLM=0 → redeploy → in the app, task
`/stage0-data-product-planning`, message "plan the product", Generate.
- 403 from serving → Serving → your model endpoint → Permissions →
  grant the app's service principal **Can Query** → retry.
- Success → check tracking/agent-log/ in the tree (the model's tool
  calls) and Experiments → dm-agent-free (the trace with tool spans).
Then optional: DM_THINKING_BUDGET=4096; if runs 400, remove it.

## Phase C — the synthetic cycle (exit criteria)
1. Gates by typing: CONFIRM_DATA_PRODUCT_PLAN → parse → 
   CONFIRM_INPUT_PARSED → Discuss twice (no new versions) → Generate
   stage 1 → CONFIRM_STAGE1_FINAL → Generate stage 2 →
   CONFIRM_STAGE2_FINAL (QA chip goes REQUIRED).
2. Next model task blocks with the verbatim QA-pending message.
3. QA tile → Run checker: verdict + defects; fix or waive; QA PASSED
   or WAIVED; walkthrough task now runs.
4. Artifacts visible + downloadable from the tree (STM/DDL/YAML/ERD/
   notebook, all same v{n}).
5. Leave it 24h → app auto-stops → Start it → everything resumes
   (Lakebase + volume survived; the transitory-agent principle proven).
Record any deviation with its step number.
