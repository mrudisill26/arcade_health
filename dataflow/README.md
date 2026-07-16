# Dataflow — Portfolio Catalog Advisor (POC)

A data pipeline and RCARS-style recommendation API for Red Hat Architecture Center / Interactive Experience assets. Pulls catalog metadata from Google Sheets and GitLab, merges it, indexes content with vector embeddings, and serves semantic search with progressive SSE results.

## What it does

```
Request_Master (Google Sheet)  ──┐
                                 ├── merge ──► merged CSV ──► fetch .adoc ──► scan ──► embed ──► SQLite index
PAList (GitLab osspa-site)     ──┘                                                              │
                                                                                                ▼
                                                                                    FastAPI advisor (vector → triage → rationale)
```

| Stage | Script | Output |
|---|---|---|
| Pull Request Master | `IE_metadata_datapull.py` | `data/request_master.csv` |
| Pull PAList | `osspa_palist_datapull.py` | `data/palist.csv` |
| Merge | `merge_palist_requestmaster.py` | `data/merged_live_and_ie_published.csv` |
| Orchestrator | `live_ie_published_datapull.py` | Runs pull + merge |
| Index | `build_index.py` | `data/advisor_index.sqlite` |
| Serve | `advisor_server.py` | HTTP API on port 8081 |

---

## Data collection

This section is the source of truth for **what we pull, how we join it, and what lands in the catalog**.

### Overview

| Step | When | Source | Local artifact |
|---|---|---|---|
| 1. Pull RM | On demand / orchestrator | Google Sheet `Request_Master` via `gws` | `data/request_master.csv` |
| 2. Pull PAList | On demand / orchestrator | GitLab `osspa-site` raw CSV | `data/palist.csv` |
| 3. Merge | After pulls (or `--skip-pull`) | Join RM ↔ PAList | `data/merged_live_and_ie_published.csv` |
| 4. Fetch content | During `build_index.py` | GitLab `.adoc` (or metadata fallback) | `data/content_cache/` + index |
| 5. Scan + embed | During `build_index.py` | Merged row + parsed text | `data/advisor_index.sqlite` |

Orchestrator (pull both sources, then merge):

```bash
.venv/bin/python live_ie_published_datapull.py
# or merge only, using existing CSVs:
.venv/bin/python live_ie_published_datapull.py --skip-pull
```

Generated files under `data/` are gitignored. For demos without live pulls, copy `poc/merged_live_and_ie_published.csv` → `data/`.

### Source 1 — Request Master (Google Sheet)

| | |
|---|---|
| Script | `IE_metadata_datapull.py` |
| Auth | [Google Workspace CLI (`gws`)](https://github.com/googleworkspace/cli) must be authenticated |
| Spreadsheet | Default ID in script (`DEFAULT_SPREADSHEET_ID`) |
| Tab | `Request_Master` |
| Output | `data/request_master.csv` |

The sheet is fetched in full, then **projected to a fixed column whitelist** (`RM_COLUMNS` in `merge_palist_requestmaster.py`). Missing headers are filled empty and warned on stderr.

#### Columns collected (with sheet letters)

| Column | Letter | Role in pipeline |
|---|---|---|
| Status | A | Filter IE Published RM-only rows; prefer published when colliding |
| Public Site Link | B | Canonical URL + **ppid extraction** |
| Production Link | C | Canonical URL + ppid extraction |
| Final Content Type | D | Format / content type for scan & triage |
| Drupal Page URL | F | Canonical URL + ppid extraction |
| RHAC page | G | Canonical URL + ppid extraction |
| Final Demo Title | H | Heading fallback; **secondary title join** |
| Publish states | S | Publish metadata (kept for future filters) |
| Featured Start Date | U | Featured window |
| Featured End Date | V | Featured window |
| Origin Type | AF | Provenance |
| Primary Product | AO | Product signal for scan / embed |
| Product | AP | Product signal |
| Marketing Program | AV | Catalog metadata |
| TDP | AW | Catalog metadata |
| Sales Tactic | AX | Catalog metadata |
| Verticals | AY | Vertical for embed / triage |
| Event | AZ | Event fit context |
| Primary Audience | BA | Audience for embed / triage / rationale |
| Personas | BB | Audience detail |
| Pain Points | BC | Intent matching signal |
| Creator Name | BH | Attribution |
| Creator Team | BJ | Attribution |
| Quarter | BL | Planning metadata |
| Demo Description | BM | Manual description (fallback) |
| Demo Description (Gemini generated) | BN | **Preferred description** for embed / scan / triage |
| Language | BO | Locale |
| Duration | BP | Curated duration for rerank |
| SEOWords | BQ | Keyword signal in embeddings |
| CTALink | BV | CTA URL |
| Join Key | CA | Usually a **title**, not a ppid (see join rules) |
| Number | CB | RM-internal row id (not portfolio ppid) |
| Metadata | CC | Freeform sheet metadata |

After merge, these appear on catalog rows with an `rm_` prefix and spaces turned into underscores, e.g.:

- `Demo Description` → `rm_Demo_Description`
- `Demo Description (Gemini generated)` → `rm_Demo_Description_(Gemini_generated)`

Helpers: `catalog_fields.rm_field()`, `demo_description()` (Gemini first, then manual).

#### Fields intentionally not pulled

Older columns such as `Content Type`, `Creation Link`, `Creator Employee Advocacy Link`, and `Latest Prod Link` are no longer in the whitelist. Prefer `Final Content Type` for type.

### Source 2 — PAList (GitLab)

| | |
|---|---|
| Script | `osspa_palist_datapull.py` (PAList only in the live/IE orchestrator) |
| Auth | None (public raw URLs) |
| Repo path | `osspa-site` → `src/app/ArchitectureList/PAList.csv` |
| Output | `data/palist.csv` |

#### PAList columns kept in the merge

`ppid`, `PAName`, `Heading`, `islive`, `isnew`, `showInCatalog`, `Summary`, `Vertical`, `Solutions`, `Platform`, `Product`, `ProductType`, `Image1Url`, `DetailPage`, `Status`, `externalUrl`, `isRedirected`

`DetailPage` drives `.adoc` fetch from [portfolio-architecture-examples](https://gitlab.com/osspa/portfolio-architecture-examples).

The same script can also pull Platform/Type/Solution/Product/DetailLink CSVs for other uses; the advisor merge path uses **PAList** only.

### Source 3 — AsciiDoc body (at index time)

| | |
|---|---|
| Script | `adoc_fetch.py` (called from `build_index.py`) |
| Repo | `portfolio-architecture-examples` raw `main` |
| Cache | `data/content_cache/` |

If `DetailPage` is set, the `.adoc` is fetched and parsed to plain text. If missing or fetch fails, a **metadata-only** blob is used (heading, summaries, Gemini/manual description, products, verticals, audience, SEO words, etc.).

### Merge — how rows are joined

Script: `merge_palist_requestmaster.py`  
Primary output for the advisor: `data/merged_live_and_ie_published.csv`

Each merged row has:

- `source`: `PAList+RM` | `PAList only` | `RM only`
- `canonical_url`: best public URL
- All PAList columns (blank for RM-only)
- All `rm_*` columns (blank for PAList-only)

#### Join strategy (order matters)

1. **Primary — portfolio ppid**
   - From RM URLs: `RHAC page`, `Public Site Link`, `Drupal Page URL`, `Production Link` (slug leading digits, e.g. `108-…` → `108`)
   - From `Join Key` **only** when it is clearly an id:
     - bare digits, or
     - paname form `123-slug`
   - **Do not** treat title-like Join Keys (e.g. `5. Kaoto - …`) as ppids
   - **`Number` is not a portfolio ppid** (RM-internal counter)

2. **Secondary — unique title match**
   - Normalize lightly (case, punctuation); **keep** parentheticals like `(Autoplay)` so variants do not cross-link
   - Match PAList `Heading` ↔ RM `Join Key` / `Final Demo Title` when the normalized title is unique on both sides
   - Skip if URL-derived ppids would conflict or the RM row is already claimed

3. **Collision preference**
   - When two RM rows map to the same ppid, prefer `Status == "IE Published"`

#### Live / IE Published catalog filter

`merge_live_and_ie_published()` keeps:

1. All PAList rows with `islive == TRUE` (with RM attached when joined)
2. Plus RM-only rows where `rm_Status == "IE Published"`

Typical size: ~300 rows (mostly `PAList+RM`, plus some `PAList only` / `RM only`).

Remaining `PAList only` rows are usually true orphans or intentional variants (autoplay / deep-dive) without a safe RM match.

### What collected data is used for downstream

| Stage | Uses |
|---|---|
| **Embeddings** (`embed_index.build_embed_text`) | Heading, analysis summary, Gemini/manual description, topics, products, type, vertical, solutions, audience, personas, pain points, SEO words, parsed body excerpt |
| **Scan** (`scan_analyze.py`) | Heading, PAList summary, products, vertical, Final Content Type, duration, audience/personas/pain points, Gemini description, body text |
| **Triage / rationale** | Compact catalog + analysis fields; description via `demo_description()` |
| **Duration rerank** | Curated `rm_Duration` when the user query mentions a time limit |

Without `ANTHROPIC_API_KEY`, scan/triage/rationale fall back to metadata (still using collected RM/PAList fields).

### Refresh checklist

```bash
# 1) Pull + merge
.venv/bin/python live_ie_published_datapull.py

# 2) Rebuild index (required after column or join changes)
export ANTHROPIC_API_KEY="..."   # optional but recommended
.venv/bin/python build_index.py

# 3) Serve
.venv/bin/uvicorn advisor_server:app --port 8081
```

To update the committed demo snapshot after a good pull:

```bash
cp data/merged_live_and_ie_published.csv poc/merged_live_and_ie_published.csv
```

---

## Quick start

### Prerequisites

- Python 3.11+
- [Google Workspace CLI (`gws`)](https://github.com/googleworkspace/cli) authenticated (for live Request Master pulls)
- Network access to GitLab (public raw URLs — no token needed)

Optional: `ANTHROPIC_API_KEY` for Sonnet/Haiku scan, triage, and rationale. Works without it using metadata fallbacks.

### Setup

```bash
cd dataflow
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Option A — Use committed POC snapshot (no pulls required)

```bash
mkdir -p data
cp poc/merged_live_and_ie_published.csv data/
.venv/bin/python build_index.py --fallback-scan
.venv/bin/uvicorn advisor_server:app --port 8081
```

### Option B — Refresh from live sources

```bash
.venv/bin/python live_ie_published_datapull.py          # full pull
# or
.venv/bin/python live_ie_published_datapull.py --skip-pull  # merge existing CSVs only

export ANTHROPIC_API_KEY="..."   # optional
.venv/bin/python build_index.py
.venv/bin/uvicorn advisor_server:app --port 8081
```

### Test the API

In a **second terminal**:

```bash
# Health check
curl http://localhost:8081/advisor/health

# Submit a query
curl -X POST http://localhost:8081/advisor/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"Ansible automation orchestrator workshop"}'

# Stream results (replace JOB_ID)
curl -N http://localhost:8081/advisor/query/JOB_ID/stream
```

Expected SSE phases: `VECTOR_SEARCH` → `TRIAGE` → `RATIONALE` → `COMPLETE`.

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/advisor/health` | Index stats |
| `POST` | `/advisor/query` | Submit query → `{job_id}` |
| `GET` | `/advisor/query/{job_id}/stream` | SSE progressive results |
| `POST` | `/advisor/reindex` | Background index rebuild |

There is no web UI — use `curl`, Postman, or any HTTP client.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enables Sonnet scan + Haiku triage + Sonnet rationale |
| `RCARS_VECTOR_CUTOFF` | `0.55` | Max cosine distance for vector search |
| `RCARS_TRIAGE_CUTOFF` | `30` | Min relevance score |
| `RCARS_RATIONALE_TOP_N` | `5` | Candidates sent to rationale phase |

## Project layout

```
dataflow/
├── README.md
├── requirements.txt
├── live_ie_published_datapull.py   # pull + merge orchestrator
├── IE_metadata_datapull.py          # GWS → Request_Master CSV (column projection)
├── osspa_palist_datapull.py         # GitLab → PAList CSV
├── merge_palist_requestmaster.py    # join + live/IE filter (RM_COLUMNS live here)
├── adoc_fetch.py                    # fetch .adoc from portfolio-architecture-examples
├── adoc_parse.py                    # strip AsciiDoc to plain text
├── scan_analyze.py                  # LLM structured analysis
├── embed_index.py                   # sentence-transformers embeddings
├── build_index.py                   # ingest entry point
├── advisor_server.py                # FastAPI + SSE
├── catalog_fields.py                # shared CSV field helpers
├── advisor/                         # recommendation pipeline
│   ├── pipeline.py                  # vector → triage → rationale
│   ├── vector_search.py
│   ├── triage.py
│   └── ...
├── poc/                             # committed snapshot for demo (see poc/README.md)
└── data/                            # local generated data (gitignored)
```

## What gets gitignored

- `data/` — regenerated locally (CSVs, index, content cache)
- `.venv/` — Python virtual environment
- `.claude/` — local IDE settings

The `poc/` folder contains a committed CSV snapshot so clones can run the advisor without live pulls.

## Related

Part of the [retirement](../) repo. See also the parent project's arcade health dashboard (`build_dashboard.py`).
