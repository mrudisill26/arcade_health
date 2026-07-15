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
├── IE_metadata_datapull.py          # GWS → Request_Master CSV
├── osspa_palist_datapull.py         # GitLab → PAList CSV
├── merge_palist_requestmaster.py    # join on ppid
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

## Data sources

| Source | Location |
|---|---|
| Request Master | Google Sheet `Request_Master` tab |
| PAList catalog | [osspa-site ArchitectureList](https://gitlab.com/osspa/osspa-site/-/tree/main/src/app/ArchitectureList) |
| Content (.adoc) | [portfolio-architecture-examples](https://gitlab.com/osspa/portfolio-architecture-examples) |

Merged catalog (~301 rows): live PAList assets + IE Published Request Master rows, joined on portfolio ID (`ppid`).

## What gets gitignored

- `data/` — regenerated locally (CSVs, index, content cache)
- `.venv/` — Python virtual environment
- `.claude/` — local IDE settings

The `poc/` folder contains a committed CSV snapshot so clones can run the advisor without live pulls.

## Related

Part of the [retirement](../) repo. See also the parent project's arcade health dashboard (`build_dashboard.py`).
