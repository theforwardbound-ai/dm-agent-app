"""Generic, WORKING generators for the Free Edition cycle (ADR 12).
Contract: the stage-2 prompt instructs the model to end its deliverable
with a fenced json block tagged MODEL_SPEC:

```json MODEL_SPEC
{"grain": {"<table>": "One row per ..."},
 "tables": [{"name": "...", "columns": [
    {"name": "...", "type": "STRING|INT|DECIMAL(18,2)|DATE|TIMESTAMP|BOOLEAN",
     "nullable": true, "pk": false, "privacy": "PUBLIC|INTERNAL|CONFIDENTIAL",
     "source_field": "..."}]}]}
```

Generators consume that spec deterministically. The bank's real
generators replace these at office-merge time behind the same
signatures (markdown+context in, bytes out)."""
import io, json, re

class SpecMissing(Exception):
    pass

_SPEC_RX = re.compile(r"```json\s+MODEL_SPEC\s*(\{.*?\})\s*```", re.S)

def extract_spec(stage2_md: str) -> dict:
    m = _SPEC_RX.search(stage2_md or "")
    if not m:
        raise SpecMissing("no MODEL_SPEC block in stage-2 output")
    try:
        spec = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise SpecMissing(f"MODEL_SPEC not valid JSON: {e}")
    if not spec.get("tables"):
        raise SpecMissing("MODEL_SPEC has no tables")
    return spec

def _qualify(project: dict) -> tuple[str, str]:
    cat = project.get("target_catalog") or "{catalog}"
    sch = project.get("schema_naming") or "{schema}"
    return cat, sch

def generate_ddl(stage2_md: str, project: dict, source_id: str) -> bytes:
    spec = extract_spec(stage2_md)
    cat, sch = _qualify(project)
    out = [f"-- Generated DDL — source {source_id} — dev environments only"]
    for t in spec["tables"]:
        pks = [c["name"] for c in t["columns"] if c.get("pk")]
        cols = []
        for c in t["columns"]:
            null = "" if c.get("nullable", True) else " NOT NULL"
            priv = c.get("privacy", "INTERNAL")
            cols.append(f"  {c['name']} {c.get('type','STRING')}{null} "
                        f"COMMENT 'privacy={priv}'")
        if pks:
            cols.append(f"  CONSTRAINT pk_{t['name']} PRIMARY KEY "
                        f"({', '.join(pks)})")
        grain = (spec.get("grain") or {}).get(t["name"], "")
        out.append(
            f"CREATE TABLE IF NOT EXISTS `{cat}`.`{sch}`.`{t['name']}` (\n"
            + ",\n".join(cols)
            + f"\n) COMMENT 'grain: {grain}';")
    return "\n\n".join(out).encode("utf-8")

def generate_yaml(stage2_md: str, project: dict, source_id: str) -> bytes:
    import yaml
    spec = extract_spec(stage2_md)
    cat, sch = _qualify(project)
    doc = {"contract_version": 1, "source_system": source_id,
           "target": {"catalog": cat, "schema": sch},
           "tables": [{"target_table": t["name"],
                       "grain": (spec.get("grain") or {}).get(t["name"], ""),
                       "columns": [{"target_column": c["name"],
                                    "type": c.get("type", "STRING"),
                                    "nullable": c.get("nullable", True),
                                    "privacy": c.get("privacy", "INTERNAL"),
                                    "source_field": c.get("source_field", "")}
                                   for c in t["columns"]]}
                      for t in spec["tables"]]}
    return yaml.safe_dump(doc, sort_keys=False).encode("utf-8")

def generate_stm_xlsx(stage2_md: str, project: dict, source_id: str) -> bytes:
    from openpyxl import Workbook
    spec = extract_spec(stage2_md)
    wb = Workbook(); wb.remove(wb.active)
    hdr = ["Source System", "Source Field", "Target Table", "Target Column",
           "Type", "Nullable", "Privacy", "Transformation"]
    for t in spec["tables"]:
        sh = wb.create_sheet(title=t["name"][:31])
        sh.append(hdr)
        for c in t["columns"]:
            sh.append([source_id, c.get("source_field", ""), t["name"],
                       c["name"], c.get("type", "STRING"),
                       "Y" if c.get("nullable", True) else "N",
                       c.get("privacy", "INTERNAL"), "direct"])
        g = (spec.get("grain") or {}).get(t["name"], "")
        sh.append([]); sh.append(["Grain", g])
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()

def generate_erd_html(stage2_md: str, project: dict, source_id: str) -> bytes:
    spec = extract_spec(stage2_md)
    ents = []
    for t in spec["tables"]:
        rows = "".join(
            f"<tr><td>{'* ' if c.get('pk') else ''}{c['name']}</td>"
            f"<td>{c.get('type','STRING')}</td></tr>"
            for c in t["columns"])
        grain = (spec.get("grain") or {}).get(t["name"], "")
        ents.append(f"<div class='e'><h3>{t['name']}</h3>"
                    f"<p class='g'>{grain}</p><table>{rows}</table></div>")
    html = ("<!doctype html><meta charset='utf-8'><title>Target ERD — "
            + source_id + "</title><style>body{font:14px system-ui;"
            "background:#1e1e1e;color:#ddd;padding:20px}"
            ".e{display:inline-block;vertical-align:top;background:#252526;"
            "border:1px solid #3c3c3c;border-radius:8px;margin:10px;"
            "padding:12px;min-width:220px}h3{margin:0 0 4px;color:#4ec9b0}"
            ".g{color:#888;font-size:12px;margin:0 0 8px}table{border-"
            "collapse:collapse;width:100%}td{border-top:1px solid #333;"
            "padding:3px 6px;font-family:ui-monospace,monospace;font-size:"
            "12.5px}</style><h1>Target ERD (self-contained)</h1>"
            + "".join(ents))
    return html.encode("utf-8")

def generate_lddm_md(stage2_md: str, project: dict, source_id: str) -> bytes:
    spec = extract_spec(stage2_md)
    lines = [f"# LDDM Registration Checklist — {source_id}", ""]
    for t in spec["tables"]:
        lines.append(f"- [ ] Register {t['name']} "
                     f"({len(t['columns'])} columns; grain: "
                     f"{(spec.get('grain') or {}).get(t['name'], 'n/a')})")
    return "\n".join(lines).encode("utf-8")

def generate_construction_notebook(stage2_md, project, source_id) -> bytes:
    try:
        ddl = generate_ddl(stage2_md, project, source_id).decode()
    except SpecMissing:
        ddl = "-- MODEL_SPEC missing; DDL not generated"
    stmts = [s.strip() + ";" for s in ddl.split(";") if "CREATE TABLE" in s]
    body = json.dumps(stmts, indent=1)
    nb = (
        "# Databricks notebook source\n"
        f"# Construction Notebook — {project.get('data_product')} / {source_id}\n"
        "# Modelling happens in LOWER ENVIRONMENTS ONLY; production receives\n"
        "# artifacts through the release pipeline, never through this agent.\n"
        f'dbutils.widgets.text("target_catalog", "{project.get("target_catalog") or ""}")\n'
        f'dbutils.widgets.text("target_schema", "{project.get("schema_naming") or ""}")\n'
        'dbutils.widgets.dropdown("dry_run", "true", ["true", "false"])\n\n'
        "# COMMAND ----------\n"
        'catalog = dbutils.widgets.get("target_catalog")\n'
        'schema  = dbutils.widgets.get("target_schema")\n'
        'dry     = dbutils.widgets.get("dry_run") == "true"\n'
        'spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")\n'
        f"DDL = {body}\n"
        "for s in DDL:\n"
        "    print(('DRY: ' if dry else 'RUN: ') + s.splitlines()[0][:120])\n"
        "    if not dry:\n"
        "        spark.sql(s)\n\n"
        "# COMMAND ----------\n"
        'display(spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema}`"))\n')
    return nb.encode("utf-8")

STAGE2_SET = [
    ("ddl", generate_ddl, "model.ddl.sql"),
    ("yaml", generate_yaml, "etl-contract.yaml"),
    ("stm_xlsx", generate_stm_xlsx, "STM_workbook.xlsx"),
    ("erd_html", generate_erd_html, "target-erd.html"),
    ("lddm_md", generate_lddm_md, "lddm-checklist.md"),
    ("construction_notebook", generate_construction_notebook,
     "construction_notebook.py"),
]
