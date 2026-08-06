"""ProjectWorkspace — the only path authority. Local-disk branch for dev;
Unity Catalog Volume branch (Files API via databricks-sdk) on platform.
The volume branch is REAL in this build — Phase B proves it."""
import io, pathlib, posixpath
from core import config

SKELETON = ["input/idra", "input/de-catalogue", "input/stm",
            "input/source-code", "input/reference/brd", "input/reference/srd",
            "input/reference/policies", "input/reference/other",
            "output/stage0", "output/stage1", "output/stage2",
            "qa", "tracking/idra-extractions", "tracking/agent-log"]

def _safe(rel: str) -> str:
    rel = (rel or "").strip("/")
    p = posixpath.normpath(rel)
    if p.startswith("..") or p.startswith("/"):
        raise ValueError(f"unsafe path '{rel}'")
    return "" if p == "." else p

class ProjectWorkspace:
    def __init__(self, project_id: str):
        self.pid = project_id
        self.local = config.LOCAL_FS_ROOT
        self.root = (f"{self.local}/p_{project_id}" if self.local
                     else f"{config.FILES_VOLUME}/p_{project_id}")
        self._w = None

    def _sdk(self):
        if self._w is None:
            from databricks.sdk import WorkspaceClient
            self._w = WorkspaceClient()
        return self._w

    def path(self, rel: str = "") -> str:
        rel = _safe(rel)
        return f"{self.root}/{rel}" if rel else self.root

    def ensure_skeleton(self):
        if self.local:
            for d in SKELETON:
                pathlib.Path(self.path(d)).mkdir(parents=True, exist_ok=True)
        else:
            w = self._sdk()
            for d in SKELETON:
                w.files.create_directory(self.path(d))

    def upload(self, rel: str, data: bytes) -> str:
        p = self.path(rel)
        if self.local:
            fp = pathlib.Path(p); fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(data)
        else:
            w = self._sdk()
            try:
                w.files.create_directory(p.rsplit("/", 1)[0])
            except Exception:
                pass
            w.files.upload(p, io.BytesIO(data), overwrite=True)
        return p

    def download(self, rel: str) -> bytes:
        p = self.path(rel)
        if self.local:
            return pathlib.Path(p).read_bytes()
        return self._sdk().files.download(p).contents.read()

    def exists(self, rel: str) -> bool:
        try:
            self.download(rel); return True
        except Exception:
            return False

    def listdir(self, rel: str = "") -> list[dict]:
        """Recursive: [{path, size}] relative to project root."""
        base = self.path(rel)
        out: list[dict] = []
        if self.local:
            b = pathlib.Path(base)
            if not b.exists(): return out
            for x in sorted(b.rglob("*")):
                if x.is_file():
                    out.append({"path": str(x.relative_to(self.root)).replace("\\", "/"),
                                "size": x.stat().st_size})
            return out
        w = self._sdk()
        def walk(d):
            try:
                for e in w.files.list_directory_contents(d):
                    if getattr(e, "is_directory", False):
                        walk(e.path)
                    else:
                        out.append({"path": e.path[len(self.root) + 1:],
                                    "size": getattr(e, "file_size", 0) or 0})
            except Exception:
                pass
        walk(base)
        return sorted(out, key=lambda x: x["path"])

def asset(rel: str) -> bytes:
    """Maker assets (templates). Generic build ships none; office merge
    points this at the real templates volume/folder."""
    base = pathlib.Path(config.PROMPT_DIR).parent / "templates"
    return (base / rel).read_bytes()
