import json


def render_dashboard(json_path: str, output_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)

    generated_date = data["generated_at"][:10]
    summary = data["summary"]
    arcades_json = json.dumps(data["arcades"])

    status_colors = {
        "Healthy": "#2e7d32",
        "Watch": "#f9a825",
        "Refresh": "#ef6c00",
        "Replace": "#c62828",
        "Retire": "#4a148c",
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
            f'<span class="badge" style="background:{color}">'
            f"{status}: {count}</span>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Arcade Health Dashboard</title>
<link href="https://unpkg.com/tabulator-tables@6.3.1/dist/css/tabulator_midnight.min.css" rel="stylesheet">
<script src="https://unpkg.com/tabulator-tables@6.3.1/dist/js/tabulator.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    padding: 20px;
  }}
  h1 {{
    font-size: 1.5rem;
    margin-bottom: 4px;
    color: #fff;
  }}
  .subtitle {{
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 16px;
  }}
  .summary-bar {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #16213e;
    border-radius: 8px;
  }}
  .summary-stat {{
    font-size: 0.9rem;
    color: #aaa;
  }}
  .summary-stat strong {{
    color: #fff;
    font-size: 1.1rem;
  }}
  .badge {{
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    color: #fff;
    font-size: 0.8rem;
    font-weight: 600;
  }}
  .filters {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
    align-items: center;
  }}
  .filters label {{
    font-size: 0.8rem;
    color: #aaa;
  }}
  .filters select, .filters input {{
    background: #16213e;
    color: #e0e0e0;
    border: 1px solid #333;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 0.85rem;
  }}
  .filter-group {{
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .status-filters {{
    display: flex;
    gap: 8px;
    align-items: center;
  }}
  .status-filters label {{
    display: flex;
    align-items: center;
    gap: 3px;
    cursor: pointer;
  }}
  #arcade-table {{ margin-top: 8px; }}

  .detail-row {{
    padding: 16px;
    background: #0f1729;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 16px;
  }}
  .detail-section h4 {{
    font-size: 0.8rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
  }}
  .detail-section p {{
    font-size: 0.85rem;
    margin-bottom: 4px;
  }}
  .detail-section a {{
    color: #64b5f6;
    text-decoration: none;
  }}
  .detail-section a:hover {{ text-decoration: underline; }}
  .score-bar {{
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }}
  .score-bar-label {{
    width: 90px;
    font-size: 0.8rem;
    color: #aaa;
  }}
  .score-bar-track {{
    flex: 1;
    height: 8px;
    background: #333;
    border-radius: 4px;
    overflow: hidden;
  }}
  .score-bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
  }}
  .score-bar-value {{
    width: 30px;
    text-align: right;
    font-size: 0.8rem;
  }}
  .metadata-dots {{
    display: inline-flex;
    gap: 2px;
  }}
  .metadata-dots .dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }}
  .dot-filled {{ background: #4caf50; }}
  .dot-empty {{ background: #444; }}
</style>
</head>
<body>

<h1>Arcade Health Dashboard</h1>
<p class="subtitle">Data as of: {generated_date}</p>

<div class="summary-bar">
  <div class="summary-stat"><strong>{summary['total_arcades']}</strong> arcades</div>
  <div class="summary-stat"><strong>{summary['unowned_count']}</strong> unowned</div>
  <div class="summary-stat">avg score: <strong>{summary['avg_health_score']}</strong></div>
  <div style="flex:1"></div>
  {status_badges_html}
</div>

<div class="filters">
  <div class="filter-group">
    <label>Status</label>
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

<div id="arcade-table"></div>

<script>
const ARCADE_DATA = {arcades_json};
const TREND_ARROWS = {json.dumps(trend_arrows)};
const STATUS_COLORS = {json.dumps(status_colors)};

// Populate filter dropdowns
const tdps = [...new Set(ARCADE_DATA.map(a => a.metadata.tdp).filter(Boolean))].sort();
const owners = [...new Set(ARCADE_DATA.map(a => a.metadata.owner).filter(Boolean))].sort();
const tdpSelect = document.getElementById("filter-tdp");
const ownerSelect = document.getElementById("filter-owner");
tdps.forEach(t => {{ const o = document.createElement("option"); o.value = t; o.textContent = t; tdpSelect.appendChild(o); }});
owners.forEach(t => {{ const o = document.createElement("option"); o.value = t; o.textContent = t; ownerSelect.appendChild(o); }});

function scoreColor(val) {{
  if (val >= 80) return "#2e7d32";
  if (val >= 60) return "#f9a825";
  if (val >= 40) return "#ef6c00";
  if (val >= 20) return "#c62828";
  return "#4a148c";
}}

function metadataDots(meta) {{
  const checks = [meta.has_rm_match, !!meta.owner, meta.has_cta, !!meta.product || !!meta.tdp, meta.has_deployment_url];
  return checks.map(c => '<span class="dot ' + (c ? 'dot-filled' : 'dot-empty') + '"></span>').join("");
}}

function makeDetailHtml(arcade) {{
  const s = arcade.scores;
  function bar(label, val) {{
    const color = scoreColor(val || 0);
    return '<div class="score-bar">' +
      '<span class="score-bar-label">' + label + '</span>' +
      '<div class="score-bar-track"><div class="score-bar-fill" style="width:' + (val||0) + '%;background:' + color + '"></div></div>' +
      '<span class="score-bar-value">' + (val||0) + '</span></div>';
  }}

  const dep = arcade.deployment;
  const links = [
    dep.drupal_url ? '<p><a href="' + dep.drupal_url + '" target="_blank">Drupal Page</a></p>' : '',
    dep.rhac_url ? '<p><a href="' + dep.rhac_url + '" target="_blank">RHAC Page</a></p>' : '',
    dep.public_site ? '<p><a href="' + dep.public_site + '" target="_blank">Public Site</a></p>' : '',
    dep.cta_link ? '<p><a href="' + dep.cta_link + '" target="_blank">CTA Link</a></p>' : '',
  ].filter(Boolean).join("") || '<p style="color:#666">No deployment URLs</p>';

  const sales = arcade.sales;
  const salesHtml = sales.has_data
    ? '<p>Pipeline: $' + (sales.total_opp_value||0).toLocaleString() + '</p>' +
      '<p>Won: $' + (sales.total_won_value||0).toLocaleString() + '</p>' +
      '<p>$/player: ' + (sales.opp_value_per_player||0).toLocaleString() + '</p>'
    : '<p style="color:#666">No sales data</p>';

  const desc = arcade.metadata.quarter_created
    ? '<p>Created: ' + arcade.metadata.quarter_created + '</p>'
    : '';

  return '<div class="detail-row">' +
    '<div class="detail-section"><h4>Score Breakdown</h4>' +
      bar("Engagement", s.engagement) + bar("Freshness", s.freshness) +
      bar("Metadata", s.metadata) + bar("Sales", s.sales) + '</div>' +
    '<div class="detail-section"><h4>Deployment</h4>' + links +
      '<h4 style="margin-top:12px">Sales Attribution</h4>' + salesHtml + '</div>' +
    '<div class="detail-section"><h4>Details</h4>' + desc +
      '<p>Type: ' + (arcade.metadata.content_type || 'N/A') + '</p>' +
      '<p>Channels: ' + (arcade.metadata.destination_channels || 'N/A') + '</p>' +
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
      formatter: function(cell) {{ return '<span style="font-weight:500">' + cell.getValue() + '</span>'; }}
    }},
    {{
      title: "Score", field: "health_score", width: 70, hozAlign: "center",
      formatter: function(cell) {{
        const v = cell.getValue();
        return '<span style="color:' + scoreColor(v) + ';font-weight:700">' + v + '</span>';
      }}
    }},
    {{
      title: "Status", field: "status", width: 90, hozAlign: "center",
      formatter: function(cell) {{
        const v = cell.getValue();
        return '<span class="badge" style="background:' + (STATUS_COLORS[v]||"#555") + ';font-size:0.75rem;padding:2px 8px">' + v + '</span>';
      }}
    }},
    {{
      title: "Owner", field: "metadata.owner", width: 160,
      formatter: function(cell) {{ return cell.getValue() || '<span style="color:#666">Unknown</span>'; }}
    }},
    {{ title: "Team", field: "metadata.team", width: 120, visible: false }},
    {{ title: "TDP", field: "metadata.tdp", width: 130 }},
    {{
      title: "Players (3mo)", field: "engagement.recent_3mo_avg", width: 100, hozAlign: "right",
      formatter: function(cell) {{ const v = cell.getValue(); return v != null ? Math.round(v).toLocaleString() : "-"; }}
    }},
    {{
      title: "Trend", field: "engagement.trend", width: 60, hozAlign: "center",
      formatter: function(cell) {{ return TREND_ARROWS[cell.getValue()] || "?"; }}
    }},
    {{ title: "Months", field: "engagement.months_active", width: 70, hozAlign: "center" }},
    {{
      title: "Meta", field: "metadata", width: 70, hozAlign: "center",
      formatter: function(cell) {{ return '<div class="metadata-dots">' + metadataDots(cell.getValue()) + '</div>'; }},
      headerSort: false,
    }},
  ],
}});

// Row click to expand/collapse detail
table.on("rowClick", function(e, row) {{
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
  const tdp = tdpSelect.value;
  const owner = ownerSelect.value;
  const search = document.getElementById("filter-search").value.toLowerCase();

  table.setFilter(function(data) {{
    if (!checkedStatuses.includes(data.status)) return false;
    if (tdp && data.metadata.tdp !== tdp) return false;
    if (owner && data.metadata.owner !== owner) return false;
    if (search && !data.name.toLowerCase().includes(search)) return false;
    return true;
  }});
}}

document.querySelectorAll(".status-cb").forEach(cb => cb.addEventListener("change", applyFilters));
tdpSelect.addEventListener("change", applyFilters);
ownerSelect.addEventListener("change", applyFilters);
document.getElementById("filter-search").addEventListener("input", applyFilters);
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    return output_path
