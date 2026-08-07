"""Stdlib HTTP server: static shell + JSON routes onto the seam.
Binds DATABRICKS_APP_PORT on the platform, DM_SERVER_PORT locally.
Identity: X-Forwarded-Email (Apps-injected) else DM_DEV_USER."""
import io, json, mimetypes, pathlib, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from core import config, state, worker
from ui.backend import LocalBackend, UiError, resolve_user

STATIC = pathlib.Path(__file__).parent / "static"
STATUS = {"blocked": 422, "forbidden": 403, "conflict": 409, "notfound": 404}

class H(BaseHTTPRequestHandler):
    server_version = "dm-agent"

    def _hdrs(self):
        return {k.lower(): v for k, v in self.headers.items()}

    def _json(self, code: int, obj):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, data: bytes, ctype: str, download: str | None = None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if download:
            self.send_header("Content-Disposition",
                             f'attachment; filename="{download}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _backend(self) -> LocalBackend:
        return LocalBackend(resolve_user(self._hdrs()))

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode() or "{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if u.path == "/healthz":
                db_ok = True
                try:
                    state.init_db()
                except Exception as e:
                    db_ok = str(e)
                return self._json(200, {"ok": db_ok is True, "db": db_ok,
                                        "version": config.AGENT_VERSION})
            if u.path == "/api/status":
                return self._json(200, self._backend().status_bundle())
            if u.path == "/api/tree":
                return self._json(200, self._backend().tree())
            if u.path == "/api/thread":
                return self._json(200, self._backend().thread(
                    q.get("source") or None, q.get("stage", "stage0")))
            if u.path == "/api/defects":
                return self._json(200, self._backend().defects(
                    q.get("source") or None))
            if u.path == "/api/run":
                return self._json(200, self._backend().run_status(q["id"]))
            if u.path == "/api/run/events":
                return self._json(200, self._backend().run_events(
                    q["id"], since=int(q.get("since") or 0),
                    limit=int(q.get("limit") or 500)))
            if u.path == "/api/file":
                rel = q.get("path", "")
                data = self._backend().file_bytes(rel)
                name = rel.split("/")[-1]
                if q.get("download") == "1":
                    return self._bytes(data, "application/octet-stream", name)
                ctype = mimetypes.guess_type(name)[0] or "text/plain"
                if name.endswith((".md", ".sql", ".yaml", ".yml", ".py",
                                  ".txt", ".json")):
                    ctype = "text/plain; charset=utf-8"
                return self._bytes(data, ctype)
            # static
            rel = u.path.lstrip("/") or "index.html"
            f = (STATIC / rel).resolve()
            if STATIC.resolve() in f.parents or f == STATIC.resolve():
                if f.is_file():
                    return self._bytes(f.read_bytes(),
                                       mimetypes.guess_type(f.name)[0]
                                       or "text/plain")
            return self._json(404, {"error": "not found"})
        except UiError as e:
            return self._json(STATUS.get(e.kind, 400),
                              {"error": str(e), "kind": e.kind})
        except Exception as e:
            return self._json(500, {"error": str(e)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            b = self._backend()
            body = self._body()
            if u.path == "/api/project":
                return self._json(200, b.create_project(body))
            if u.path == "/api/source":
                return self._json(200, b.register_source(
                    body.pop("project_id", None) or
                    state.active_project(b.user)["project_id"], body))
            if u.path == "/api/upload":
                p = b.upload_b64(body.get("folder", "input/idra"),
                                 body["filename"], body["b64"])
                return self._json(200, {"stored": p})
            if u.path == "/api/send":
                # wait=False: claim the run, hand it to the worker, return at
                # once. The client tails /api/run/events from here. A gate
                # command settles inline and stays 200.
                r = b.send(body.get("source") or None, body.get("task", ""),
                           body.get("message", ""), bool(body.get("chat")),
                           wait=False)
                return self._json(202 if r.get("kind") == "run" else 200, r)
            if u.path == "/api/run/cancel":
                return self._json(200, b.cancel_run(body["id"]))
            if u.path == "/api/qa":
                return self._json(200, b.qa_run(body.get("mode", "GATE"),
                                                body.get("source") or None,
                                                body.get("artifact") or None))
            if u.path == "/api/qa/pass":
                return self._json(200, b.qa_pass(body["source"]))
            if u.path == "/api/qa/waive":
                return self._json(200, b.qa_waive(body["source"],
                                                  body.get("reason", "")))
            return self._json(404, {"error": "not found"})
        except UiError as e:
            return self._json(STATUS.get(e.kind, 400),
                              {"error": str(e), "kind": e.kind})
        except KeyError as e:
            return self._json(400, {"error": f"missing field {e}"})
        except Exception as e:
            return self._json(500, {"error": str(e)})

    def log_message(self, *a):
        pass

def main():
    dbk = ("lakebase" if config.LAKEBASE_INSTANCE else
           "postgres" if config.DATABASE_URL.startswith("postgres") else "duckdb")
    print(f"boot: port={config.SERVER_PORT} db={dbk} "
          f"volume={'set' if not config.LOCAL_FS_ROOT else 'local-fs'} "
          f"fake_llm={config.FAKE_LLM}", flush=True)
    try:
        state.init_db()
        print("db init: OK", flush=True)
    except Exception as e:
        print(f"db init FAILED (serving anyway; /healthz reports): {e}",
              flush=True)
    # Starts the run workers and requeues anything a previous process left
    # QUEUED or RUNNING. Safe after a failed init: it only reads on demand.
    worker.start()
    srv = ThreadingHTTPServer(("0.0.0.0", config.SERVER_PORT), H)
    print(f"dm-agent listening on 0.0.0.0:{config.SERVER_PORT} "
          f"(version {config.AGENT_VERSION}, "
          f"{config.WORKER_THREADS} worker thread(s))", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
