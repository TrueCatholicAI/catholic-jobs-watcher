import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cfg = window.__CJW_CONFIG__ || {};
const supabase = createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY);

// ---------- DOM ----------
const $ = (sel) => document.querySelector(sel);
const els = {
  authGate:   $("#auth-gate"),
  secretIn:   $("#secret-input"),
  secretBtn:  $("#secret-submit"),
  secretErr:  $("#secret-error"),
  statsBar:   $("#stats-bar"),
  filters:    $("#filters"),
  list:       $("#list"),
  listEmpty:  $("#list-empty"),
  tabs:       document.querySelectorAll(".tab"),
  filterCompany: $("#filter-company"),
  filterScore:   $("#filter-score"),
  filterScoreVal:$("#filter-score-val"),
  filterStatus:  $("#filter-status"),
  filterQuery:   $("#filter-query"),
  stats: {
    total:     $("#stat-total"),
    active:    $("#stat-active"),
    week:      $("#stat-week"),
    topCompany:$("#stat-top-company"),
  },
};

// ---------- Auth gate ----------
const SECRET_KEY = "cjw_secret";
function checkAuth() {
  const required = (cfg.DASHBOARD_SECRET || "").trim();
  if (!required) return true;
  const stored = localStorage.getItem(SECRET_KEY);
  return stored === required;
}
function showAuthGate() {
  els.authGate.classList.remove("hidden");
  els.statsBar.classList.add("hidden");
  els.filters.classList.add("hidden");
  $("#list-wrap").classList.add("hidden");
}
els.secretBtn?.addEventListener("click", () => {
  const v = els.secretIn.value.trim();
  if (v === (cfg.DASHBOARD_SECRET || "").trim()) {
    localStorage.setItem(SECRET_KEY, v);
    location.reload();
  } else {
    els.secretErr.classList.remove("hidden");
  }
});

// ---------- State ----------
let view = "active";
let rows = [];

// ---------- Queries ----------
async function loadActive() {
  const { data, error } = await supabase
    .from("job_watcher_seen")
    .select("*")
    .eq("catholic_aligned", true)
    .eq("senior_design_or_product", true)
    .gte("fit_score", 7)
    .in("status", ["new", "starred"])
    .order("fit_score", { ascending: false })
    .order("first_seen_at", { ascending: false });
  if (error) throw error;
  return data || [];
}

async function loadHistory() {
  const { data, error } = await supabase
    .from("job_watcher_seen")
    .select("*")
    .order("first_seen_at", { ascending: false })
    .limit(500);
  if (error) throw error;
  return data || [];
}

async function loadStats() {
  const since7 = new Date(Date.now() - 7 * 86400_000).toISOString();
  const since90 = new Date(Date.now() - 90 * 86400_000).toISOString();

  const [total, active, week, top] = await Promise.all([
    supabase.from("job_watcher_seen").select("id", { count: "exact", head: true }),
    supabase.from("job_watcher_seen")
      .select("id", { count: "exact", head: true })
      .eq("catholic_aligned", true)
      .eq("senior_design_or_product", true)
      .gte("fit_score", 7)
      .in("status", ["new", "starred"]),
    supabase.from("job_watcher_seen")
      .select("id", { count: "exact", head: true })
      .gte("first_seen_at", since7),
    supabase.from("job_watcher_seen")
      .select("company")
      .gte("first_seen_at", since90)
      .not("company", "is", null)
      .limit(2000),
  ]);

  els.stats.total.textContent  = total.count ?? "—";
  els.stats.active.textContent = active.count ?? "—";
  els.stats.week.textContent   = week.count ?? "—";

  if (top.data && top.data.length) {
    const counts = new Map();
    for (const r of top.data) {
      counts.set(r.company, (counts.get(r.company) || 0) + 1);
    }
    let best = null;
    for (const [c, n] of counts) {
      if (!best || n > best.n) best = { c, n };
    }
    els.stats.topCompany.textContent = best ? `${best.c} (${best.n})` : "—";
  } else {
    els.stats.topCompany.textContent = "—";
  }
}

// ---------- Render ----------
function badge(score) {
  if (score == null) return `<span class="badge badge-low">?/10</span>`;
  if (score >= 9) return `<span class="badge badge-9">${score}/10</span>`;
  if (score >= 7) return `<span class="badge badge-7">${score}/10</span>`;
  return `<span class="badge badge-low">${score}/10</span>`;
}

function esc(s) {
  return (s ?? "").toString()
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function relDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  return d.toISOString().slice(0, 10);
}

function rowHtml(r) {
  const isStarred = r.status === "starred";
  const isApplied = r.status === "applied";
  const isDismissed = r.status === "dismissed";
  return `
    <li class="posting-card" data-id="${r.id}">
      <div class="title-row">
        ${badge(r.fit_score)}
        <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title || "(untitled)")}</a>
      </div>
      <div class="meta">
        <strong>${esc(r.company || "")}</strong>${r.location ? " · " + esc(r.location) : ""}
        · <span title="${esc(r.first_seen_at)}">${relDate(r.first_seen_at)}</span>
        · <span class="text-slate-400">${esc(r.source)}</span>
      </div>
      ${r.fit_reason ? `<div class="reason">${esc(r.fit_reason)}</div>` : ""}
      <div class="actions">
        <button class="action-btn ${isStarred ? "active" : ""}" data-act="starred">★ Star</button>
        <button class="action-btn ${isApplied ? "active" : ""}" data-act="applied">Applied</button>
        <button class="action-btn ${isDismissed ? "active" : ""}" data-act="dismissed">Dismiss</button>
        <button class="action-btn" data-act="new">Reset</button>
        ${r.url ? `<a class="action-btn" href="${esc(r.url)}" target="_blank" rel="noopener">Open ↗</a>` : ""}
      </div>
    </li>
  `;
}

function applyFiltersToRows(items) {
  const company = els.filterCompany.value;
  const minScore = parseInt(els.filterScore.value, 10) || 1;
  const status = els.filterStatus.value;
  const q = els.filterQuery.value.trim().toLowerCase();
  return items.filter((r) => {
    if (company && r.company !== company) return false;
    if ((r.fit_score ?? 0) < minScore) return false;
    if (status && r.status !== status) return false;
    if (q) {
      const hay = `${r.title || ""} ${r.company || ""} ${r.location || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderList() {
  const filtered = view === "history" ? applyFiltersToRows(rows) : rows;
  if (!filtered.length) {
    els.list.innerHTML = "";
    els.listEmpty.classList.remove("hidden");
  } else {
    els.listEmpty.classList.add("hidden");
    els.list.innerHTML = filtered.map(rowHtml).join("");
  }
}

function populateCompanyFilter() {
  const seen = new Set();
  const companies = rows.map(r => r.company).filter(c => {
    if (!c || seen.has(c)) return false;
    seen.add(c);
    return true;
  }).sort();
  els.filterCompany.innerHTML =
    `<option value="">All</option>` +
    companies.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
}

// ---------- Actions ----------
async function setStatus(id, status) {
  const local = rows.find(r => r.id === id);
  const prev = local?.status;
  if (local) local.status = status;
  renderList();

  const { error } = await supabase
    .from("job_watcher_seen")
    .update({ status, status_updated_at: new Date().toISOString() })
    .eq("id", id);
  if (error) {
    console.error("update failed", error);
    if (local) local.status = prev;
    renderList();
    alert("Update failed — see console.");
  }
}

els.list.addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-act]");
  if (!btn) return;
  const li = btn.closest("li[data-id]");
  if (!li) return;
  setStatus(li.dataset.id, btn.dataset.act);
});

// ---------- View switching ----------
async function switchView(name) {
  view = name;
  for (const t of els.tabs) {
    const active = t.dataset.view === name;
    t.classList.toggle("bg-slate-900", active);
    t.classList.toggle("text-white", active);
    t.classList.toggle("text-slate-600", !active);
  }
  els.filters.classList.toggle("hidden", name !== "history");
  rows = name === "active" ? await loadActive() : await loadHistory();
  if (name === "history") populateCompanyFilter();
  renderList();
}

for (const t of els.tabs) {
  t.addEventListener("click", () => switchView(t.dataset.view));
}

// ---------- Filter listeners ----------
els.filterCompany.addEventListener("change", renderList);
els.filterScore.addEventListener("input", () => {
  els.filterScoreVal.textContent = els.filterScore.value;
  renderList();
});
els.filterStatus.addEventListener("change", renderList);
els.filterQuery.addEventListener("input", renderList);

// ---------- Boot ----------
(async function boot() {
  if (!cfg.SUPABASE_URL || cfg.SUPABASE_URL.startsWith("REPLACE_ME")) {
    els.list.innerHTML = `<li class="p-6 text-sm text-red-600">
      Dashboard not configured. Set <code>SUPABASE_URL</code> and
      <code>SUPABASE_ANON_KEY</code> in <code>config.js</code>.</li>`;
    return;
  }
  if (!checkAuth()) {
    showAuthGate();
    return;
  }
  try {
    await Promise.all([loadStats(), switchView("active")]);
  } catch (err) {
    console.error(err);
    els.list.innerHTML = `<li class="p-6 text-sm text-red-600">Load failed: ${esc(err.message || err)}</li>`;
  }
})();
