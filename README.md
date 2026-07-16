# Dataflow — Portfolio catalog data collection

**Purpose:** Pull and merge Red Hat portfolio catalog metadata into a stable CSV that other applications can consume for search, recommendation, or evaluation.

This package is a **data collection workflow**. Evaluation / ranking / LLM recommendation logic belongs in the consuming application. A local advisor POC remains in-repo for smoke-testing the catalog, but it is **not** the handoff deliverable.

```
Request_Master (Google Sheet)  ──┐
                                 ├── merge ──► merged_live_and_ie_published.csv  ──► your app
PAList (GitLab osspa-site)     ──┘
                                      │
                                      └── (optional) .adoc fetch / scan / embed / local advisor
```

---

## Handoff contract

### Primary deliverable

| Artifact | Path | Description |
|---|---|---|
| **Merged catalog CSV** | `data/merged_live_and_ie_published.csv` | One row per asset. This is what you plug into another application. |
| POC snapshot (same schema) | `poc/merged_live_and_ie_published.csv` | Committed sample for offline use / CI without live pulls |

### How to produce it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # stdlib-only for pull/merge; requirements needed if you also index

# Requires: gws authenticated + GitLab network access
.venv/bin/python live_ie_published_datapull.py
```

Output: `data/merged_live_and_ie_published.csv` (~300 rows).

Merge-only (reuse existing pulls):

```bash
.venv/bin/python live_ie_published_datapull.py --skip-pull
```

### What the consuming app should read

Each row includes:

| Field group | Examples | Notes |
|---|---|---|
| Join / identity | `source`, `canonical_url`, `ppid`, `PAName`, `rm_Number`, `rm_Join_Key` | `source` ∈ `PAList+RM` \| `PAList only` \| `RM only` |
| PAList catalog | `Heading`, `Summary`, `Vertical`, `Product`, `ProductType`, `DetailPage`, `islive`, … | Blank on RM-only rows |
| Request Master (`rm_*`) | `rm_Final_Demo_Title`, `rm_Demo_Description`, `rm_Demo_Description_(Gemini_generated)`, `rm_Duration`, `rm_Primary_Product`, `rm_SEOWords`, `rm_Primary_Audience`, … | Blank on PAList-only rows |

**Preferred description for display / retrieval text:**  
`rm_Demo_Description_(Gemini_generated)` falling back to `rm_Demo_Description` or PAList `Summary`  
(helper: `catalog_fields.demo_description(row)`).

**Do not treat as portfolio ppid:** `rm_Number` (RM-internal id), title-like `rm_Join_Key`.

Helpers for field access live in `catalog_fields.py` (`rm_field`, `display_heading`, `demo_description`).

### Out of scope for handoff

These are optional local tools, not required by the consuming app:

- `build_index.py` / `advisor_index.sqlite` — embeddings index
- `advisor_server.py` / `advisor/` — RCARS-style evaluation POC
- `ANTHROPIC_API_KEY` — only for optional scan / local advisor

Pull + merge scripts are intended to stay **stdlib-only** (`IE_metadata_datapull.py`, `osspa_palist_datapull.py`, `merge_palist_requestmaster.py`, `live_ie_published_datapull.py`).

---

## Pipeline stages

| Stage | Script | Output | Required for handoff? |
|---|---|---|---|
| Pull Request Master | `IE_metadata_datapull.py` | `data/request_master.csv` | Yes |
| Pull PAList | `osspa_palist_datapull.py` | `data/palist.csv` | Yes |
| Merge | `merge_palist_requestmaster.py` | `data/merged_live_and_ie_published.csv` | Yes |
| Orchestrator | `live_ie_published_datapull.py` | Runs pull + merge | Yes (entry point) |
| Fetch `.adoc` / scan / embed | `build_index.py` | `data/advisor_index.sqlite` | No |
| Local advisor API | `advisor_server.py` | `:8081` | No |

---

## Data collection details

### Source 1 — Request Master (Google Sheet)

| | |
|---|---|
| Script | `IE_metadata_datapull.py` |
| Auth | [Google Workspace CLI (`gws`)](https://github.com/googleworkspace/cli) |
| Tab | `Request_Master` |
| Output | `data/request_master.csv` |

The sheet is fetched in full, then **projected to a fixed whitelist** (`RM_COLUMNS` in `merge_palist_requestmaster.py`). Missing headers become empty cells; warnings go to stderr.

#### Columns collected (sheet letters)

| Column | Letter | Why we keep it |
|---|---|---|
| Status | A | IE Published filter; collision preference |
| Public Site Link | B | Canonical URL + **ppid extraction** |
| Production Link | C | Canonical URL + ppid extraction |
| Final Content Type | D | Content / format type |
| Drupal Page URL | F | Canonical URL + ppid extraction |
| RHAC page | G | Canonical URL + ppid extraction |
| Final Demo Title | H | Title; secondary join |
| Publish states | S | Publish metadata |
| Featured Start Date | U | Featured window |
| Featured End Date | V | Featured window |
| Origin Type | AF | Provenance |
| Primary Product | AO | Product |
| Product | AP | Product |
| Marketing Program | AV | Program |
| TDP | AW | TDP |
| Sales Tactic | AX | Tactic |
| Verticals | AY | Vertical |
| Event | AZ | Event |
| Primary Audience | BA | Audience |
| Personas | BB | Personas |
| Pain Points | BC | Pain points |
| Creator Name | BH | Attribution |
| Creator Team | BJ | Attribution |
| Quarter | BL | Quarter |
| Demo Description | BM | Manual description |
| Demo Description (Gemini generated) | BN | Preferred generated description |
| Language | BO | Locale |
| Duration | BP | Duration |
| SEOWords | BQ | SEO / keywords |
| CTALink | BV | CTA |
| Join Key | CA | Usually a **title**, not a ppid |
| Number | CB | RM-internal id (not portfolio ppid) |
| Metadata | CC | Freeform |

Merged names use `rm_` + spaces → underscores, e.g. `rm_Demo_Description_(Gemini_generated)`.

**Not pulled:** `Content Type`, `Creation Link`, `Creator Employee Advocacy Link`, `Latest Prod Link` (use `Final Content Type` instead).

### Source 2 — PAList (GitLab)

| | |
|---|---|
| Script | `osspa_palist_datapull.py` |
| Auth | None (public raw URL) |
| Path | `osspa-site` → `ArchitectureList/PAList.csv` |
| Output | `data/palist.csv` |

Columns kept: `ppid`, `PAName`, `Heading`, `islive`, `isnew`, `showInCatalog`, `Summary`, `Vertical`, `Solutions`, `Platform`, `Product`, `ProductType`, `Image1Url`, `DetailPage`, `Status`, `externalUrl`, `isRedirected`.

`DetailPage` points at AsciiDoc in [portfolio-architecture-examples](https://gitlab.com/osspa/portfolio-architecture-examples) (used only if you run optional indexing).

### Merge — join rules

Script: `merge_palist_requestmaster.py`

1. **Primary — portfolio ppid** from RM URLs (`RHAC page`, `Public Site Link`, `Drupal Page URL`, `Production Link`), or from `Join Key` only when it is bare digits or `123-slug` paname form. Never treat title-like Join Keys (e.g. `5. Kaoto - …`) as ppids. Never use `Number` as portfolio ppid.
2. **Secondary — unique title match** between PAList `Heading` and RM `Join Key` / `Final Demo Title` (light normalization; parentheticals like `(Autoplay)` kept so variants do not cross-link). Skipped on ppid conflict or if the RM row is already claimed.
3. **Collisions:** prefer RM `Status == "IE Published"`.

#### Catalog filter (`merge_live_and_ie_published`)

Keeps:

1. PAList rows with `islive == TRUE` (RM attached when joined)
2. RM-only rows with `rm_Status == "IE Published"`

Typical mix: mostly `PAList+RM`, plus some `PAList only` / `RM only` orphans or variants.

### Optional: content enrichment (not required for handoff)

If the consuming app wants body text or vectors from this repo:

```bash
.venv/bin/python build_index.py --fallback-scan
# or with ANTHROPIC_API_KEY for LLM scan analysis
```

That writes `data/advisor_index.sqlite` (metadata JSON per asset, parsed text, optional embeddings). Your application may instead ingest the merged CSV directly and build its own index.

---

## Prerequisites

- Python 3.11+
- [`gws`](https://github.com/googleworkspace/cli) authenticated (Request Master pulls)
- Network access to GitLab public raw URLs

---

## Quick start (data only)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python live_ie_published_datapull.py
ls -la data/merged_live_and_ie_published.csv
```

Offline sample (no pulls):

```bash
mkdir -p data
cp poc/merged_live_and_ie_published.csv data/
```

### Optional local advisor smoke test

```bash
.venv/bin/python build_index.py --fallback-scan
.venv/bin/uvicorn advisor_server:app --port 8081
curl http://localhost:8081/advisor/health
```

Env knobs for that POC only: `ANTHROPIC_API_KEY`, `RCARS_VECTOR_CUTOFF`, `RCARS_TRIAGE_CUTOFF`, `RCARS_RATIONALE_TOP_N`.

---

## Project layout

```
.
├── README.md
├── live_ie_published_datapull.py
├── IE_metadata_datapull.py
├── osspa_palist_datapull.py
├── merge_palist_requestmaster.py
├── catalog_fields.py
├── build_index.py
├── advisor_server.py / advisor/
├── poc/
└── data/
```

## Gitignore

- `data/` — regenerated locally
- `.venv/`
- `.claude/`

Refresh the committed snapshot after a good pull:

```bash
cp data/merged_live_and_ie_published.csv poc/
# update poc/stats.json (see poc/README.md)
```

## Related

This repository is the portfolio catalog **data collection** handoff. Consuming apps should ingest `data/merged_live_and_ie_published.csv` (or `poc/` offline).
