/* DM Agent minimal workbench — vanilla JS against the JSON seam.
   Identity travels as X-Forwarded-Email: exactly the header Databricks
   Apps injects, so local and platform use one mechanism. */
const $ = (id) => document.getElementById(id);
let STATUS = null, CURRENT_STAGE = "stage0";

function acting() {
  return localStorage.getItem("dm_user") || "";
}
async function api(path, opts = {}) {
  const headers = Object.assign({"Content-Type": "application/json"},
                                opts.headers || {});
  const u = acting();
  if (u) headers["X-Forwarded-Email"] = u;
  const r = await fetch(path, Object.assign({}, opts, {headers}));
  const ct = r.headers.get("Content-Type") || "";
  const body = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    const msg = body && body.error ? body.error : `HTTP ${r.status}`;
    banner(msg, body && body.kind === "blocked");
    throw new Error(msg);
  }
  return body;
}
function banner(msg, warn) {
  const b = $("banner");
  b.textContent = msg;
  b.className = warn ? "warn" : "";
  clearTimeout(b._t);
  b._t = setTimeout(() => b.classList.add("hidden"), 8000);
}

/* ---------- status rail + selectors ---------- */
const STAGE_STEPS = ["stage0", "parsed", "stage1_confirmed", "stage2_confirmed"];
function stageForTask(t) {
  if (!STATUS) return "stage0";
  const spec = STATUS.tasks[t];
  if (!spec) return "stage0";
  if (t.startsWith("stage1")) return "stage1";
  if (t.startsWith("stage2") || t === "enhancement_delta") return "stage2";
  if (t === "stage0_data_product_planning") return "stage0";
  return t;
}
async function refreshStatus() {
  STATUS = await api("/api/status");
  if (STATUS.user && !acting()) {
    $("acting").placeholder = STATUS.user + " (platform identity)";
  }
  if (STATUS.role) $("rolebadge").textContent = STATUS.role.toUpperCase();
  if (!STATUS.project) {
    $("projname").textContent = "no work item yet";
    $("newproj").classList.remove("hidden");
    $("convo").classList.add("hidden");
    $("inputbar").classList.add("hidden");
    return;
  }
  $("newproj").classList.add("hidden");
  $("convo").classList.remove("hidden");
  $("inputbar").classList.remove("hidden");
  $("projname").textContent =
    `${STATUS.project.name}  ·  tenant ${STATUS.project.tenant}`;
  $("rolebadge").textContent = STATUS.role.toUpperCase();
  const src = $("source");
  const keep = src.value;
  src.innerHTML = "";
  STATUS.sources.forEach(s => {
    const o = document.createElement("option");
    o.value = s.source_id;
    o.textContent = `${s.source_id} · ${s.stage}` +
                    (s.qa_status === "REQUIRED" ? " ⚠" : "");
    src.appendChild(o);
  });
  if (keep) src.value = keep;
  const task = $("task");
  const keepT = task.value;
  task.innerHTML = "";
  Object.entries(STATUS.tasks).forEach(([k, v]) => {
    const o = document.createElement("option");
    o.value = k;
    o.textContent = `${v.slash} (${v.mode})`;
    task.appendChild(o);
  });
  if (keepT) task.value = keepT;
  paintRail();
}
function paintRail() {
  const sid = $("source").value;
  const s = STATUS.sources.find(x => x.source_id === sid);
  if (!s) { $("t_stage").querySelector(".tb").textContent = "no sources"; return; }
  const idx = STAGE_STEPS.indexOf(s.stage);
  const steps = STAGE_STEPS.map((_, i) =>
    `<span class="step ${i <= idx ? "done" : ""}"></span>`).join("");
  $("t_stage").querySelector(".tb").innerHTML =
    `<div class="steps">${steps}</div>
     <div class="hint">plan · parsed · stage 1 · stage 2</div>
     <div><span class="chip ${s.qa_status}">QA ${s.qa_status}</span></div>
     <div class="hint">next gate: <b>${s.next_gate || "—"}</b><br>
     type it in the conversation to confirm</div>`;
  const r = STATUS.last_run;
  $("t_run").querySelector(".tb").innerHTML = r ?
    `<div>${r.task_type}</div><div class="hint">${r.status} ·
     in ${r.tokens_in || 0} / out ${r.tokens_out || 0} tok</div>` : "—";
  $("t_open").querySelector(".tb").innerHTML =
    `<div>defects open: <b>${s.open_defects}</b></div>
     <div>unknowns open: <b>${STATUS.open_unknowns}</b></div>`;
}

/* ---------- tree + viewer ---------- */
async function refreshTree() {
  const rows = await api("/api/tree");
  const body = $("treebody");
  body.innerHTML = "";
  let lastDir = "";
  rows.forEach(r => {
    const parts = r.path.split("/");
    const dir = parts.slice(0, -1).join("/");
    if (dir !== lastDir) {
      const d = document.createElement("div");
      d.className = "t d";
      d.textContent = "▾ " + (dir || ".") + "/";
      body.appendChild(d);
      lastDir = dir;
    }
    const f = document.createElement("div");
    f.className = "t f";
    f.style.paddingLeft = (10 + parts.length * 8) + "px";
    f.textContent = parts[parts.length - 1];
    f.title = r.path + ` (${r.size} B)`;
    f.onclick = () => openFile(r.path);
    body.appendChild(f);
  });
  if (!rows.length) body.innerHTML = "<div class='hint'>no files yet</div>";
}
async function openFile(path) {
  const v = $("viewer");
  $("convo").classList.add("hidden");
  $("inputbar").classList.add("hidden");
  $("backbtn").classList.remove("hidden");
  v.classList.remove("hidden");
  if (path.endsWith(".html")) {
    v.innerHTML = "";
    const fr = document.createElement("iframe");
    fr.setAttribute("sandbox", "");
    fr.src = "/api/file?path=" + encodeURIComponent(path);
    v.appendChild(fr);
    return;
  }
  if (/\.(xlsx|zip|png)$/.test(path)) {
    v.innerHTML = `<p>${path}</p>
      <p><a style="color:#4ec9b0"
         href="/api/file?download=1&path=${encodeURIComponent(path)}">
         download</a></p>`;
    return;
  }
  const text = await api("/api/file?path=" + encodeURIComponent(path));
  v.textContent = typeof text === "string" ? text : JSON.stringify(text, null, 1);
}
$("backbtn").onclick = () => {
  $("viewer").classList.add("hidden");
  $("backbtn").classList.add("hidden");
  $("convo").classList.remove("hidden");
  $("inputbar").classList.remove("hidden");
};

/* ---------- conversation ---------- */
async function refreshThread() {
  CURRENT_STAGE = stageForTask($("task").value);
  const rows = await api(`/api/thread?stage=${CURRENT_STAGE}` +
                         `&source=${encodeURIComponent($("source").value || "")}`);
  const c = $("convo");
  c.innerHTML = "";
  rows.forEach(m => addMsg(m.role, m.content));
  if (!rows.length)
    addMsg("system", `No conversation yet on ${CURRENT_STAGE}. ` +
           `Discuss to think together; Generate to produce the deliverable; ` +
           `type a gate command to confirm.`);
  c.scrollTop = c.scrollHeight;
}
function addMsg(role, content) {
  const d = document.createElement("div");
  d.className = "m " + role;
  d.innerHTML = `<div class="who">${role}</div>`;
  const t = document.createElement("div");
  t.textContent = content;
  d.appendChild(t);
  $("convo").appendChild(d);
  $("convo").scrollTop = $("convo").scrollHeight;
}
async function send(chat) {
  const msg = $("msg").value.trim();
  if (!msg && chat) return;
  $("discuss").disabled = $("generate").disabled = true;
  try {
    if (msg) addMsg("user", msg);
    const r = await api("/api/send", {method: "POST", body: JSON.stringify({
      source: $("source").value || null, task: $("task").value,
      message: msg, chat})});
    if (r.kind === "gate") {
      addMsg("system", `✔ ${r.gate} — ${r.effect}`);
    } else {
      addMsg("assistant", r.assistant || "(empty)");
      if (r.outputs && r.outputs.length)
        addMsg("system", "outputs:\n" + r.outputs.join("\n"));
    }
    $("msg").value = "";
    await Promise.all([refreshStatus(), refreshTree()]);
  } catch (e) { /* banner already shown */ }
  $("discuss").disabled = $("generate").disabled = false;
}
$("discuss").onclick = () => send(true);
$("generate").onclick = () => send(false);
$("msg").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(true); }
});
$("source").onchange = () => { paintRail(); refreshThread(); };
$("task").onchange = refreshThread;

/* ---------- QA tile ---------- */
$("qarun").onclick = async () => {
  $("qarun").disabled = true;
  try {
    const r = await api("/api/qa", {method: "POST", body: JSON.stringify({
      mode: $("qamode").value, source: $("source").value || null})});
    addMsg("system", `Checker verdict: ${r.verdict} — ${r.defects ?? 0} ` +
           `defect(s), ${r.blocking ?? 0} blocking` +
           (r.report_path ? `\nreport: ${r.report_path}` : "") +
           (r.detail ? `\n${r.detail}` : ""));
    await Promise.all([refreshStatus(), refreshTree()]);
  } catch (e) {}
  $("qarun").disabled = false;
};
$("qapass").onclick = async () => {
  try {
    const r = await api("/api/qa/pass", {method: "POST",
      body: JSON.stringify({source: $("source").value})});
    addMsg("system", `QA PASSED for ${r.source_id}`);
    refreshStatus();
  } catch (e) {}
};
$("qawaive").onclick = async () => {
  try {
    const r = await api("/api/qa/waive", {method: "POST",
      body: JSON.stringify({source: $("source").value,
                            reason: $("waivereason").value})});
    addMsg("system", `QA WAIVED for ${r.source_id}`);
    $("waivereason").value = "";
    refreshStatus();
  } catch (e) {}
};

/* ---------- first-run create ---------- */
$("np_create").onclick = async () => {
  $("np_create").disabled = true;
  try {
    await api("/api/project", {method: "POST", body: JSON.stringify({
      name: $("np_name").value.trim(),
      tenant: $("np_tenant").value.trim(),
      primary_input_type: "IDRA", dp_type: "SADP",
      target_catalog: "workspace", schema_naming: "dm_demo"})});
    const sid = $("np_source").value.trim() || "SRC1";
    await api("/api/source", {method: "POST", body: JSON.stringify({
      source_id: sid, modelling_profile: $("np_profile").value})});
    await boot();
  } catch (e) {}
  $("np_create").disabled = false;
};

/* ---------- boot ---------- */
$("acting").value = acting();
$("acting").addEventListener("change", () => {
  localStorage.setItem("dm_user", $("acting").value.trim());
  boot();
});
async function boot() {
  try {
    await refreshStatus();
    await refreshTree();
    await refreshThread();
  } catch (e) {}
}
boot();
