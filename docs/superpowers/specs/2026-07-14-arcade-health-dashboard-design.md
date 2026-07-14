# Arcade Asset Health Dashboard — Design Spec

**Date:** 2026-07-14
**Phase:** 1 (POC)
**Scope:** Scoring model + interactive HTML dashboard

## Problem

Red Hat manages ~563 interactive demo ("arcade") assets. There is no system to determine whether an asset is current, who owns it, where it's deployed, or when it needs a refresh or retirement. The current analysis (analysis_v1.ipynb) provides engagement analytics but produces no actionable lifecycle statuses.

## Goals

Build a practical system that answers five questions per arcade:

1. Is it still current and relevant?
2. Where is it being used?
3. Who owns it / needs to review it?
4. When does it need an update, refresh, replacement, or retirement?
5. Who needs to be alerted when a product, name, feature, or message changes?

Phase 1 delivers goals 1–4 as a scored dataset and interactive dashboard. Goal 5 (alerting/notifications) is designed for but implemented in a later phase.

## Approach

Pandas scoring pipeline → JSON intermediate → self-contained interactive HTML file. No server, no framework, no build step.

## Data Sources

### Databricks Engagement Data (`data/databricksaracade.csv`)
- 563 unique arcades, 18 months (Jan 2025 – Jun 2026)
- Per-arcade monthly: players, completers, CTA clicks, completion rate, CTA click rate
- Sales attribution (65 arcades): UVs, inquiries, opps, wins, pipeline value, won value
- Classification: product, TDP, marketing program, verticals, language, event
- Pulled from: `dev.arcade_demo.v_arcade_name_month_v2`

### Request Master Metadata (`data/request_master.csv`)
- 229 rows (IE Published status only)
- Creator name, creator team, content type, quarter created, duration
- Deployment URLs: public site, production link, Drupal page, RHAC page, CTA link
- Destination channels, demo description, sales tactic
- Source: Google Sheet via OAuth (`gspread`)
- Join: `Join Key` column matches `arcade_display_key`. Normalized fallback for prefix variations. Current match rate: 205/563 (36%).

### Known Data Limitations
- CTA click tracking stops after Feb 2026 (zeros from Mar 2026 onward)
- Sales attribution exists for only 65 of 563 arcades
- 358 arcades have no Request Master match (no known owner or metadata)
- Product version alignment must be inferred from arcade names — no structured version field exists

## Health Score Model

Each arcade receives a composite health score from 0–100, built from four weighted dimensions.

### Engagement Health (35%)

Measures whether the arcade is actively used and how its usage is trending.

**Inputs:**
- Recent average monthly players (last 3 months)
- All-time average monthly players
- Completion rate (recent 3 months)
- Consecutive months of zero or near-zero engagement (< 3 players)

**Scoring logic:**
- Recent-to-historic ratio: >1.0 = growing (full marks), 0.5–1.0 = stable (partial), <0.5 = declining (low)
- Completion rate: scored against TDP peer group median (above median = full, below = scaled down)
- Zero-engagement months: 3+ consecutive months of near-zero engagement applies a steep penalty
- All values scaled relative to TDP peer group so niche arcades aren't penalized for lower absolute traffic

### Content Freshness (25%)

Measures how likely the content is to be outdated.

**Inputs:**
- Age in quarters since creation (from Request Master `Quarter` field, or `first_month` from Databricks as fallback)
- Product version references in arcade name (regex patterns like version numbers, year-quarter codes)

**Scoring logic:**
- Age: full marks if < 4 quarters old, linear decay to 6 quarters, steep penalty beyond 6 quarters
- Version mismatch: if arcade name contains a version string (e.g., "AAP 2.4", "CY24Q4"), apply a penalty based on age of that reference. This is heuristic — no authoritative "current version" source exists, so the scoring uses the version/date string's age relative to now. Not all arcades reference versions; those without version strings get no penalty here.
- No creation date available: moderate penalty (unknown age is a risk)

### Metadata Completeness (20%)

Measures whether the arcade is properly managed and trackable.

**Inputs (binary checklist):**
- Has a Request Master match
- Has an identified owner (Creator Name not empty)
- Has a CTA link
- Has a product or TDP classification
- Has at least one deployment URL (Drupal, RHAC, or public site)

**Scoring logic:**
- Each item is worth equal weight within the 20% dimension
- No Request Master match = maximum 40% of this dimension's score (you can't get full metadata marks without it)

### Sales/Conversion Signal (20%)

Measures whether the arcade drives business outcomes.

**Inputs:**
- Has any sales attribution data (yes/no)
- Total pipeline value (relative to peer group)
- CTA click-through rate (pre-March 2026 data only)
- Win rate where available

**Scoring logic:**
- Arcades with no sales data: neutral score (50% of dimension max). Don't penalize, but can't boost.
- Arcades with sales data: scored relative to peer group on pipeline value per player
- CTA click rate: only scored for months with tracking data (pre-March 2026)

### Composite Score and Lifecycle Status

Weighted sum of four dimensions → 0–100 score → lifecycle status:

| Score Range | Status   | Recommended Action | Review Timeline |
|-------------|----------|--------------------|-----------------|
| 80–100      | Healthy  | Keep as-is, standard review cycle | Next scheduled review |
| 60–79       | Watch    | Schedule review within 1 quarter | Within 3 months |
| 40–59       | Refresh  | Content update needed — flag to owner | Within 1 month |
| 20–39       | Replace  | Significant rework or new version needed | Urgent |
| 0–19        | Retire   | Candidate for removal — escalate to owner + team | Immediate |

## Data Pipeline

### Architecture

```
data_to_csv_v1.py          build_dashboard.py
(Databricks + Sheets)  →   (score + render)
        ↓                        ↓
data/databricksaracade.csv   data/arcade_health.json
data/request_master.csv      arcade_health_dashboard.html
```

### Entry Point: `build_dashboard.py`

```
python build_dashboard.py              # full: pull data → score → render
python build_dashboard.py --skip-pull  # score + render only (use existing CSVs)
```

### Stage 1: Data Pull (optional, via `--skip-pull` flag)

Calls the existing logic from `data_to_csv_v1.py`:
- Connects to Databricks, pulls `v_arcade_name_month_v2`, saves to `data/databricksaracade.csv`
- Connects to Google Sheets, pulls Request_Master (IE Published only), saves to `data/request_master.csv`

### Stage 2: Score

1. Load both CSVs
2. Merge datasets (exact Join Key match + normalized fallback)
3. Compute per-arcade metrics:
   - Recent 3-month engagement averages
   - Trend direction (comparing recent to all-time)
   - TDP peer group medians for relative scoring
   - Age calculation from Quarter field or first_month
   - Metadata completeness checklist
   - Sales metrics (where available)
4. Calculate four dimension scores (0–100 each)
5. Calculate composite health score (weighted sum)
6. Assign lifecycle status based on score thresholds
7. Output `data/arcade_health.json`

### Stage 3: Render

1. Load `data/arcade_health.json`
2. Generate a single self-contained HTML file: `arcade_health_dashboard.html`
3. Embed JSON data, CSS, and JS inline — no external dependencies
4. Use Tabulator.js (CDN link) for the interactive table

### Output JSON Schema

```json
{
  "generated_at": "2026-07-14T10:30:00",
  "summary": {
    "total_arcades": 563,
    "by_status": {"Healthy": 120, "Watch": 180, "Refresh": 150, "Replace": 80, "Retire": 33},
    "unowned_count": 358,
    "avg_health_score": 54.2
  },
  "arcades": [
    {
      "name": "Migrate VMs from VMware to Red Hat OpenShift | Business Intro",
      "health_score": 82,
      "status": "Healthy",
      "scores": {
        "engagement": 90,
        "freshness": 75,
        "metadata": 85,
        "sales": 78
      },
      "engagement": {
        "total_players": 5789,
        "recent_3mo_avg": 340,
        "alltime_monthly_avg": 322,
        "trend": "stable",
        "completion_rate": 27.4,
        "months_active": 18
      },
      "metadata": {
        "has_rm_match": true,
        "owner": "Ricardo Garcia Cavero",
        "team": "Portfolio Technical Marketing and Platforms",
        "product": "OpenShift",
        "tdp": "Virtualization",
        "content_type": "Business Intro",
        "quarter_created": "CY25Q1",
        "has_cta": true,
        "has_deployment_url": true
      },
      "deployment": {
        "drupal_url": "https://...",
        "rhac_url": "https://...",
        "public_site": "https://...",
        "cta_link": "https://..."
      },
      "sales": {
        "has_data": true,
        "total_opp_value": 2473725,
        "total_won_value": 861508,
        "opp_value_per_player": 427
      }
    }
  ]
}
```

## Interactive HTML Dashboard

### Technology
- Self-contained HTML file, no build step
- Tabulator.js for table rendering (loaded from CDN). The render script downloads and embeds the Tabulator JS/CSS inline so the HTML works fully offline.
- Vanilla CSS for styling — clean, professional, Red Hat-ish color palette
- No framework dependencies beyond Tabulator

### Layout

**Top: Summary Bar**
- Total arcades count
- Five colored status badges with counts (Healthy=green, Watch=yellow, Refresh=orange, Replace=red, Retire=dark red)
- Count of unowned arcades
- Data freshness timestamp ("Data as of: 2026-07-14")

**Middle: Filters**
- Status filter: checkbox per lifecycle status
- TDP dropdown
- Product dropdown
- Owner/Team dropdown
- Free-text search across arcade name

**Main: Arcade Table**

Sortable columns:
- Arcade Name
- Health Score (with color gradient)
- Status (color-coded badge)
- Owner
- Team
- TDP
- Product
- Players (recent 3mo avg)
- Trend (arrow icon: ↑ ↗ → ↘ ↓)
- Months Active
- Metadata (completeness indicator: ●●●○○)

**Row Expansion (click to expand):**
- Full scoring breakdown: four dimension scores as a horizontal bar chart or mini gauges
- Deployment URLs (clickable links)
- Sales attribution summary (if available)
- Demo description
- Recommended action text

### Interactions
- Click any column header to sort
- Click any filter to narrow the table
- Click a row to expand/collapse detail view
- All filtering/sorting happens client-side (data is embedded in the page)

## Phase 2 Design Hooks (not built in Phase 1)

The following are designed into the data model but not implemented:

### Notification System
- Owner-to-arcade mapping in JSON supports recipient lookup
- Status thresholds define trigger conditions
- Escalation chain: Creator → Team Lead → BU Contact
- Will be developed once scoring model is validated and trusted

### Product Change Alerting
- Product field per arcade enables product-to-arcade dependency mapping
- When a product name/version/feature changes, query all arcades with that product
- Surface affected arcades and their owners for targeted outreach

### Rcars Integration
- JSON output format is portable — can be consumed by Rcars or any downstream system
- Health score dimensions can be extended with Rcars content intelligence signals
- Rcars inputs needed: arcade content analysis, product version mapping, content similarity detection

## File Structure

```
retirement/
├── build_dashboard.py           # main entry point: pull → score → render
├── data_to_csv_v1.py            # existing data pull (Databricks + Sheets)
├── scoring.py                   # health score computation
├── render.py                    # HTML dashboard generation
├── data/
│   ├── databricksaracade.csv    # raw engagement data
│   ├── request_master.csv       # raw metadata
│   └── arcade_health.json       # scored output
├── arcade_health_dashboard.html # generated dashboard
└── docs/
    └── superpowers/specs/
        └── 2026-07-14-arcade-health-dashboard-design.md
```

## Success Criteria

Phase 1 is successful when:
1. Every arcade has a health score and lifecycle status
2. You can open the HTML dashboard, filter to "Retire" status, and see which arcades need action, who owns them, and where they're deployed
3. Ruby can run `python build_dashboard.py` and get a fresh dashboard
4. The scoring model produces results that match your intuition for arcades you know well — top performers score high, known-stale assets score low
5. The 358 unmatched arcades surface clearly as needing ownership assignment
