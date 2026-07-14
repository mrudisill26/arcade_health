# Arcade Health Dashboard

A scoring pipeline and interactive dashboard for managing the lifecycle of interactive demo ("arcade") assets.

## What It Does

Scores each arcade on four dimensions:
- **Engagement Health (35%)** — usage trends, completion rates, player volume relative to peers
- **Content Freshness (25%)** — age since creation, outdated version references
- **Metadata Completeness (20%)** — ownership, deployment URLs, product classification
- **Sales/Conversion Signal (20%)** — pipeline value, CTA click-through rates

Each arcade gets a composite health score (0–100) and a lifecycle status:

| Score | Status | Action |
|-------|--------|--------|
| 80–100 | Healthy | Standard review cycle |
| 60–79 | Watch | Review within 1 quarter |
| 40–59 | Refresh | Content update needed |
| 20–39 | Replace | Significant rework needed |
| 0–19 | Retire | Candidate for removal |

## Quick Start

```bash
# Set up
python -m venv .venv
source .venv/bin/activate
pip install pandas numpy pytest

# Run with existing data files
python build_dashboard.py --skip-pull

# Run with fresh data pull (requires Databricks + Google Sheets access)
python build_dashboard.py
```

Output: `arcade_health_dashboard.html` — open in any browser.

## Data Sources

This project requires two CSV files in `data/`:

1. **`data/databricksaracade.csv`** — Engagement data from Databricks (pulled via `data_to_csv_v1.py`)
2. **`data/request_master.csv`** — Metadata from Google Sheets Request_Master (all statuses; analysis focuses on IE Published)

Data files are not included in the repository. Run `python build_dashboard.py` (without `--skip-pull`) to fetch them, or place the CSVs manually.

## Project Structure

```
├── build_dashboard.py    # Entry point: pull → score → render
├── scoring.py            # Health score computation + JSON export
├── render.py             # HTML dashboard generation (Tabulator.js)
├── data_to_csv_v1.py     # Data pull from Databricks + Google Sheets
├── tests/
│   ├── test_scoring.py
│   ├── test_render.py
│   └── test_build_dashboard.py
└── docs/superpowers/
    ├── specs/            # Design spec
    └── plans/            # Implementation plan
```

## Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

## Dashboard Features

- Sortable columns (score, status, owner, TDP, players, trend)
- Filter by lifecycle status, TDP, owner, or free-text search
- Click any row to expand score breakdown, deployment links, and sales data
- Metadata completeness indicator dots per arcade
- Trend arrows showing engagement direction
