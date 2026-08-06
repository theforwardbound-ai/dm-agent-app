"""Durable Project state. The agent is transitory; THIS persists.
All ids uuid-hex app-side; timestamps UTC app-side; tenant denormalized
onto every child row (ADR 7); one bundled version per (source, stage)
generate-run (ADR 11)."""
import uuid, json
from core import db, config

def _id(): return uuid.uuid4().hex

DDL = [
"""CREATE TABLE IF NOT EXISTS projects(
 project_id TEXT PRIMARY KEY, name TEXT NOT NULL, tenant TEXT NOT NULL,
 custodian TEXT, node_name TEXT, domain TEXT, data_product TEXT,
 dp_type TEXT, target_catalog TEXT, schema_naming TEXT,
 primary_input_type TEXT, map_ids TEXT,
 status TEXT NOT NULL DEFAULT 'DEVELOPMENT',
 created_by TEXT, created_at TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS project_members(
 project_id TEXT, principal TEXT, principal_type TEXT DEFAULT 'USER',
 role TEXT NOT NULL, added_by TEXT, added_at TIMESTAMP,
 PRIMARY KEY(project_id, principal))""",
"""CREATE TABLE IF NOT EXISTS source_registry(
 project_id TEXT, source_id TEXT, tenant TEXT,
 feed_status TEXT DEFAULT 'ACTIVE', modelling_profile TEXT,
 stage TEXT DEFAULT 'stage0', qa_status TEXT DEFAULT 'NOT_REQUIRED',
 is_shared_dimension BOOLEAN DEFAULT FALSE, depends_on TEXT,
 updated_at TIMESTAMP, PRIMARY KEY(project_id, source_id))""",
"""CREATE TABLE IF NOT EXISTS runs(
 run_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_id TEXT,
 tenant TEXT, task_type TEXT NOT NULL, status TEXT DEFAULT 'RUNNING',
 invoked_by TEXT, agent_version TEXT, prompt_versions TEXT,
 trace_id TEXT, tokens_in INTEGER, tokens_out INTEGER,
 started_at TIMESTAMP, finished_at TIMESTAMP, error TEXT,
 output_paths TEXT)""",
"""CREATE TABLE IF NOT EXISTS gate_log(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_id TEXT,
 tenant TEXT, gate_name TEXT NOT NULL, decision TEXT DEFAULT 'CONFIRMED',
 decided_by TEXT, decided_at TIMESTAMP, comment TEXT)""",
"""CREATE TABLE IF NOT EXISTS deliverable_versions(
 id TEXT PRIMARY KEY, project_id TEXT, source_id TEXT, tenant TEXT,
 stage TEXT, artifact_type TEXT, version INTEGER, volume_path TEXT,
 created_by TEXT, created_at TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS defects(
 id TEXT PRIMARY KEY, project_id TEXT, source_id TEXT, tenant TEXT,
 qa_run_id TEXT, severity TEXT, artifact TEXT, description TEXT,
 status TEXT DEFAULT 'OPEN', waiver_reason TEXT,
 created_at TIMESTAMP, resolved_at TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS unknowns(
 id TEXT PRIMARY KEY, project_id TEXT, source_id TEXT, tenant TEXT,
 question TEXT, owner TEXT, status TEXT DEFAULT 'OPEN',
 resolution TEXT, created_at TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS messages(
 id TEXT PRIMARY KEY, project_id TEXT, source_id TEXT, tenant TEXT,
 thread_key TEXT, role TEXT, run_id TEXT, content TEXT,
 created_by TEXT, created_at TIMESTAMP)""",
"""CREATE TABLE IF NOT EXISTS feature_requests(
 id TEXT PRIMARY KEY, requested_by TEXT, title TEXT, detail TEXT,
 status TEXT DEFAULT 'NEW', created_at TIMESTAMP)""",
]

def init_db():
    for stmt in DDL:
        db.execute(stmt)

class Forbidden(Exception): pass
class Conflict(Exception): pass
class NotFound(Exception): pass

ROLE_RANK = {"VIEWER": 0, "EDITOR": 1, "OWNER": 2}

# ---------- projects & membership ----------
def create_project(payload: dict, user: str) -> dict:
    if not payload.get("tenant"):
        raise Conflict("tenant (application team) is required — a product "
                       "belongs to exactly one tenant")
    pid = _id()
    db.execute(
        "INSERT INTO projects(project_id,name,tenant,custodian,node_name,"
        "domain,data_product,dp_type,target_catalog,schema_naming,"
        "primary_input_type,map_ids,status,created_by,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, payload.get("name"), payload["tenant"], payload.get("custodian"),
         payload.get("node_name"), payload.get("domain"),
         payload.get("data_product"), payload.get("dp_type"),
         payload.get("target_catalog"), payload.get("schema_naming"),
         payload.get("primary_input_type"),
         json.dumps(payload.get("map_ids") or {}), "DEVELOPMENT",
         user, db.now()))
    db.execute("INSERT INTO project_members(project_id,principal,principal_type,"
               "role,added_by,added_at) VALUES(?,?,?,?,?,?)",
               (pid, user, "USER", "OWNER", user, db.now()))
    return get_project(pid)

def get_project(pid: str) -> dict:
    r = db.query("SELECT * FROM projects WHERE project_id=?", (pid,))
    if not r: raise NotFound(f"project {pid}")
    return r[0]

def project_tenant(pid: str) -> str:
    return get_project(pid)["tenant"]

def active_project(user: str) -> dict | None:
    """Minimal-UI rule: pinned via env, else most recent the user can see."""
    if config.ACTIVE_PROJECT:
        try: return get_project(config.ACTIVE_PROJECT)
        except NotFound: pass
    rows = db.query(
        "SELECT p.* FROM projects p JOIN project_members m "
        "ON p.project_id=m.project_id WHERE lower(m.principal)=? "
        "ORDER BY p.created_at DESC", (user.lower(),))
    return rows[0] if rows else None

def list_projects_for(user: str, tenant: str | None = None) -> list[dict]:
    q = ("SELECT p.* FROM projects p JOIN project_members m "
         "ON p.project_id=m.project_id WHERE lower(m.principal)=?")
    params: list = [user.lower()]
    if tenant:
        q += " AND p.tenant=?"; params.append(tenant)
    return db.query(q + " ORDER BY p.created_at DESC", tuple(params))

def member_role(pid: str, user: str) -> str | None:
    if user.lower() in config.MAKER_EMAILS:
        return "OWNER"
    r = db.query("SELECT role FROM project_members WHERE project_id=? "
                 "AND lower(principal)=?", (pid, user.lower()))
    return r[0]["role"] if r else None

def require_member(pid: str, user: str, min_role: str = "VIEWER") -> str:
    role = member_role(pid, user)
    if role is None or ROLE_RANK[role] < ROLE_RANK[min_role]:
        raise Forbidden(f"{user} lacks {min_role} on project {pid}")
    return role

def add_member(pid, principal, role, user):
    require_member(pid, user, "OWNER")
    db.execute("INSERT INTO project_members(project_id,principal,principal_type,"
               "role,added_by,added_at) VALUES(?,?,?,?,?,?)",
               (pid, principal, "USER", role, user, db.now()))

def list_members(pid):
    return db.query("SELECT * FROM project_members WHERE project_id=?", (pid,))

# ---------- sources ----------
def upsert_source(pid, source_id, **vals):
    tenant = project_tenant(pid)
    cur = db.query("SELECT * FROM source_registry WHERE project_id=? AND "
                   "source_id=?", (pid, source_id))
    if cur:
        sets, params = [], []
        for k, v in vals.items():
            sets.append(f"{k}=?")
            params.append(json.dumps(v) if k == "depends_on" and
                          not isinstance(v, str) else v)
        sets.append("updated_at=?"); params.append(db.now())
        params += [pid, source_id]
        db.execute(f"UPDATE source_registry SET {', '.join(sets)} "
                   "WHERE project_id=? AND source_id=?", tuple(params))
    else:
        db.execute("INSERT INTO source_registry(project_id,source_id,tenant,"
                   "feed_status,modelling_profile,stage,qa_status,"
                   "is_shared_dimension,depends_on,updated_at) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (pid, source_id, tenant, vals.get("feed_status", "ACTIVE"),
                    vals.get("modelling_profile"), vals.get("stage", "stage0"),
                    vals.get("qa_status", "NOT_REQUIRED"),
                    vals.get("is_shared_dimension", False),
                    json.dumps(vals.get("depends_on") or []), db.now()))

def sources(pid):
    return db.query("SELECT * FROM source_registry WHERE project_id=? "
                    "ORDER BY source_id", (pid,))

def source(pid, source_id):
    r = db.query("SELECT * FROM source_registry WHERE project_id=? AND "
                 "source_id=?", (pid, source_id))
    return r[0] if r else None

# ---------- gates ----------
STAGE_FX = {"CONFIRM_INPUT_PARSED": "parsed",
            "CONFIRM_STAGE1_FINAL": "stage1_confirmed",
            "CONFIRM_AADP_STAGE1_FINAL": "stage1_confirmed",
            "CONFIRM_STAGE2_FINAL": "stage2_confirmed",
            "CONFIRM_AADP_STAGE2_FINAL": "stage2_confirmed",
            "CONFIRM_CADP_STAGE2_FINAL": "stage2_confirmed"}
QA_TRIGGERS = {"CONFIRM_STAGE2_FINAL", "CONFIRM_AADP_STAGE2_FINAL",
               "CONFIRM_CADP_STAGE2_FINAL"}

def add_gate(pid, gate_name, user, source_id=None, decision="CONFIRMED",
             comment=None):
    tenant = project_tenant(pid)
    db.execute("INSERT INTO gate_log(id,project_id,source_id,tenant,gate_name,"
               "decision,decided_by,decided_at,comment) VALUES(?,?,?,?,?,?,?,?,?)",
               (_id(), pid, source_id, tenant, gate_name, decision, user,
                db.now(), comment))
    if decision != "CONFIRMED" or not source_id:
        return
    vals = {}
    if gate_name in STAGE_FX:
        vals["stage"] = STAGE_FX[gate_name]
    if gate_name in QA_TRIGGERS:
        vals["qa_status"] = "REQUIRED"      # handoff: modeler now locked
    if vals:
        upsert_source(pid, source_id, **vals)

def confirmed_gates(pid, source_id=None) -> set[str]:
    if source_id:
        rows = db.query("SELECT gate_name FROM gate_log WHERE project_id=? "
                        "AND decision='CONFIRMED' AND (source_id=? OR "
                        "source_id IS NULL)", (pid, source_id))
    else:
        rows = db.query("SELECT gate_name FROM gate_log WHERE project_id=? "
                        "AND decision='CONFIRMED'", (pid,))
    return {r["gate_name"] for r in rows}

def list_gate_log(pid, source_id=None):
    return db.query("SELECT * FROM gate_log WHERE project_id=? "
                    "ORDER BY decided_at DESC", (pid,))

def set_qa(pid, source_id, status):
    upsert_source(pid, source_id, qa_status=status)

# ---------- runs (one active per project) ----------
def claim_run(pid, task_type, user, source_id=None) -> str:
    rid = _id()
    tenant = project_tenant(pid)
    with db.tx() as t:
        active = t.q("SELECT run_id FROM runs WHERE project_id=? AND "
                     "status='RUNNING'", (pid,))
        if active:
            raise Conflict(f"run {active[0]['run_id'][:8]} is already active "
                           "on this project — one active run per project")
        t.run("INSERT INTO runs(run_id,project_id,source_id,tenant,task_type,"
              "status,invoked_by,agent_version,started_at) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              (rid, pid, source_id, tenant, task_type, "RUNNING", user,
               config.AGENT_VERSION, db.now()))
    return rid

def finish_run(rid, status, output_paths=None, error=None, trace_id=None,
               tokens_in=None, tokens_out=None, prompt_versions=None):
    db.execute("UPDATE runs SET status=?, finished_at=?, error=?, "
               "output_paths=?, trace_id=?, tokens_in=?, tokens_out=?, "
               "prompt_versions=? WHERE run_id=?",
               (status, db.now(), error,
                json.dumps(output_paths or []), trace_id, tokens_in,
                tokens_out, json.dumps(prompt_versions or {}), rid))

def list_runs(pid, limit=50):
    return db.query("SELECT * FROM runs WHERE project_id=? "
                    "ORDER BY started_at DESC LIMIT ?", (pid, limit))

# ---------- versions (ADR 11: bundled per source+stage) ----------
def next_stage_version(pid, source_id, stage) -> int:
    r = db.query("SELECT MAX(version) AS v FROM deliverable_versions WHERE "
                 "project_id=? AND source_id=? AND stage=?",
                 (pid, source_id, stage))
    return (r[0]["v"] or 0) + 1

def add_deliverable(pid, source_id, stage, artifact_type, version,
                    volume_path, user):
    db.execute("INSERT INTO deliverable_versions(id,project_id,source_id,"
               "tenant,stage,artifact_type,version,volume_path,created_by,"
               "created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (_id(), pid, source_id, project_tenant(pid), stage,
                artifact_type, version, volume_path, user, db.now()))

def list_deliverables(pid, source_id=None):
    if source_id:
        return db.query("SELECT * FROM deliverable_versions WHERE project_id=?"
                        " AND source_id=? ORDER BY created_at DESC",
                        (pid, source_id))
    return db.query("SELECT * FROM deliverable_versions WHERE project_id=? "
                    "ORDER BY created_at DESC", (pid,))

# ---------- defects / unknowns / messages / features ----------
def add_defect(pid, source_id, qa_run_id, severity, artifact, description):
    db.execute("INSERT INTO defects(id,project_id,source_id,tenant,qa_run_id,"
               "severity,artifact,description,status,created_at) "
               "VALUES(?,?,?,?,?,?,?,?,?,?)",
               (_id(), pid, source_id, project_tenant(pid), qa_run_id,
                severity, artifact, description, "OPEN", db.now()))

def list_defects(pid, source_id=None, status=None):
    q = "SELECT * FROM defects WHERE project_id=?"
    p: list = [pid]
    if source_id: q += " AND source_id=?"; p.append(source_id)
    if status: q += " AND status=?"; p.append(status)
    return db.query(q + " ORDER BY created_at DESC", tuple(p))

def waive_defects(pid, source_id, reason):
    db.execute("UPDATE defects SET status='WAIVED', waiver_reason=?, "
               "resolved_at=? WHERE project_id=? AND source_id=? AND "
               "status='OPEN'", (reason, db.now(), pid, source_id))

def supersede_open_defects(pid, source_id):
    db.execute("UPDATE defects SET status='FIXED', resolved_at=? "
               "WHERE project_id=? AND source_id=? AND status='OPEN'",
               (db.now(), pid, source_id))

def record_unknown(pid, source_id, question, owner=None):
    db.execute("INSERT INTO unknowns(id,project_id,source_id,tenant,question,"
               "owner,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
               (_id(), pid, source_id, project_tenant(pid), question, owner,
                "OPEN", db.now()))

def list_unknowns(pid, source_id=None, status=None):
    q = "SELECT * FROM unknowns WHERE project_id=?"
    p: list = [pid]
    if source_id: q += " AND source_id=?"; p.append(source_id)
    if status: q += " AND status=?"; p.append(status)
    return db.query(q + " ORDER BY created_at DESC", tuple(p))

def add_message(pid, thread_key, role, content, user, source_id=None,
                run_id=None):
    db.execute("INSERT INTO messages(id,project_id,source_id,tenant,"
               "thread_key,role,run_id,content,created_by,created_at) "
               "VALUES(?,?,?,?,?,?,?,?,?,?)",
               (_id(), pid, source_id, project_tenant(pid), thread_key, role,
                run_id, content, user, db.now()))

def list_messages(pid, thread_key=None, source_id=None, limit=50):
    q = "SELECT * FROM messages WHERE project_id=?"
    p: list = [pid]
    if thread_key: q += " AND thread_key=?"; p.append(thread_key)
    if source_id: q += " AND source_id=?"; p.append(source_id)
    rows = db.query(q + " ORDER BY created_at DESC LIMIT ?", tuple(p + [limit]))
    return list(reversed(rows))

def add_feature_request(user, title, detail):
    db.execute("INSERT INTO feature_requests(id,requested_by,title,detail,"
               "status,created_at) VALUES(?,?,?,?,?,?)",
               (_id(), user, title, detail, "NEW", db.now()))
