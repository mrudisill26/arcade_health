# Dataflow Repo Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make this repository dataflow-only by promoting `dataflow/` to the repo root and deleting Arcade Health and unrelated docs.

**Architecture:** In-place structural cleanup with `git mv` so dataflow file history is preserved. No pipeline logic changes — only layout, README/gitignore/cursor-rule path updates, and deletion of arcade material.

**Tech Stack:** Git, Python 3.11+ (stdlib pull/merge; optional deps in `requirements.txt`), existing dataflow scripts.

**Spec:** `docs/superpowers/specs/2026-07-16-dataflow-repo-cleanup-design.md`

## Global Constraints

- Do not change merge/join logic, column contracts, or advisor behavior.
- Do not commit generated catalog data under `data/` (except `data/.gitkeep`).
- Do not promote nested `dataflow/.venv`; recreate venv at root if needed.
- Preserve dataflow file history via `git mv` where practical.
- Keep this cleanup design and this plan under `docs/superpowers/`; delete all other prior docs listed in the spec.
- User-Agent string `dataflow/1.0` in pull scripts stays (product name, not a path).

---

## File map

| Path | Action |
|---|---|
| `dataflow/**` (tracked) | Move to repo root equivalents |
| Root arcade Python (`build_dashboard.py`, `scoring.py`, `render.py`, `data_to_csv_v1.py`, `main.py`) | Delete |
| Root `README.md` | Replace with promoted dataflow README (path-fixed) |
| Root `.gitignore` | Replace with merged dataflow-oriented ignore rules |
| `static/`, `tests/` | Delete |
| Old arcade/UI docs under `docs/superpowers/` | Delete (keep cleanup design + this plan) |
| Local arcade artifacts (`arcade_health_dashboard.html`, `analysis_v1.ipynb`, root `data/*`) | Delete from working tree |
| `data/.gitkeep` | Create + track after new gitignore allows it |
| `.cursor/rules/dataflow-workflow.mdc` | Update wording (no `dataflow/` project path) |
| Empty `dataflow/` | Remove after move |

---

### Task 1: Clear arcade root `data/` collision and move local dataflow runtime data aside

**Files:**
- Delete (untracked): `data/databricksaracade.csv`, `data/request_master.csv`, `data/arcade_health.json`, and any other root `data/*`
- Preserve locally (not committed): contents of `dataflow/data/` by moving to a temp path before promotion

**Why:** Root `data/` is arcade-only and conflicts with the dataflow `data/` directory name after promotion. Existing `dataflow/data/*.csv` / sqlite should survive locally if possible.

- [ ] **Step 1: Verify arcade root data vs dataflow data**

Run:

```bash
ls -la data/
ls -la dataflow/data/
```

Expected: root `data/` has arcade CSVs/JSON; `dataflow/data/` has `merged_live_and_ie_published.csv`, `palist.csv`, `request_master.csv`, optionally sqlite/cache, and `.gitkeep`.

- [ ] **Step 2: Move dataflow generated data to a safe temp location**

```bash
rm -rf /tmp/retirement-dataflow-data-backup
mkdir -p /tmp/retirement-dataflow-data-backup
# Preserve generated files (including .gitkeep) outside the repo briefly
cp -a dataflow/data/. /tmp/retirement-dataflow-data-backup/
```

Expected: `/tmp/retirement-dataflow-data-backup/` contains the former `dataflow/data/` contents.

- [ ] **Step 3: Remove arcade root `data/` directory**

```bash
rm -rf data/
```

Expected: `test ! -d data` succeeds.

- [ ] **Step 4: Do not commit**

This task only clears local untracked/ignored data. No git commit.

---

### Task 2: Promote tracked `dataflow/` files to repo root

**Files:**
- Move: every path under `git ls-files dataflow/` to the same relative path without the `dataflow/` prefix
- Conflict handling: root already has `README.md` and `.gitignore` — remove arcade versions first, then move

**Interfaces:**
- Consumes: clean root `data/` absence from Task 1
- Produces: dataflow scripts/packages at repo root; empty or near-empty `dataflow/` left for later removal

- [ ] **Step 1: List tracked dataflow paths**

```bash
git ls-files dataflow/
```

Expected: ~29 paths including scripts, `advisor/`, `poc/`, `README.md`, `.gitignore`, `.cursor/rules/dataflow-workflow.mdc`, `requirements.txt`.

- [ ] **Step 2: Remove arcade root files that block the move**

```bash
git rm -f README.md .gitignore
git rm -f build_dashboard.py scoring.py render.py data_to_csv_v1.py main.py
git rm -rf static tests
```

Expected: those paths staged for deletion; no unstaged errors about missing files.

- [ ] **Step 3: Create destination dirs and `git mv` dataflow tree to root**

```bash
mkdir -p advisor poc .cursor/rules
git mv dataflow/README.md README.md
git mv dataflow/.gitignore .gitignore.dataflow-tmp
git mv dataflow/requirements.txt requirements.txt
git mv dataflow/IE_metadata_datapull.py IE_metadata_datapull.py
git mv dataflow/osspa_palist_datapull.py osspa_palist_datapull.py
git mv dataflow/merge_palist_requestmaster.py merge_palist_requestmaster.py
git mv dataflow/live_ie_published_datapull.py live_ie_published_datapull.py
git mv dataflow/catalog_fields.py catalog_fields.py
git mv dataflow/adoc_fetch.py adoc_fetch.py
git mv dataflow/adoc_parse.py adoc_parse.py
git mv dataflow/scan_analyze.py scan_analyze.py
git mv dataflow/embed_index.py embed_index.py
git mv dataflow/build_index.py build_index.py
git mv dataflow/advisor_index.py advisor_index.py
git mv dataflow/advisor_server.py advisor_server.py
git mv dataflow/advisor advisor
git mv dataflow/poc poc
git mv dataflow/.cursor/rules/dataflow-workflow.mdc .cursor/rules/dataflow-workflow.mdc
```

Expected: `git ls-files dataflow/` returns empty (or only leftover empty dirs / untracked junk). Root has `live_ie_published_datapull.py`, `advisor/`, `poc/`, etc.

- [ ] **Step 4: Verify no tracked files remain under `dataflow/`**

```bash
git ls-files dataflow/
ls -la dataflow/ 2>/dev/null || true
```

Expected: no tracked files. Untracked leftovers may include `dataflow/.venv`, `dataflow/__pycache__`, `dataflow/datacheck.ipynb`, empty dirs — clean those in Task 4.

- [ ] **Step 5: Commit the promotion + arcade tracked deletions**

```bash
git add -A
git status
git commit -m "$(cat <<'EOF'
Promote dataflow to repo root and remove arcade health code.

EOF
)"
```

Note: `.gitignore` is still the temporary `.gitignore.dataflow-tmp` until Task 3 — that is intentional so this commit can land the moves first. If `git status` shows `.gitignore.dataflow-tmp` as added and no root `.gitignore`, that is OK for this commit; Task 3 fixes ignore rules immediately after.

**Preferred alternate (cleaner):** skip committing here and commit once after Task 3 merges `.gitignore`. If you prefer one commit for move+ignore+docs, defer Step 5 until end of Task 3.

**Use the single-commit approach:** do **not** commit in this task; proceed to Task 3, then commit once covering Tasks 2–4 content that is staged.

---

### Task 3: Install merged root `.gitignore` and track `data/.gitkeep`

**Files:**
- Create: `.gitignore` (final)
- Delete: `.gitignore.dataflow-tmp` (after merge)
- Create: `data/.gitkeep`
- Modify: none of the Python pipeline files

**Interfaces:**
- Consumes: `.gitignore.dataflow-tmp` from Task 2
- Produces: root `.gitignore` that ignores `data/*` but allows `data/.gitkeep`

- [ ] **Step 1: Write the final root `.gitignore`**

Create `.gitignore` with exactly:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
.eggs/
dist/
build/
.pytest_cache/
.coverage
htmlcov/

# Virtual environments
.venv/
venv/
ENV/
env/

# Local IDE / agent settings
.claude/
.cursor/settings.local.json
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Generated at runtime (regenerate via pipeline)
data/*
!data/.gitkeep
```

Then remove the temp file:

```bash
rm -f .gitignore.dataflow-tmp
```

- [ ] **Step 2: Restore local dataflow data and ensure `.gitkeep`**

```bash
mkdir -p data
cp -a /tmp/retirement-dataflow-data-backup/. data/ 2>/dev/null || true
# Ensure gitkeep exists even if backup was empty
test -f data/.gitkeep || : > data/.gitkeep
```

- [ ] **Step 3: Force-add `data/.gitkeep` and stage `.gitignore`**

```bash
git add .gitignore
git add -f data/.gitkeep
git check-ignore -v data/merged_live_and_ie_published.csv || true
git check-ignore -v data/.gitkeep || true
```

Expected:
- Generated CSV under `data/` is ignored (check-ignore prints a matching rule).
- `data/.gitkeep` is **not** ignored (check-ignore exits non-zero / prints nothing useful as “ignored”).

- [ ] **Step 4: Smoke-check import from root (optional venv)**

```bash
python3 -c "import catalog_fields; import merge_palist_requestmaster; print('ok')"
```

Expected: prints `ok`. If imports fail due to missing deps for advisor-only modules, that is fine — these two should be stdlib-friendly. If `merge_palist_requestmaster` imports fail for an unexpected reason, stop and fix before continuing.

---

### Task 4: Delete remaining arcade artifacts and empty `dataflow/` shell

**Files:**
- Delete (working tree): `arcade_health_dashboard.html`, `analysis_v1.ipynb`
- Delete (tracked if still present): old docs listed below
- Delete: leftover `dataflow/` directory (venv, pycache, notebook, empty dirs)
- Delete untracked UI guideline docs if still present

**Delete tracked docs (keep cleanup design + this plan):**

```bash
git rm -f \
  docs/superpowers/plans/2026-07-14-arcade-health-dashboard.md \
  docs/superpowers/specs/2026-07-14-arcade-health-dashboard-design.md \
  2>/dev/null || true

# Untracked UI guideline docs — remove from disk
rm -f \
  docs/superpowers/plans/2026-07-14-ui-guideline.md \
  docs/superpowers/specs/2026-07-14-ui-guideline-design.md
```

Keep:

- `docs/superpowers/specs/2026-07-16-dataflow-repo-cleanup-design.md`
- `docs/superpowers/plans/2026-07-16-dataflow-repo-cleanup.md` (this file)

- [ ] **Step 1: Remove local arcade outputs**

```bash
rm -f arcade_health_dashboard.html analysis_v1.ipynb
```

- [ ] **Step 2: Remove old docs (commands above)**

- [ ] **Step 3: Remove leftover `dataflow/` directory entirely**

```bash
rm -rf dataflow/
test ! -e dataflow
```

Expected: `dataflow` path does not exist.

- [ ] **Step 4: Confirm kept docs exist**

```bash
test -f docs/superpowers/specs/2026-07-16-dataflow-repo-cleanup-design.md
test -f docs/superpowers/plans/2026-07-16-dataflow-repo-cleanup.md
ls docs/superpowers/specs/
ls docs/superpowers/plans/
```

Expected: only the 2026-07-16 cleanup design/plan files remain (plus this plan once committed).

---

### Task 5: Fix README and cursor rule for root layout

**Files:**
- Modify: `README.md`
- Modify: `.cursor/rules/dataflow-workflow.mdc`

**Interfaces:**
- Consumes: files already at root from Task 2
- Produces: docs that describe running from repo root with no `cd dataflow`

- [ ] **Step 1: Update README path references**

In `README.md`, apply these exact content fixes:

1. In **How to produce it** and **Quick start**, remove the `cd dataflow` line so blocks start with `python3 -m venv .venv` (or equivalent) at repo root.
2. Change the **Project layout** tree from:

```
dataflow/
├── README.md
...
```

to:

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

3. Remove or rewrite the **Related** section that says `Part of the [retirement](../) repo.` — the repo root *is* dataflow now. Replace with a single line such as:

```markdown
## Related

This repository is the portfolio catalog **data collection** handoff. Consuming apps should ingest `data/merged_live_and_ie_published.csv` (or `poc/` offline).
```

4. Search the whole README for remaining `dataflow/` path instructions:

```bash
rg -n 'cd dataflow|dataflow/' README.md
```

Expected: no `cd dataflow`; any remaining `dataflow` word should only be the product name in titles (e.g. “Dataflow — …”), not a directory path. The User-Agent note is in Python, not README.

- [ ] **Step 2: Update cursor rule wording**

In `.cursor/rules/dataflow-workflow.mdc`, change the opening paragraph from referring to `This project (\`dataflow/\`)` to:

```markdown
This repository **collects and merges** Red Hat portfolio catalog metadata for other applications to consume. Evaluation / recommendation belongs in the consuming app; the local advisor is optional smoke-test only.
```

Keep the pipeline steps and conventions unchanged (they already use root-relative script names like `IE_metadata_datapull.py`).

- [ ] **Step 3: Verify no stale nested-path docs**

```bash
rg -n 'cd dataflow|`dataflow/`' README.md .cursor/rules/dataflow-workflow.mdc
```

Expected: no matches.

- [ ] **Step 4: Commit all remaining cleanup changes**

```bash
git add -A
git status
# Review: should NOT stage data/*.csv or .venv
git commit -m "$(cat <<'EOF'
Make the repository dataflow-only at the root.

EOF
)"
```

If Tasks 2–5 were left uncommitted, this single commit should include: promoted files, deleted arcade files, new `.gitignore`, `data/.gitkeep`, README/rule updates, and old-doc deletions.

---

### Task 6: Verification

**Files:**
- Test: working tree layout and imports (no new test files required — arcade tests were deleted by design)

- [ ] **Step 1: Layout checks**

```bash
test -f live_ie_published_datapull.py
test -f merge_palist_requestmaster.py
test -f catalog_fields.py
test -f requirements.txt
test -f data/.gitkeep
test -d advisor
test -d poc
test -f poc/merged_live_and_ie_published.csv
test ! -e dataflow
test ! -e build_dashboard.py
test ! -e scoring.py
test ! -e render.py
test ! -e arcade_health_dashboard.html
```

Expected: all `test` commands exit 0.

- [ ] **Step 2: Git hygiene checks**

```bash
git ls-files dataflow/
git ls-files | rg 'build_dashboard|scoring\.py|render\.py|data_to_csv|static/|tests/'
git status
```

Expected:
- First command empty
- Second command empty
- Status clean except intentional local ignored files under `data/` / `.venv`

- [ ] **Step 3: Offline sample path still works**

```bash
mkdir -p data
cp poc/merged_live_and_ie_published.csv data/
python3 -c "import catalog_fields; print('ok')"
```

Expected: `ok`. CSV present at `data/merged_live_and_ie_published.csv` (ignored by git).

- [ ] **Step 4: Optional merge dry-run if local pulls exist**

Only if `data/request_master.csv` and `data/palist.csv` exist:

```bash
python3 live_ie_published_datapull.py --skip-pull
```

Expected: refreshes `data/merged_live_and_ie_published.csv` without network errors. If CSVs missing, skip this step.

---

## Self-review checklist (plan author)

1. **Spec coverage:** Promote to root ✓; delete arcade ✓; delete old docs ✓; keep cleanup design+plan ✓; merge gitignore + `.gitkeep` ✓; README/rule path fixes ✓; no pipeline logic changes ✓; success criteria covered in Task 6 ✓.
2. **Placeholders:** None — commands and file contents are concrete.
3. **Consistency:** Temp `.gitignore.dataflow-tmp` → final `.gitignore` flow is explicit; single final commit preferred at Task 5.

## Execution notes

- Prefer **one** cleanup commit at end of Task 5 (defer Task 2 Step 5).
- Do not `git add data/*.csv`.
- Do not force-push; do not rename the remote.
