# Dataflow repo cleanup — design

**Date:** 2026-07-16  
**Status:** Approved for planning  
**Goal:** Make this repository a dataflow-only project. Remove Arcade Health and unrelated material. Promote `dataflow/` to the repo root so the catalog pipeline runs from the root without a nested folder.

## Background

The repo currently mixes two projects:

1. **Arcade Health dashboard** (repo root) — scoring, HTML dashboard, arcade CSVs, related tests and docs.
2. **Dataflow** (`dataflow/`) — pull/merge of Request Master + PAList into `merged_live_and_ie_published.csv`, plus optional advisor/POC tooling.

Only dataflow is needed going forward.

## Decisions

| Decision | Choice |
|---|---|
| Layout | Promote `dataflow/` contents to the repo root (no nested `dataflow/` folder) |
| Arcade Health | Delete entirely (code, data, tests, generated HTML, notebooks) |
| Existing `docs/superpowers/` arcade + UI docs | Delete entirely |
| Approach | In-place cleanup with `git mv` so dataflow file history is preserved |
| Scope of keep | Everything currently under `dataflow/` that supports running the pipeline and optional advisor/POC |

## End state

Repo root **is** the dataflow project:

```
├── README.md                 # former dataflow/README.md (paths updated)
├── .gitignore                # merged; no arcade-specific rules
├── requirements.txt
├── live_ie_published_datapull.py
├── IE_metadata_datapull.py
├── osspa_palist_datapull.py
├── merge_palist_requestmaster.py
├── catalog_fields.py
├── adoc_fetch.py / adoc_parse.py / scan_analyze.py / embed_index.py / build_index.py
├── advisor_index.py / advisor_server.py
├── advisor/
├── poc/
├── data/                     # gitignored generated outputs; .gitkeep tracked
└── .cursor/rules/            # dataflow workflow rule (paths updated)
```

Primary handoff artifact remains: `data/merged_live_and_ie_published.csv`.

## Delete list

**Tracked arcade / non-dataflow:**

- `build_dashboard.py`, `scoring.py`, `render.py`, `data_to_csv_v1.py`, `main.py`
- Root `README.md` (replaced by dataflow README)
- `static/theme.css`
- `tests/` (arcade health tests only)
- `docs/superpowers/plans/2026-07-14-arcade-health-dashboard.md`
- `docs/superpowers/specs/2026-07-14-arcade-health-dashboard-design.md`
- `docs/superpowers/plans/2026-07-14-ui-guideline.md`
- `docs/superpowers/specs/2026-07-14-ui-guideline-design.md`
- Empty `dataflow/` directory after promotion

**Local / untracked arcade artifacts (remove from working tree):**

- `arcade_health_dashboard.html`, `analysis_v1.ipynb`
- Root `data/` arcade files (`databricksaracade.csv`, `request_master.csv`, `arcade_health.json`)
- Arcade root `.venv` / `__pycache__` / `.pytest_cache` as needed

**Keep (do not delete):** this cleanup design (and its implementation plan once written) under `docs/superpowers/` so the cleanup itself is documented. All other prior docs are removed.

## Promote list

Move all tracked paths under `dataflow/` to the corresponding root paths, including:

- Pipeline and optional scripts listed in End state
- `advisor/`, `poc/`
- `requirements.txt`, `.gitignore` (merged into root)
- `.cursor/rules/dataflow-workflow.mdc`

Untracked local dataflow runtime under `dataflow/data/` and `dataflow/.venv` should be handled carefully: prefer moving useful generated CSVs into root `data/` if present, or leave them to be regenerated; do not commit gitignored data. Nested `dataflow/.venv` should not be promoted; recreate venv at root after cleanup.

## Path and doc updates

After promotion:

1. Root `README.md` — remove `cd dataflow`; document running from repo root; fix any tree diagram that shows a `dataflow/` prefix.
2. `.cursor/rules/dataflow-workflow.mdc` — refer to the project as the repo root, not `dataflow/`.
3. `.gitignore` — union of useful root Python/OS ignores + dataflow’s `data/*` / `!data/.gitkeep` pattern; drop `arcade_health_dashboard.html` and notebook blanket rules unless still desired for dataflow notebooks (dataflow may keep local notebooks untracked; prefer ignoring `__pycache__`, `.venv`, and `data/*` only).
4. User-Agent string `dataflow/1.0` in pull scripts may stay (product name, not a path).

No changes to merge/join logic, column contracts, or advisor behavior — this is structural cleanup only.

## Out of scope

- Renaming the git remote or GitHub repository
- Rewriting pipeline logic or advisor code
- Adding CI
- Committing generated catalog data under `data/`

## Success criteria

- Arcade Health files are gone from the working tree and index
- All former `dataflow/` tracked files live at repo root
- `README.md` instructions work from root (`python live_ie_published_datapull.py` / `--skip-pull`)
- `git status` is clean aside from intentional untracked local data/venv
- Optional: `python -c "import catalog_fields"` (or a dry import of merge module) succeeds from root with venv active
