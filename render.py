import json
from pathlib import Path

from scoring import REQUEST_MASTER_STATUS_ORDER

THEME_CSS = (Path(__file__).parent / "static" / "theme.css").read_text()


def _ordered_rm_statuses(row_counts: dict, matched_counts: dict) -> list[str]:
    extras = set(row_counts) | set(matched_counts) - set(REQUEST_MASTER_STATUS_ORDER)
    ordered = [s for s in REQUEST_MASTER_STATUS_ORDER if s in row_counts or s in matched_counts]
    ordered += sorted(extras)
    return ordered


def _compute_analytics_summary(arcades: list) -> dict:
    if not arcades:
        return {"total_players": 0, "avg_3mo_players": 0.0, "avg_completion_rate": 0.0}

    total_players = sum(a.get("engagement", {}).get("total_players") or 0 for a in arcades)
    avg_3mo = sum(a.get("engagement", {}).get("recent_3mo_avg") or 0 for a in arcades) / len(arcades)
    completion_rates = [
        a["engagement"]["completion_rate"]
        for a in arcades
        if a.get("engagement", {}).get("completion_rate") is not None
    ]
    avg_completion = sum(completion_rates) / len(completion_rates) if completion_rates else 0.0

    return {
        "total_players": total_players,
        "avg_3mo_players": round(avg_3mo, 1),
        "avg_completion_rate": round(avg_completion, 1),
    }


def render_dashboard(json_path: str, output_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)

    generated_date = data["generated_at"][:10]
    summary = data["summary"]
    arcades = data["arcades"]
    analytics = _compute_analytics_summary(arcades)
    arcades_json = json.dumps(arcades)

    status_colors = {
        "Healthy": "var(--status-healthy)",
        "Watch": "var(--status-watch)",
        "Refresh": "var(--status-refresh)",
        "Replace": "var(--status-replace)",
        "Retire": "var(--status-retire)",
    }

    trend_arrows = {
        "growing_fast": "↑",
        "growing": "↗",
        "stable": "→",
        "declining": "↘",
        "declining_fast": "↓",
    }

    status_badges_html = ""
    for status in ["Healthy", "Watch", "Refresh", "Replace", "Retire"]:
        count = summary["by_status"].get(status, 0)
        color = status_colors[status]
        status_badges_html += (
            f'<span class="badge lifecycle-badge" style="background:{color}">'
            f"{status}: {count}</span>\n"
        )

    rm_row_counts = summary.get("request_master_row_counts_by_status", {})
    rm_matched_counts = summary.get("matched_arcades_by_rm_status", {})
    rm_status_list = _ordered_rm_statuses(rm_row_counts, rm_matched_counts)
    dropdown_statuses = list(REQUEST_MASTER_STATUS_ORDER)
    for status in rm_status_list:
        if status not in dropdown_statuses and status != "Unknown":
            dropdown_statuses.append(status)

    rm_status_options_html = '<option value="">All arcades</option>\n'
    for status in dropdown_statuses:
        selected = " selected" if status == "IE Published" else ""
        rm_status_options_html += (
            f'<option value="{status}"{selected}>{status}</option>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Arcade Health Dashboard</title>
<link href="https://unpkg.com/tabulator-tables@6.3.1/dist/css/tabulator.min.css" rel="stylesheet">
<script src="https://unpkg.com/tabulator-tables@6.3.1/dist/js/tabulator.min.js"></script>
<style>
  {THEME_CSS}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: var(--font-family);
    background: var(--bg-page);
    color: var(--text-primary);
    padding: var(--space-2xl) var(--space-xl);
    max-width: 1440px;
    margin: 0 auto;
  }}
  h1 {{
    font-family: var(--font-family-heading);
    font-size: var(--font-size-2xl);
    margin-bottom: var(--space-xs);
    color: var(--text-primary);
    font-weight: var(--font-weight-bold);
  }}
  .subtitle {{
    color: var(--text-muted);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-xl);
  }}

  /* Stat Cards */
  .stat-cards {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: var(--space-lg);
    margin-bottom: var(--space-lg);
  }}
  .stat-card {{
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    padding: var(--space-xl);
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }}
  .stat-label {{
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
    font-weight: var(--font-weight-medium);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  .stat-value {{
    font-family: var(--font-family-heading);
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    color: var(--text-primary);
  }}

  /* Status Badges */
  .badge {{
    display: inline-block;
    padding: var(--space-xs) var(--space-md);
    border-radius: var(--radius-pill);
    color: var(--text-on-color);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
  }}
  .status-row {{
    display: flex;
    gap: var(--space-sm);
    flex-wrap: wrap;
    margin-bottom: var(--space-xl);
  }}

  /* Filters */
  .filter-card {{
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    padding: var(--space-lg) var(--space-xl);
    margin-bottom: var(--space-lg);
  }}
  .filters {{
    display: flex;
    gap: var(--space-lg);
    flex-wrap: wrap;
    align-items: flex-end;
  }}
  .filters label {{
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
    font-weight: var(--font-weight-medium);
  }}
  .filters select, .filters input {{
    background: var(--bg-input);
    color: var(--text-primary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    padding: var(--space-sm) var(--space-md);
    font-size: var(--font-size-sm);
  }}
  .filters select:focus, .filters input:focus {{
    outline: none;
    border-color: var(--link-color);
    box-shadow: 0 0 0 1px var(--link-color);
  }}
  .filter-group {{
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }}
  .status-filters {{
    display: flex;
    gap: var(--space-md);
    align-items: center;
  }}
  .status-filters label {{
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    cursor: pointer;
    font-weight: var(--font-weight-normal);
  }}

  /* Table Card */
  .table-card {{
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    padding: var(--space-lg);
    overflow: hidden;
  }}
  #arcade-table {{ margin: 0; }}

  /* Tabulator overrides for light theme */
  .tabulator {{
    border: none;
    background: var(--bg-surface);
    font-family: var(--font-family);
    font-size: var(--font-size-md);
  }}
  .tabulator .tabulator-header {{
    background: var(--bg-surface-raised);
    border-bottom: 1px solid var(--border-default);
    font-weight: var(--font-weight-semibold);
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
  }}
  .tabulator .tabulator-header .tabulator-col {{
    background: transparent;
    border-right: none;
  }}
  .tabulator .tabulator-tableHolder .tabulator-table .tabulator-row {{
    border-bottom: 1px solid var(--border-default);
    background: var(--bg-surface);
    min-height: 44px;
  }}
  .tabulator .tabulator-tableHolder .tabulator-table .tabulator-row:hover {{
    background: var(--bg-surface-raised);
  }}
  .tabulator .tabulator-tableHolder .tabulator-table .tabulator-row .tabulator-cell {{
    border-right: none;
    padding: var(--space-md) var(--space-lg);
  }}

  /* Detail Expansion */
  .tabulator-detail-row {{
    width: 100%;
    box-sizing: border-box;
    overflow: hidden;
  }}
  .detail-row {{
    padding: var(--space-xl);
    background: var(--bg-surface-raised);
    border-top: 1px solid var(--border-default);
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-xl);
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
  }}
  @media (max-width: 768px) {{
    .stat-cards {{ grid-template-columns: 1fr; }}
    .detail-row {{ grid-template-columns: 1fr; }}
  }}
  .detail-section {{
    min-width: 0;
    max-width: 100%;
    overflow-wrap: break-word;
    word-break: break-word;
  }}
  .detail-section h4 {{
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: var(--space-sm);
    font-weight: var(--font-weight-semibold);
  }}
  .detail-section p {{
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-xs);
    color: var(--text-secondary);
  }}
  .detail-section a {{
    color: var(--link-color);
    text-decoration: none;
  }}
  .detail-section a:hover {{ text-decoration: underline; }}
  .demo-description {{
    margin-top: var(--space-sm);
    margin-bottom: var(--space-md);
    padding: var(--space-md);
    background: var(--bg-surface);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    max-width: 100%;
    box-sizing: border-box;
  }}
  .demo-description-label {{
    display: block;
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: var(--font-weight-semibold);
    margin-bottom: var(--space-xs);
  }}
  .demo-description-text {{
    margin: 0;
    font-size: var(--font-size-sm);
    line-height: 1.5;
    color: var(--text-secondary);
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: break-word;
  }}
  .score-bar {{
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-sm);
  }}
  .score-bar-label {{
    width: 90px;
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
  }}
  .score-bar-track {{
    flex: 1;
    height: var(--space-sm);
    background: var(--border-default);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }}
  .score-bar-fill {{
    height: 100%;
    border-radius: var(--radius-sm);
    transition: width 0.3s;
  }}
  .score-bar-value {{
    width: 30px;
    text-align: right;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
  }}
</style>
</head>
<body>

<h1>Arcade Health Dashboard</h1>
<p class="subtitle">Data as of: {generated_date}</p>

<div class="stat-cards">
  <div class="stat-card">
    <span class="stat-label">Total Arcades</span>
    <span class="stat-value">{summary['total_arcades']}</span>
  </div>
  <div class="stat-card">
    <span class="stat-label">Avg Health Score</span>
    <span class="stat-value">{summary.get('avg_health_score', '—')}</span>
  </div>
  <div class="stat-card">
    <span class="stat-label">Total Players</span>
    <span class="stat-value">{analytics['total_players']:,}</span>
  </div>
  <div class="stat-card">
    <span class="stat-label">Avg Players (3mo)</span>
    <span class="stat-value">{analytics['avg_3mo_players']}</span>
  </div>
  <div class="stat-card">
    <span class="stat-label">Avg Completion Rate</span>
    <span class="stat-value">{analytics['avg_completion_rate']}%</span>
  </div>
</div>

<div class="status-row">
  {status_badges_html}
</div>

<div class="filter-card">
  <div class="filters">
    <div class="filter-group">
      <label>Request Master status</label>
      <select id="filter-rm-status">{rm_status_options_html}</select>
    </div>
    <div class="filter-group">
      <label>Lifecycle status</label>
      <div class="status-filters">
        <label><input type="checkbox" class="status-cb" value="Healthy" checked> Healthy</label>
        <label><input type="checkbox" class="status-cb" value="Watch" checked> Watch</label>
        <label><input type="checkbox" class="status-cb" value="Refresh" checked> Refresh</label>
        <label><input type="checkbox" class="status-cb" value="Replace" checked> Replace</label>
        <label><input type="checkbox" class="status-cb" value="Retire" checked> Retire</label>
      </div>
    </div>
    <div class="filter-group">
      <label>TDP</label>
      <select id="filter-tdp"><option value="">All</option></select>
    </div>
    <div class="filter-group">
      <label>Owner</label>
      <select id="filter-owner"><option value="">All</option></select>
    </div>
    <div class="filter-group">
      <label>Search</label>
      <input type="text" id="filter-search" placeholder="Arcade name...">
    </div>
  </div>
</div>

<div class="table-card">
  <div id="arcade-table"></div>
</div>

<script>
const ARCADE_DATA = {arcades_json};
const TREND_ARROWS = {json.dumps(trend_arrows)};
const STATUS_COLORS = {json.dumps(status_colors)};

// Populate filter dropdowns
const tdps = [...new Set(ARCADE_DATA.map(a => a.metadata.tdp).filter(Boolean))].sort();
const owners = [...new Set(ARCADE_DATA.map(a => a.metadata.owner).filter(Boolean))].sort();
const tdpSelect = document.getElementById("filter-tdp");
const ownerSelect = document.getElementById("filter-owner");
const rmStatusSelect = document.getElementById("filter-rm-status");
tdps.forEach(t => {{ const o = document.createElement("option"); o.value = t; o.textContent = t; tdpSelect.appendChild(o); }});
owners.forEach(t => {{ const o = document.createElement("option"); o.value = t; o.textContent = t; ownerSelect.appendChild(o); }});

function arcadeHasRmStatus(data, rmStatus) {{
  const all = data.metadata.all_rm_statuses || [];
  const primary = data.metadata.rm_status || "";
  return primary === rmStatus || all.includes(rmStatus);
}}

function rmStatusText(meta) {{
  const statuses = (meta.all_rm_statuses && meta.all_rm_statuses.length)
    ? meta.all_rm_statuses
    : (meta.rm_status ? [meta.rm_status] : []);
  if (!statuses.length) {{
    return '<span style="color:var(--text-disabled)">—</span>';
  }}
  return statuses.join(", ");
}}

function scoreColor(val) {{
  const s = getComputedStyle(document.documentElement);
  if (val >= 80) return s.getPropertyValue('--status-healthy').trim();
  if (val >= 60) return s.getPropertyValue('--status-watch').trim();
  if (val >= 40) return s.getPropertyValue('--status-refresh').trim();
  if (val >= 20) return s.getPropertyValue('--status-replace').trim();
  return s.getPropertyValue('--status-retire').trim();
}}

function arcadeSiteUrl(dep) {{
  if (!dep) return "";
  if (dep.public_site) return dep.public_site;
  if (dep.rhac_url) return dep.rhac_url;
  return "";
}}

function arcadeNameHtml(name, dep) {{
  const url = arcadeSiteUrl(dep);
  const safeName = String(name)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
  if (!url) {{
    return '<span style="font-weight:var(--font-weight-medium)">' + safeName + '</span>';
  }}
  const safeUrl = String(url).replace(/"/g, "&quot;");
  return '<a href="' + safeUrl + '" target="_blank" rel="noopener noreferrer" ' +
    'style="font-weight:var(--font-weight-medium);color:var(--link-color);text-decoration:none" ' +
    'onclick="event.stopPropagation()">' + safeName + '</a>';
}}

function escapeHtml(text) {{
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}}

function formatSalesMoney(value) {{
  if (value == null || value === "") {{
    return '<span style="color:var(--text-disabled)">—</span>';
  }}
  return "$" + Math.round(value).toLocaleString();
}}

function formatSalesNumber(value) {{
  if (value == null || value === "") {{
    return '<span style="color:var(--text-disabled)">—</span>';
  }}
  const rounded = Math.round(value * 10) / 10;
  return rounded.toLocaleString();
}}

function makeDetailHtml(arcade) {{
  const s = arcade.scores;
  const e = arcade.engagement;
  function bar(label, val) {{
    const color = scoreColor(val || 0);
    return '<div class="score-bar">' +
      '<span class="score-bar-label">' + label + '</span>' +
      '<div class="score-bar-track"><div class="score-bar-fill" style="width:' + (val||0) + '%;background:' + color + '"></div></div>' +
      '<span class="score-bar-value">' + (val||0) + '</span></div>';
  }}

  const sales = arcade.sales || {{}};
  const salesHtml = sales.has_data
    ? '<p>Pipeline: $' + (sales.total_opp_value||0).toLocaleString() + '</p>' +
      '<p>Won: $' + (sales.total_won_value||0).toLocaleString() + '</p>' +
      '<p>Opportunities: ' + formatSalesNumber(sales.total_opps) + '</p>' +
      '<p>Wins: ' + formatSalesNumber(sales.total_wins) + '</p>' +
      '<p>$/player: ' + (sales.opp_value_per_player != null ? sales.opp_value_per_player.toLocaleString() : '—') + '</p>'
    : '<p style="color:var(--text-disabled)">No sales data</p>';

  const engagementHtml =
    '<p>Total players: ' + (e.total_players||0).toLocaleString() + '</p>' +
    '<p>Recent avg (3mo): ' + Math.round(e.recent_3mo_avg||0).toLocaleString() + ' /mo</p>' +
    '<p>All-time avg: ' + Math.round(e.alltime_monthly_avg||0).toLocaleString() + ' /mo</p>' +
    '<p>Completion rate: ' + (e.completion_rate != null ? e.completion_rate + '%' : '—') + '</p>' +
    '<p>Trend: ' + (TREND_ARROWS[e.trend] || '?') + ' ' + (e.trend || 'unknown') + '</p>' +
    '<p>Months active: ' + (e.months_active||0) + '</p>';
  const siteUrl = arcadeSiteUrl(arcade.deployment);
  const siteLinkHtml = siteUrl
    ? '<p>Demo link: <a href="' + siteUrl + '" target="_blank" rel="noopener noreferrer">View demo</a></p>'
    : '<p>Demo link: <span style="color:var(--text-disabled)">No public site or RHAC page</span></p>';
  const meta = arcade.metadata || {{}};
  const geminiDesc = meta.gemini_description;
  const geminiDescHtml = geminiDesc
    ? '<div class="demo-description">' +
      '<span class="demo-description-label">Demo description</span>' +
      '<p class="demo-description-text">' + escapeHtml(geminiDesc) + '</p></div>'
    : '';

  return '<div class="detail-row">' +
    '<div class="detail-section"><h4>Health Score Breakdown</h4>' +
      bar("Engagement", s.engagement) + bar("Freshness", s.freshness) +
      bar("Sales", s.sales) + '</div>' +
    '<div class="detail-section"><h4>Engagement Analytics</h4>' + siteLinkHtml + geminiDescHtml + engagementHtml +
      '<h4 style="margin-top:var(--space-md)">Sales Attribution</h4>' + salesHtml +
    '</div></div>';
}}

const table = new Tabulator("#arcade-table", {{
  data: ARCADE_DATA,
  layout: "fitColumns",
  responsiveLayout: "collapse",
  rowFormatter: function(row) {{
    const el = row.getElement();
    el.style.cursor = "pointer";
  }},
  columns: [
    {{
      title: "Arcade", field: "name", minWidth: 250, widthGrow: 3,
      formatter: function(cell) {{
        return arcadeNameHtml(cell.getValue(), cell.getRow().getData().deployment);
      }}
    }},
    {{
      title: "Score", field: "health_score", width: 70, hozAlign: "center",
      formatter: function(cell) {{
        const v = cell.getValue();
        return '<span style="color:' + scoreColor(v) + ';font-weight:var(--font-weight-bold)">' + v + '</span>';
      }}
    }},
    {{
      title: "Lifecycle", field: "status", width: 90, hozAlign: "center",
      formatter: function(cell) {{
        const v = cell.getValue();
        return '<span class="badge lifecycle-badge" style="background:' + (STATUS_COLORS[v]||"var(--border-default)") + ';font-size:var(--font-size-xs);padding:2px var(--space-sm)">' + v + '</span>';
      }}
    }},
    {{
      title: "RM Status", field: "metadata.rm_status", width: 160,
      formatter: function(cell) {{ return rmStatusText(cell.getRow().getData().metadata); }}
    }},
    {{
      title: "Owner", field: "metadata.owner", width: 160,
      formatter: function(cell) {{ return cell.getValue() || '<span style="color:var(--text-disabled)">Unknown</span>'; }}
    }},
    {{ title: "Team", field: "metadata.team", width: 120, visible: false }},
    {{ title: "TDP", field: "metadata.tdp", width: 130 }},
    {{
      title: "Players (3mo)", field: "engagement.recent_3mo_avg", width: 100, hozAlign: "right",
      formatter: function(cell) {{ const v = cell.getValue(); return v != null ? Math.round(v).toLocaleString() : "-"; }}
    }},
    {{
      title: "Completion", field: "engagement.completion_rate", width: 90, hozAlign: "right",
      formatter: function(cell) {{
        const v = cell.getValue();
        return v != null ? v.toFixed(1) + '%' : '—';
      }}
    }},
    {{
      title: "Total Players", field: "engagement.total_players", width: 100, hozAlign: "right",
      formatter: function(cell) {{ const v = cell.getValue(); return v != null ? v.toLocaleString() : "-"; }}
    }},
    {{
      title: "Pipeline", field: "sales.total_opp_value", width: 100, hozAlign: "right",
      formatter: function(cell) {{ return formatSalesMoney(cell.getValue()); }}
    }},
    {{
      title: "Won", field: "sales.total_won_value", width: 100, hozAlign: "right",
      formatter: function(cell) {{ return formatSalesMoney(cell.getValue()); }}
    }},
    {{
      title: "Opps", field: "sales.total_opps", width: 70, hozAlign: "right",
      formatter: function(cell) {{ return formatSalesNumber(cell.getValue()); }}
    }},
    {{
      title: "Trend", field: "engagement.trend", width: 60, hozAlign: "center",
      formatter: function(cell) {{ return TREND_ARROWS[cell.getValue()] || "?"; }}
    }},
    {{ title: "Months", field: "engagement.months_active", width: 70, hozAlign: "center" }},
  ],
}});

// Row click to expand/collapse detail
table.on("rowClick", function(e, row) {{
  if (e.target.closest("a")) return;
  const el = row.getElement();
  const existing = el.nextElementSibling;
  if (existing && existing.classList.contains("tabulator-detail-row")) {{
    existing.remove();
    return;
  }}
  // Remove any other open details
  document.querySelectorAll(".tabulator-detail-row").forEach(d => d.remove());
  const detail = document.createElement("div");
  detail.className = "tabulator-detail-row";
  detail.innerHTML = makeDetailHtml(row.getData());
  el.parentNode.insertBefore(detail, el.nextSibling);
}});

// Filtering
function applyFilters() {{
  const checkedStatuses = [...document.querySelectorAll(".status-cb:checked")].map(cb => cb.value);
  const rmStatus = rmStatusSelect.value;
  const tdp = tdpSelect.value;
  const owner = ownerSelect.value;
  const search = document.getElementById("filter-search").value.toLowerCase();

  table.setFilter(function(data) {{
    if (rmStatus && !arcadeHasRmStatus(data, rmStatus)) return false;
    if (!checkedStatuses.includes(data.status)) return false;
    if (tdp && data.metadata.tdp !== tdp) return false;
    if (owner && data.metadata.owner !== owner) return false;
    if (search && !data.name.toLowerCase().includes(search)) return false;
    return true;
  }});
}}

document.getElementById("filter-rm-status").addEventListener("change", applyFilters);
document.querySelectorAll(".status-cb").forEach(cb => cb.addEventListener("change", applyFilters));
tdpSelect.addEventListener("change", applyFilters);
ownerSelect.addEventListener("change", applyFilters);
document.getElementById("filter-search").addEventListener("input", applyFilters);
applyFilters();
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    return output_path
