-- Lakebase Postgres — production source of truth. DuckDB mirrors the
-- shape; this file adds what DuckDB cannot enforce.
CREATE SCHEMA IF NOT EXISTS dm;
SET search_path TO dm;
CREATE TABLE IF NOT EXISTS projects(
 project_id text PRIMARY KEY, name text NOT NULL, tenant text NOT NULL,
 custodian text, node_name text, domain text, data_product text,
 dp_type text CHECK (dp_type IN ('SADP','AADP','CADP')),
 target_catalog text, schema_naming text,
 primary_input_type text CHECK (primary_input_type IN ('IDRA','DE_CATALOGUE')),
 map_ids text, status text NOT NULL DEFAULT 'DEVELOPMENT'
   CHECK (status IN ('DEVELOPMENT','RELEASED','DISCARDED')),
 created_by text, created_at timestamptz);
CREATE INDEX IF NOT EXISTS projects_by_tenant ON projects(tenant);
CREATE TABLE IF NOT EXISTS project_members(
 project_id text REFERENCES projects(project_id), principal text,
 principal_type text DEFAULT 'USER', role text NOT NULL
   CHECK (role IN ('OWNER','EDITOR','VIEWER')),
 added_by text, added_at timestamptz,
 PRIMARY KEY(project_id, principal));
CREATE TABLE IF NOT EXISTS source_registry(
 project_id text REFERENCES projects(project_id), source_id text,
 tenant text, feed_status text DEFAULT 'ACTIVE'
   CHECK (feed_status IN ('ACTIVE','DEPRECATED')),
 modelling_profile text CHECK (modelling_profile IN ('A','B','C')),
 stage text DEFAULT 'stage0', qa_status text DEFAULT 'NOT_REQUIRED'
   CHECK (qa_status IN ('NOT_REQUIRED','REQUIRED','PASSED','WAIVED')),
 is_shared_dimension boolean DEFAULT false, depends_on text,
 updated_at timestamptz, PRIMARY KEY(project_id, source_id));
CREATE TABLE IF NOT EXISTS runs(
 run_id text PRIMARY KEY, project_id text NOT NULL
   REFERENCES projects(project_id),
 source_id text, tenant text, task_type text NOT NULL,
 status text DEFAULT 'RUNNING'
   CHECK (status IN ('RUNNING','SUCCEEDED','FAILED')),
 invoked_by text, agent_version text, prompt_versions text, trace_id text,
 tokens_in bigint, tokens_out bigint, started_at timestamptz,
 finished_at timestamptz, error text, output_paths text);
CREATE INDEX IF NOT EXISTS runs_by_project ON runs(project_id, started_at DESC);
-- what DuckDB cannot enforce: ONE active run per project
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run_per_project
  ON runs(project_id) WHERE status = 'RUNNING';
CREATE TABLE IF NOT EXISTS gate_log(
 id text PRIMARY KEY, project_id text NOT NULL REFERENCES projects(project_id),
 source_id text, tenant text, gate_name text NOT NULL,
 decision text DEFAULT 'CONFIRMED', decided_by text, decided_at timestamptz,
 comment text);
CREATE TABLE IF NOT EXISTS deliverable_versions(
 id text PRIMARY KEY, project_id text, source_id text, tenant text,
 stage text, artifact_type text, version int, volume_path text,
 created_by text, created_at timestamptz);
CREATE TABLE IF NOT EXISTS defects(
 id text PRIMARY KEY, project_id text, source_id text, tenant text,
 qa_run_id text, severity text
   CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW')),
 artifact text, description text, status text DEFAULT 'OPEN'
   CHECK (status IN ('OPEN','FIXED','WAIVED')),
 waiver_reason text, created_at timestamptz, resolved_at timestamptz);
CREATE TABLE IF NOT EXISTS unknowns(
 id text PRIMARY KEY, project_id text, source_id text, tenant text,
 question text, owner text, status text DEFAULT 'OPEN', resolution text,
 created_at timestamptz);
CREATE TABLE IF NOT EXISTS messages(
 id text PRIMARY KEY, project_id text, source_id text, tenant text,
 thread_key text, role text, run_id text, content text, created_by text,
 created_at timestamptz);
CREATE INDEX IF NOT EXISTS messages_by_thread
  ON messages(project_id, thread_key, created_at);
CREATE TABLE IF NOT EXISTS feature_requests(
 id text PRIMARY KEY, requested_by text, title text, detail text,
 status text DEFAULT 'NEW', created_at timestamptz);
