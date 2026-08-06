"""Engine adapter — schema parity, not engine parity (ADR 4).
DuckDB locally; Lakebase Postgres on Databricks (psycopg, lazy import,
auto-credential via SDK when DM_LAKEBASE_INSTANCE is set).
Rules: '?' placeholders only (converted to %s for pg); NO literal '?'
inside SQL strings; ids and timestamps generated app-side."""
import os, threading, datetime as dt
from core import config

_lock = threading.Lock()
_conn = None
_kind = None

def _connect():
    global _conn, _kind
    url = config.DATABASE_URL
    if os.getenv("PGHOST"):        # injected by an attached DB resource
        _kind = "pg"
        import psycopg
        _conn = psycopg.connect(host=os.environ["PGHOST"],
                                port=int(os.getenv("PGPORT", "5432")),
                                dbname=os.getenv("PGDATABASE", "databricks_postgres"),
                                user=os.getenv("PGUSER"),
                                password=os.getenv("PGPASSWORD"),
                                sslmode=os.getenv("PGSSLMODE", "require"),
                                autocommit=False)
        return _conn
    if config.LAKEBASE_INSTANCE:
        _kind = "pg"
        from databricks.sdk import WorkspaceClient          # platform only
        import psycopg, uuid
        w = WorkspaceClient()
        inst = w.database.get_database_instance(config.LAKEBASE_INSTANCE)
        cred = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[config.LAKEBASE_INSTANCE])
        user = w.current_user.me().user_name
        _conn = psycopg.connect(host=inst.read_write_dns, port=5432,
                                dbname="databricks_postgres", user=user,
                                password=cred.token, sslmode="require",
                                autocommit=False)
    elif url.startswith("postgres"):
        _kind = "pg"
        import psycopg
        _conn = psycopg.connect(url, autocommit=False)
    else:
        _kind = "duck"
        import duckdb
        path = url.replace("duckdb:///", "").replace("duckdb://", "") or ":memory:"
        _conn = duckdb.connect(path)
    return _conn

def _c():
    global _conn
    if _conn is None:
        _connect()
    return _conn

def _sql(q: str) -> str:
    return q.replace("?", "%s") if _kind == "pg" else q

def execute(q: str, params: tuple = ()):  # write
    with _lock:
        c = _c()
        try:
            c.execute(_sql(q), params) if _kind == "duck" else c.cursor().execute(_sql(q), params)
            c.commit()
        except Exception:
            try: c.rollback()
            except Exception: pass
            raise

def query(q: str, params: tuple = ()) -> list[dict]:
    with _lock:
        c = _c()
        if _kind == "duck":
            cur = c.execute(_sql(q), params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        cur = c.cursor()
        cur.execute(_sql(q), params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

class tx:
    """Serialized transaction: execute several statements atomically."""
    def __enter__(self):
        _lock.acquire(); self.c = _c()
        if _kind == "duck":
            try: self.c.execute("BEGIN TRANSACTION")
            except Exception: pass
        return self
    def run(self, q, params=()):
        (self.c.execute(_sql(q), params) if _kind == "duck"
         else self.c.cursor().execute(_sql(q), params))
    def q(self, q, params=()):
        if _kind == "duck":
            cur = self.c.execute(_sql(q), params)
        else:
            cur = self.c.cursor(); cur.execute(_sql(q), params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    def __exit__(self, et, ev, tb):
        try:
            if et:
                try: self.c.rollback()
                except Exception: pass
            else:
                self.c.commit()
        finally:
            _lock.release()
        return False

def now() -> dt.datetime:
    return dt.datetime.utcnow()
