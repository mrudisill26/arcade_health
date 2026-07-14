# Arcade Health Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a scoring pipeline and interactive HTML dashboard that assigns every arcade a health score (0–100), lifecycle status (Healthy/Watch/Refresh/Replace/Retire), and surfaces ownership, deployment, and engagement data in a filterable single-file HTML dashboard.

**Architecture:** Python scoring pipeline reads two CSVs (Databricks engagement + Request Master metadata), merges them, computes a composite health score from four weighted dimensions (engagement 35%, freshness 25%, metadata 20%, sales 20%), writes scored JSON, then renders a self-contained interactive HTML file using Tabulator.js. Entry point supports optional data refresh via existing `data_to_csv_v1.py`.

**Tech Stack:** Python 3.14, pandas, numpy, pytest. HTML/CSS/JS with Tabulator.js (embedded inline). No web framework.

## Global Constraints

- Python 3.14 with existing venv at `.venv/`
- All file paths relative to project root `/Users/mrudisill/Projects/retirement/`
- Data files live in `data/` — never commit raw CSVs
- Databricks CSV column for arcade identity: `arcade_display_key`
- Request Master join column: `Join Key` (matches `arcade_display_key`)
- CTA click data is zeros from March 2026 onward — only use pre-March 2026 data for CTA metrics
- Sales attribution exists for only ~65 of ~563 arcades — neutral score for arcades without it
- Activate venv before all commands: `source .venv/bin/activate`

---

### Task 1: Project Setup and Scoring — Data Loading & Merging

**Files:**
- Create: `scoring.py`
- Create: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `data/databricksaracade.csv`, `data/request_master.csv` (on disk)
- Produces:
  - `load_engagement_data(path: str) -> pd.DataFrame` — loads Databricks CSV with `date_ym` parsed as datetime
  - `load_request_master(path: str) -> pd.DataFrame` — loads Request Master CSV
  - `merge_datasets(engagement: pd.DataFrame, request_master: pd.DataFrame) -> pd.DataFrame` — merges on exact `Join Key` match + normalized fallback, returns one row per unique `arcade_display_key` with aggregated engagement metrics and RM metadata columns

- [ ] **Step 1: Install pytest**

```bash
source .venv/bin/activate
pip install pytest
```

- [ ] **Step 2: Write failing tests for data loading and merging**

Create `tests/test_scoring.py`:

```python
import pandas as pd
import numpy as np
import pytest
from scoring import load_engagement_data, load_request_master, merge_datasets


@pytest.fixture
def sample_engagement_csv(tmp_path):
    csv_path = tmp_path / "engagement.csv"
    csv_path.write_text(
        "arcade_display_key,arcade_name_raw,arcade_year,arcade_month,date_ym,"
        "arcade_distinct_arcade_ids,arcade_players_sum,arcade_completers_sum,"
        "arcade_cta_clicks_sum,arcade_completion_rate_avg,arcade_cta_click_rate_avg,"
        "master_product,master_marketing_program,master_tdp,master_verticals,"
        "master_rhac_page,master_event,master_language,"
        "sales_uv_unique,sales_mt_uv_unique,sales_inquiries_sum,sales_contacts_sum,"
        "sales_mt_opps_sum,sales_mt_wins_sum,sales_mt_opp_value_syb_sum,"
        "sales_mt_won_value_syb_sum,sales_distinct_pages_touched\n"
        "Arcade Alpha | Business Intro,Arcade Alpha | Business Intro,2026,4,2026-04-01,"
        "1,100,50,10,50.0,10.0,OpenShift,,Virtualization,,,,English,"
        "5,3,2,1,1,0.5,50000,25000,1\n"
        "Arcade Alpha | Business Intro,Arcade Alpha | Business Intro,2026,5,2026-05-01,"
        "1,80,40,0,50.0,0.0,OpenShift,,Virtualization,,,,English,"
        "4,2,1,1,0.5,0.2,30000,15000,1\n"
        "Arcade Alpha | Business Intro,Arcade Alpha | Business Intro,2026,6,2026-06-01,"
        "1,90,45,0,50.0,0.0,OpenShift,,Virtualization,,,,English,"
        ",,,,,,,\n"
        "Arcade Beta,Arcade Beta,2026,4,2026-04-01,"
        "1,10,5,0,50.0,0.0,,,AI Platform,,,,,"
        ",,,,,,,\n"
        "Arcade Beta,Arcade Beta,2026,5,2026-05-01,"
        "1,12,6,0,50.0,0.0,,,AI Platform,,,,,"
        ",,,,,,,\n"
        "Arcade Beta,Arcade Beta,2026,6,2026-06-01,"
        "1,8,4,0,50.0,0.0,,,AI Platform,,,,,"
        ",,,,,,,\n"
    )
    return str(csv_path)


@pytest.fixture
def sample_rm_csv(tmp_path):
    csv_path = tmp_path / "request_master.csv"
    csv_path.write_text(
        '"Final Demo Title","Join Key","Creator Name","Creator Team",'
        '"Final Content Type","Quarter","CTALink","Drupal Page URL",'
        '"RHAC page","Public Site Link","Primary Product","TDP",'
        '"Destination Channels","Demo Description"\n'
        '"Arcade Alpha","Arcade Alpha | Business Intro","Alice Smith","Team A",'
        '"Business Intro","CY26Q1","https://cta.example.com","https://drupal.example.com",'
        '"https://rhac.example.com","https://public.example.com","OpenShift","Virtualization",'
        '"Web, Social","A demo about OpenShift"\n'
    )
    return str(csv_path)


def test_load_engagement_data(sample_engagement_csv):
    df = load_engagement_data(sample_engagement_csv)
    assert len(df) == 6
    assert pd.api.types.is_datetime64_any_dtype(df["date_ym"])
    assert "arcade_display_key" in df.columns


def test_load_request_master(sample_rm_csv):
    df = load_request_master(sample_rm_csv)
    assert len(df) == 1
    assert "Join Key" in df.columns
    assert "Creator Name" in df.columns


def test_merge_datasets_exact_match(sample_engagement_csv, sample_rm_csv):
    eng = load_engagement_data(sample_engagement_csv)
    rm = load_request_master(sample_rm_csv)
    merged = merge_datasets(eng, rm)
    assert len(merged) == 2  # two unique arcades
    alpha = merged[merged["arcade_display_key"] == "Arcade Alpha | Business Intro"].iloc[0]
    assert alpha["owner"] == "Alice Smith"
    assert alpha["team"] == "Team A"
    assert alpha["has_rm_match"] is True


def test_merge_datasets_unmatched_arcade(sample_engagement_csv, sample_rm_csv):
    eng = load_engagement_data(sample_engagement_csv)
    rm = load_request_master(sample_rm_csv)
    merged = merge_datasets(eng, rm)
    beta = merged[merged["arcade_display_key"] == "Arcade Beta"].iloc[0]
    assert beta["has_rm_match"] is False
    assert pd.isna(beta["owner"]) or beta["owner"] == ""
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
source .venv/bin/activate
pytest tests/test_scoring.py -v
```

Expected: FAIL — `ImportError: cannot import name 'load_engagement_data' from 'scoring'`

- [ ] **Step 4: Implement data loading and merging in `scoring.py`**

Create `scoring.py`:

```python
import re
import json
from datetime import datetime

import numpy as np
import pandas as pd


def load_engagement_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date_ym"])


def load_request_master(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def _normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = re.sub(
        r"^\((?:copy|Autoplay version|Presenting|auto-play|New|ADS|Autoplay)\)\s*",
        "",
        s,
    )
    s = re.sub(r"\s*\|\s*Technical Walkthrough$", "", s)
    s = re.sub(r"^[A-Za-z]+-CY\d+Q\d+-\s*", "", s)
    return s.strip()


RM_COLS = [
    "Final Demo Title",
    "Join Key",
    "Final Content Type",
    "Creator Name",
    "Creator Team",
    "Primary Product",
    "Quarter",
    "CTALink",
    "Drupal Page URL",
    "RHAC page",
    "Public Site Link",
    "Destination Channels",
    "Demo Description",
]


def merge_datasets(
    engagement: pd.DataFrame, request_master: pd.DataFrame
) -> pd.DataFrame:
    rm = request_master[
        [c for c in RM_COLS if c in request_master.columns]
    ].copy()

    arcade_agg = engagement.groupby("arcade_display_key").agg(
        total_players=("arcade_players_sum", "sum"),
        total_completers=("arcade_completers_sum", "sum"),
        total_cta_clicks=("arcade_cta_clicks_sum", "sum"),
        avg_completion_rate=("arcade_completion_rate_avg", "mean"),
        avg_cta_click_rate=("arcade_cta_click_rate_avg", "mean"),
        months_active=("date_ym", "nunique"),
        first_month=("date_ym", "min"),
        last_month=("date_ym", "max"),
        tdp=("master_tdp", "first"),
        product=("master_product", "first"),
    ).reset_index()

    # Compute recent 3-month metrics
    max_date = engagement["date_ym"].max()
    cutoff_3mo = max_date - pd.DateOffset(months=2)
    recent = engagement[engagement["date_ym"] >= cutoff_3mo]
    recent_agg = recent.groupby("arcade_display_key").agg(
        recent_3mo_players=("arcade_players_sum", "sum"),
        recent_3mo_completers=("arcade_completers_sum", "sum"),
        recent_3mo_completion_rate=("arcade_completion_rate_avg", "mean"),
    ).reset_index()
    arcade_agg = arcade_agg.merge(recent_agg, on="arcade_display_key", how="left")
    arcade_agg["recent_3mo_avg"] = (arcade_agg["recent_3mo_players"] / 3).round(1)
    arcade_agg["alltime_monthly_avg"] = (
        arcade_agg["total_players"] / arcade_agg["months_active"]
    ).round(1)

    # Compute trend
    arcade_agg["trend_ratio"] = (
        arcade_agg["recent_3mo_avg"] / arcade_agg["alltime_monthly_avg"].replace(0, np.nan)
    )
    arcade_agg["trend"] = pd.cut(
        arcade_agg["trend_ratio"],
        bins=[-np.inf, 0.5, 0.8, 1.2, 2.0, np.inf],
        labels=["declining_fast", "declining", "stable", "growing", "growing_fast"],
    )

    # Compute consecutive zero months (< 3 players) from most recent month backwards
    def _consecutive_zero_months(group):
        sorted_g = group.sort_values("date_ym", ascending=False)
        count = 0
        for _, row in sorted_g.iterrows():
            if row["arcade_players_sum"] < 3:
                count += 1
            else:
                break
        return count

    zero_months = (
        engagement.groupby("arcade_display_key")
        .apply(_consecutive_zero_months, include_groups=False)
        .rename("consecutive_zero_months")
        .reset_index()
    )
    arcade_agg = arcade_agg.merge(zero_months, on="arcade_display_key", how="left")

    # Sales aggregation
    sales_cols_present = "sales_uv_unique" in engagement.columns
    if sales_cols_present:
        sales = engagement[engagement["sales_uv_unique"].notna()]
        if len(sales) > 0:
            sales_agg = sales.groupby("arcade_display_key").agg(
                total_opp_value=("sales_mt_opp_value_syb_sum", "sum"),
                total_won_value=("sales_mt_won_value_syb_sum", "sum"),
                total_opps=("sales_mt_opps_sum", "sum"),
                total_wins=("sales_mt_wins_sum", "sum"),
            ).reset_index()
            sales_agg["has_sales_data"] = True
            arcade_agg = arcade_agg.merge(
                sales_agg, on="arcade_display_key", how="left"
            )
            arcade_agg["has_sales_data"] = arcade_agg["has_sales_data"].fillna(False)
        else:
            arcade_agg["has_sales_data"] = False
            for c in ["total_opp_value", "total_won_value", "total_opps", "total_wins"]:
                arcade_agg[c] = np.nan
    else:
        arcade_agg["has_sales_data"] = False
        for c in ["total_opp_value", "total_won_value", "total_opps", "total_wins"]:
            arcade_agg[c] = np.nan

    # CTA click rate (pre-March 2026 only)
    pre_mar26 = engagement[engagement["date_ym"] < "2026-03-01"]
    if len(pre_mar26) > 0:
        cta_agg = pre_mar26.groupby("arcade_display_key").agg(
            pre_mar26_cta_rate=("arcade_cta_click_rate_avg", "mean"),
        ).reset_index()
        arcade_agg = arcade_agg.merge(cta_agg, on="arcade_display_key", how="left")
    else:
        arcade_agg["pre_mar26_cta_rate"] = np.nan

    # --- Merge with Request Master ---
    # Pass 1: exact match on Join Key
    merged = arcade_agg.merge(rm, left_on="arcade_display_key", right_on="Join Key", how="left")
    pass1_matched = set(merged.loc[merged["Final Demo Title"].notna(), "Join Key"])

    # Pass 2: normalized fallback
    rm_remaining = rm[~rm["Join Key"].isin(pass1_matched)].copy()
    rm_remaining["_norm"] = rm_remaining["Final Demo Title"].apply(_normalize_name)
    norm_lookup = rm_remaining.drop_duplicates("_norm").set_index("_norm")

    for idx in merged.index:
        if pd.notna(merged.loc[idx, "Final Demo Title"]):
            continue
        norm = _normalize_name(merged.loc[idx, "arcade_display_key"])
        if norm and norm in norm_lookup.index:
            for col in rm.columns:
                if col in norm_lookup.columns or col == norm_lookup.index.name:
                    continue
                if col in merged.columns:
                    merged.loc[idx, col] = norm_lookup.loc[norm, col]

    # Flatten to standard column names
    merged["has_rm_match"] = merged["Final Demo Title"].notna()
    merged["owner"] = merged.get("Creator Name", pd.Series(dtype=str))
    merged["team"] = merged.get("Creator Team", pd.Series(dtype=str))
    merged["content_type"] = merged.get("Final Content Type", pd.Series(dtype=str))
    merged["quarter_created"] = merged.get("Quarter", pd.Series(dtype=str))
    merged["cta_link"] = merged.get("CTALink", pd.Series(dtype=str))
    merged["drupal_url"] = merged.get("Drupal Page URL", pd.Series(dtype=str))
    merged["rhac_url"] = merged.get("RHAC page", pd.Series(dtype=str))
    merged["public_site"] = merged.get("Public Site Link", pd.Series(dtype=str))
    merged["description"] = merged.get("Demo Description", pd.Series(dtype=str))
    merged["destination_channels"] = merged.get("Destination Channels", pd.Series(dtype=str))

    return merged
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
source .venv/bin/activate
pytest tests/test_scoring.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scoring.py tests/test_scoring.py
git commit -m "feat: add data loading and merging for arcade health scoring"
```

---

### Task 2: Scoring — Four Dimension Scores and Composite Health Score

**Files:**
- Modify: `scoring.py` (add scoring functions)
- Modify: `tests/test_scoring.py` (add scoring tests)

**Interfaces:**
- Consumes: `merge_datasets(...)` output DataFrame from Task 1
- Produces:
  - `score_engagement(merged: pd.DataFrame) -> pd.Series` — returns 0–100 engagement score per arcade
  - `score_freshness(merged: pd.DataFrame) -> pd.Series` — returns 0–100 freshness score per arcade
  - `score_metadata(merged: pd.DataFrame) -> pd.Series` — returns 0–100 metadata completeness score per arcade
  - `score_sales(merged: pd.DataFrame) -> pd.Series` — returns 0–100 sales score per arcade
  - `compute_health_scores(merged: pd.DataFrame) -> pd.DataFrame` — adds `score_engagement`, `score_freshness`, `score_metadata`, `score_sales`, `health_score`, and `status` columns

- [ ] **Step 1: Write failing tests for each scoring dimension**

Append to `tests/test_scoring.py`:

```python
from scoring import (
    score_engagement,
    score_freshness,
    score_metadata,
    score_sales,
    compute_health_scores,
)


@pytest.fixture
def merged_df(sample_engagement_csv, sample_rm_csv):
    eng = load_engagement_data(sample_engagement_csv)
    rm = load_request_master(sample_rm_csv)
    return merge_datasets(eng, rm)


def test_score_engagement_returns_0_to_100(merged_df):
    scores = score_engagement(merged_df)
    assert len(scores) == len(merged_df)
    assert scores.between(0, 100).all()


def test_score_freshness_returns_0_to_100(merged_df):
    scores = score_freshness(merged_df)
    assert len(scores) == len(merged_df)
    assert scores.between(0, 100).all()


def test_score_metadata_full_match_higher_than_no_match(merged_df):
    scores = score_metadata(merged_df)
    alpha = scores[merged_df["arcade_display_key"] == "Arcade Alpha | Business Intro"].iloc[0]
    beta = scores[merged_df["arcade_display_key"] == "Arcade Beta"].iloc[0]
    assert alpha > beta  # Alpha has RM match, Beta does not


def test_score_sales_neutral_when_no_data(merged_df):
    scores = score_sales(merged_df)
    beta = scores[merged_df["arcade_display_key"] == "Arcade Beta"].iloc[0]
    assert beta == 50  # Neutral score for no sales data


def test_compute_health_scores_adds_all_columns(merged_df):
    result = compute_health_scores(merged_df)
    assert "health_score" in result.columns
    assert "status" in result.columns
    assert "score_engagement" in result.columns
    assert "score_freshness" in result.columns
    assert "score_metadata" in result.columns
    assert "score_sales" in result.columns
    assert result["health_score"].between(0, 100).all()
    assert result["status"].isin(["Healthy", "Watch", "Refresh", "Replace", "Retire"]).all()


def test_lifecycle_status_thresholds(merged_df):
    result = compute_health_scores(merged_df)
    for _, row in result.iterrows():
        score = row["health_score"]
        status = row["status"]
        if score >= 80:
            assert status == "Healthy"
        elif score >= 60:
            assert status == "Watch"
        elif score >= 40:
            assert status == "Refresh"
        elif score >= 20:
            assert status == "Replace"
        else:
            assert status == "Retire"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate
pytest tests/test_scoring.py -v -k "score"
```

Expected: FAIL — `ImportError: cannot import name 'score_engagement'`

- [ ] **Step 3: Implement the four scoring functions and composite**

Append to `scoring.py`:

```python
WEIGHTS = {
    "engagement": 0.35,
    "freshness": 0.25,
    "metadata": 0.20,
    "sales": 0.20,
}


def score_engagement(df: pd.DataFrame) -> pd.Series:
    scores = pd.Series(0.0, index=df.index)

    # Trend ratio component (40% of engagement score)
    ratio = df["trend_ratio"].fillna(0)
    trend_score = pd.Series(0.0, index=df.index)
    trend_score = np.where(ratio >= 1.0, 100, trend_score)
    trend_score = np.where(
        (ratio >= 0.5) & (ratio < 1.0), ratio * 100, trend_score
    )
    trend_score = np.where(ratio < 0.5, ratio * 60, trend_score)
    trend_score = pd.Series(trend_score, index=df.index)

    # Completion rate vs TDP peer group (30% of engagement score)
    tdp_medians = df.groupby("tdp")["recent_3mo_completion_rate"].transform("median")
    completion_ratio = (
        df["recent_3mo_completion_rate"] / tdp_medians.replace(0, np.nan)
    ).fillna(0.5)
    completion_score = np.clip(completion_ratio * 100, 0, 100)

    # Recent absolute players vs TDP peer group (20% of engagement score)
    tdp_player_medians = df.groupby("tdp")["recent_3mo_avg"].transform("median")
    player_ratio = (
        df["recent_3mo_avg"] / tdp_player_medians.replace(0, np.nan)
    ).fillna(0.5)
    player_score = np.clip(player_ratio * 50, 0, 100)  # 1x median = 50, 2x = 100

    # Zero month penalty (10% of engagement score)
    zero_penalty = np.clip(100 - df["consecutive_zero_months"].fillna(0) * 33, 0, 100)

    scores = (
        trend_score * 0.4
        + completion_score * 0.3
        + player_score * 0.2
        + zero_penalty * 0.1
    )
    return np.clip(scores, 0, 100).round(1)


def _quarter_to_date(q: str) -> datetime | None:
    """Convert 'CY25Q1' to a datetime (first month of that quarter)."""
    if not isinstance(q, str):
        return None
    m = re.match(r"CY(\d{2})Q([1-4])", q)
    if not m:
        return None
    year = 2000 + int(m.group(1))
    quarter = int(m.group(2))
    month = (quarter - 1) * 3 + 1
    return datetime(year, month, 1)


def _extract_version_age_penalty(name: str, now: datetime) -> float:
    """Detect version/date references in arcade name and penalize old ones."""
    if not isinstance(name, str):
        return 0.0

    # Match CY24Q3 style references
    cy_match = re.search(r"CY(\d{2})Q([1-4])", name)
    if cy_match:
        ref_date = _quarter_to_date(cy_match.group(0))
        if ref_date:
            months_old = (now.year - ref_date.year) * 12 + (now.month - ref_date.month)
            if months_old > 18:
                return 30.0
            elif months_old > 12:
                return 20.0
            elif months_old > 6:
                return 10.0
        return 0.0

    # Match version numbers like "2.4", "2.5", "10 Beta"
    ver_match = re.search(r"\b(\d+\.\d+)\b", name)
    if ver_match:
        return 10.0  # mild penalty — we can't verify if it's current

    return 0.0


def score_freshness(df: pd.DataFrame) -> pd.Series:
    now = datetime.now()
    scores = pd.Series(100.0, index=df.index)

    for idx in df.index:
        quarter = df.loc[idx, "quarter_created"] if "quarter_created" in df.columns else None
        first_month = df.loc[idx, "first_month"] if "first_month" in df.columns else None

        # Determine creation date
        creation_date = _quarter_to_date(quarter) if isinstance(quarter, str) else None
        if creation_date is None and pd.notna(first_month):
            creation_date = pd.Timestamp(first_month).to_pydatetime()

        if creation_date is None:
            scores.iloc[idx] = 40.0  # unknown age = moderate penalty
            continue

        age_months = (now.year - creation_date.year) * 12 + (now.month - creation_date.month)

        # Age scoring: full marks < 12 months, linear decay 12-18, steep after 18
        if age_months <= 12:
            age_score = 100.0
        elif age_months <= 18:
            age_score = 100.0 - ((age_months - 12) / 6) * 40
        else:
            age_score = max(60.0 - (age_months - 18) * 5, 10.0)

        # Version reference penalty
        version_penalty = _extract_version_age_penalty(
            df.loc[idx, "arcade_display_key"], now
        )

        scores.iloc[idx] = max(age_score - version_penalty, 0)

    return scores.round(1)


def score_metadata(df: pd.DataFrame) -> pd.Series:
    max_per_item = 20.0  # 5 items, each worth 20 points

    has_rm = df["has_rm_match"].astype(float) * max_per_item
    has_owner = df["owner"].notna() & (df["owner"] != "")
    has_owner = has_owner.astype(float) * max_per_item
    has_cta = df["cta_link"].notna() & (df["cta_link"] != "")
    has_cta = has_cta.astype(float) * max_per_item
    has_product = (df["product"].notna() & (df["product"] != "")) | (
        df["tdp"].notna() & (df["tdp"] != "")
    )
    has_product = has_product.astype(float) * max_per_item
    has_url = (
        (df["drupal_url"].notna() & (df["drupal_url"] != ""))
        | (df["rhac_url"].notna() & (df["rhac_url"] != ""))
        | (df["public_site"].notna() & (df["public_site"] != ""))
    )
    has_url = has_url.astype(float) * max_per_item

    raw = has_rm + has_owner + has_cta + has_product + has_url

    # Cap at 40% if no RM match
    no_rm_mask = ~df["has_rm_match"]
    raw[no_rm_mask] = np.minimum(raw[no_rm_mask], 40.0)

    return raw.round(1)


def score_sales(df: pd.DataFrame) -> pd.Series:
    scores = pd.Series(50.0, index=df.index)  # default: neutral

    has_sales = df["has_sales_data"] == True
    if not has_sales.any():
        return scores

    sales_df = df[has_sales]

    # Pipeline value per player, scored relative to peer group
    opp_per_player = (
        sales_df["total_opp_value"] / sales_df["total_players"].replace(0, np.nan)
    ).fillna(0)
    median_opp = opp_per_player.median()
    if median_opp > 0:
        relative = (opp_per_player / median_opp).clip(0, 3)
        sales_score = (relative / 3 * 70 + 30).round(1)  # range 30–100
    else:
        sales_score = pd.Series(50.0, index=sales_df.index)

    # CTA click rate bonus (up to +10 points, using pre-March 2026 data)
    if "pre_mar26_cta_rate" in df.columns:
        cta_bonus = sales_df["pre_mar26_cta_rate"].fillna(0).clip(0, 50) / 50 * 10
        sales_score = (sales_score + cta_bonus).clip(0, 100)

    scores[has_sales] = sales_score

    return scores.round(1)


def compute_health_scores(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["score_engagement"] = score_engagement(result)
    result["score_freshness"] = score_freshness(result)
    result["score_metadata"] = score_metadata(result)
    result["score_sales"] = score_sales(result)

    result["health_score"] = (
        result["score_engagement"] * WEIGHTS["engagement"]
        + result["score_freshness"] * WEIGHTS["freshness"]
        + result["score_metadata"] * WEIGHTS["metadata"]
        + result["score_sales"] * WEIGHTS["sales"]
    ).round(1)

    result["health_score"] = result["health_score"].clip(0, 100)

    result["status"] = pd.cut(
        result["health_score"],
        bins=[-1, 19.999, 39.999, 59.999, 79.999, 100],
        labels=["Retire", "Replace", "Refresh", "Watch", "Healthy"],
    )

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate
pytest tests/test_scoring.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scoring.py tests/test_scoring.py
git commit -m "feat: add four-dimension health scoring model with composite score"
```

---

### Task 3: Scoring — JSON Export

**Files:**
- Modify: `scoring.py` (add JSON export function)
- Modify: `tests/test_scoring.py` (add JSON export tests)

**Interfaces:**
- Consumes: `compute_health_scores(...)` output DataFrame from Task 2
- Produces:
  - `export_health_json(scored_df: pd.DataFrame, output_path: str) -> dict` — writes the scored JSON file matching the spec schema, returns the dict

- [ ] **Step 1: Write failing test for JSON export**

Append to `tests/test_scoring.py`:

```python
import json
from scoring import export_health_json


def test_export_health_json_structure(merged_df, tmp_path):
    scored = compute_health_scores(merged_df)
    output_path = str(tmp_path / "health.json")
    result = export_health_json(scored, output_path)

    assert "generated_at" in result
    assert "summary" in result
    assert "arcades" in result
    assert result["summary"]["total_arcades"] == 2
    assert set(result["summary"]["by_status"].keys()) <= {
        "Healthy", "Watch", "Refresh", "Replace", "Retire"
    }

    arcade = result["arcades"][0]
    assert "name" in arcade
    assert "health_score" in arcade
    assert "status" in arcade
    assert "scores" in arcade
    assert set(arcade["scores"].keys()) == {
        "engagement", "freshness", "metadata", "sales"
    }
    assert "engagement" in arcade
    assert "metadata" in arcade
    assert "deployment" in arcade
    assert "sales" in arcade


def test_export_health_json_writes_file(merged_df, tmp_path):
    scored = compute_health_scores(merged_df)
    output_path = str(tmp_path / "health.json")
    export_health_json(scored, output_path)

    with open(output_path) as f:
        data = json.load(f)
    assert data["summary"]["total_arcades"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate
pytest tests/test_scoring.py::test_export_health_json_structure -v
```

Expected: FAIL — `ImportError: cannot import name 'export_health_json'`

- [ ] **Step 3: Implement JSON export**

Append to `scoring.py`:

```python
def _safe_str(val) -> str:
    if pd.isna(val):
        return ""
    return str(val)


def _safe_float(val) -> float | None:
    if pd.isna(val):
        return None
    return round(float(val), 1)


def _safe_int(val) -> int | None:
    if pd.isna(val):
        return None
    return int(val)


def export_health_json(scored_df: pd.DataFrame, output_path: str) -> dict:
    status_counts = scored_df["status"].value_counts().to_dict()
    for s in ["Healthy", "Watch", "Refresh", "Replace", "Retire"]:
        status_counts.setdefault(s, 0)

    unowned = int(
        ((scored_df["owner"].isna()) | (scored_df["owner"] == "")).sum()
    )

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total_arcades": len(scored_df),
            "by_status": {k: int(v) for k, v in status_counts.items()},
            "unowned_count": unowned,
            "avg_health_score": round(float(scored_df["health_score"].mean()), 1),
        },
        "arcades": [],
    }

    for _, row in scored_df.iterrows():
        arcade = {
            "name": row["arcade_display_key"],
            "health_score": _safe_float(row["health_score"]),
            "status": str(row["status"]),
            "scores": {
                "engagement": _safe_float(row["score_engagement"]),
                "freshness": _safe_float(row["score_freshness"]),
                "metadata": _safe_float(row["score_metadata"]),
                "sales": _safe_float(row["score_sales"]),
            },
            "engagement": {
                "total_players": _safe_int(row.get("total_players")),
                "recent_3mo_avg": _safe_float(row.get("recent_3mo_avg")),
                "alltime_monthly_avg": _safe_float(row.get("alltime_monthly_avg")),
                "trend": _safe_str(row.get("trend")),
                "completion_rate": _safe_float(row.get("avg_completion_rate")),
                "months_active": _safe_int(row.get("months_active")),
            },
            "metadata": {
                "has_rm_match": bool(row.get("has_rm_match", False)),
                "owner": _safe_str(row.get("owner")),
                "team": _safe_str(row.get("team")),
                "product": _safe_str(row.get("product")),
                "tdp": _safe_str(row.get("tdp")),
                "content_type": _safe_str(row.get("content_type")),
                "quarter_created": _safe_str(row.get("quarter_created")),
                "has_cta": bool(
                    pd.notna(row.get("cta_link")) and row.get("cta_link") != ""
                ),
                "has_deployment_url": bool(
                    (pd.notna(row.get("drupal_url")) and row.get("drupal_url") != "")
                    or (pd.notna(row.get("rhac_url")) and row.get("rhac_url") != "")
                    or (pd.notna(row.get("public_site")) and row.get("public_site") != "")
                ),
            },
            "deployment": {
                "drupal_url": _safe_str(row.get("drupal_url")),
                "rhac_url": _safe_str(row.get("rhac_url")),
                "public_site": _safe_str(row.get("public_site")),
                "cta_link": _safe_str(row.get("cta_link")),
            },
            "sales": {
                "has_data": bool(row.get("has_sales_data", False)),
                "total_opp_value": _safe_float(row.get("total_opp_value")),
                "total_won_value": _safe_float(row.get("total_won_value")),
                "opp_value_per_player": _safe_float(
                    row.get("total_opp_value", 0) / row.get("total_players", 1)
                    if row.get("total_players", 0) > 0 and pd.notna(row.get("total_opp_value"))
                    else None
                ),
            },
        }
        result["arcades"].append(arcade)

    result["arcades"].sort(key=lambda a: a["health_score"] or 0, reverse=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate
pytest tests/test_scoring.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scoring.py tests/test_scoring.py
git commit -m "feat: add JSON export for scored arcade health data"
```

---

### Task 4: HTML Dashboard Renderer

**Files:**
- Create: `render.py`
- Create: `tests/test_render.py`

**Interfaces:**
- Consumes: `data/arcade_health.json` (or any path to a JSON file matching the spec schema)
- Produces:
  - `render_dashboard(json_path: str, output_path: str) -> str` — reads the scored JSON, produces a self-contained HTML file, returns the output path

- [ ] **Step 1: Write failing tests for HTML rendering**

Create `tests/test_render.py`:

```python
import json
import pytest
from render import render_dashboard


@pytest.fixture
def sample_health_json(tmp_path):
    data = {
        "generated_at": "2026-07-14T10:00:00",
        "summary": {
            "total_arcades": 3,
            "by_status": {"Healthy": 1, "Watch": 1, "Refresh": 0, "Replace": 0, "Retire": 1},
            "unowned_count": 1,
            "avg_health_score": 52.0,
        },
        "arcades": [
            {
                "name": "Arcade Alpha",
                "health_score": 85.0,
                "status": "Healthy",
                "scores": {"engagement": 90, "freshness": 80, "metadata": 85, "sales": 78},
                "engagement": {
                    "total_players": 5000,
                    "recent_3mo_avg": 300.0,
                    "alltime_monthly_avg": 280.0,
                    "trend": "growing",
                    "completion_rate": 45.2,
                    "months_active": 18,
                },
                "metadata": {
                    "has_rm_match": True,
                    "owner": "Alice Smith",
                    "team": "Team A",
                    "product": "OpenShift",
                    "tdp": "Virtualization",
                    "content_type": "Business Intro",
                    "quarter_created": "CY25Q1",
                    "has_cta": True,
                    "has_deployment_url": True,
                },
                "deployment": {
                    "drupal_url": "https://drupal.example.com",
                    "rhac_url": "https://rhac.example.com",
                    "public_site": "https://public.example.com",
                    "cta_link": "https://cta.example.com",
                },
                "sales": {
                    "has_data": True,
                    "total_opp_value": 500000.0,
                    "total_won_value": 200000.0,
                    "opp_value_per_player": 100.0,
                },
            },
            {
                "name": "Arcade Beta",
                "health_score": 55.0,
                "status": "Watch",
                "scores": {"engagement": 60, "freshness": 50, "metadata": 60, "sales": 50},
                "engagement": {
                    "total_players": 200,
                    "recent_3mo_avg": 10.0,
                    "alltime_monthly_avg": 12.0,
                    "trend": "declining",
                    "completion_rate": 30.0,
                    "months_active": 12,
                },
                "metadata": {
                    "has_rm_match": True,
                    "owner": "Bob Jones",
                    "team": "Team B",
                    "product": "RHEL",
                    "tdp": "Server/Cloud Operating System",
                    "content_type": "Technical Walkthrough",
                    "quarter_created": "CY24Q4",
                    "has_cta": False,
                    "has_deployment_url": True,
                },
                "deployment": {
                    "drupal_url": "https://drupal2.example.com",
                    "rhac_url": "",
                    "public_site": "",
                    "cta_link": "",
                },
                "sales": {"has_data": False, "total_opp_value": None, "total_won_value": None, "opp_value_per_player": None},
            },
            {
                "name": "Arcade Gamma",
                "health_score": 15.0,
                "status": "Retire",
                "scores": {"engagement": 10, "freshness": 20, "metadata": 20, "sales": 50},
                "engagement": {
                    "total_players": 5,
                    "recent_3mo_avg": 0.0,
                    "alltime_monthly_avg": 1.0,
                    "trend": "declining_fast",
                    "completion_rate": 0.0,
                    "months_active": 6,
                },
                "metadata": {
                    "has_rm_match": False,
                    "owner": "",
                    "team": "",
                    "product": "",
                    "tdp": "AI Platform",
                    "content_type": "",
                    "quarter_created": "",
                    "has_cta": False,
                    "has_deployment_url": False,
                },
                "deployment": {"drupal_url": "", "rhac_url": "", "public_site": "", "cta_link": ""},
                "sales": {"has_data": False, "total_opp_value": None, "total_won_value": None, "opp_value_per_player": None},
            },
        ],
    }
    path = tmp_path / "health.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_render_produces_html_file(sample_health_json, tmp_path):
    output = str(tmp_path / "dashboard.html")
    result = render_dashboard(sample_health_json, output)
    assert result == output
    with open(output) as f:
        html = f.read()
    assert len(html) > 1000


def test_render_html_contains_key_elements(sample_health_json, tmp_path):
    output = str(tmp_path / "dashboard.html")
    render_dashboard(sample_health_json, output)
    with open(output) as f:
        html = f.read()
    assert "Arcade Alpha" in html
    assert "Arcade Gamma" in html
    assert "Healthy" in html
    assert "Retire" in html
    assert "2026-07-14" in html
    assert "tabulator" in html.lower() or "Tabulator" in html


def test_render_html_is_self_contained(sample_health_json, tmp_path):
    output = str(tmp_path / "dashboard.html")
    render_dashboard(sample_health_json, output)
    with open(output) as f:
        html = f.read()
    assert "<style" in html
    assert "<script" in html
    assert "ARCADE_DATA" in html  # embedded JSON variable
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate
pytest tests/test_render.py -v
```

Expected: FAIL — `ImportError: cannot import name 'render_dashboard'`

- [ ] **Step 3: Implement the HTML renderer**

Create `render.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate
pytest tests/test_render.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "feat: add HTML dashboard renderer with Tabulator.js table"
```

---

### Task 5: Entry Point — `build_dashboard.py`

**Files:**
- Create: `build_dashboard.py`
- Create: `tests/test_build_dashboard.py`

**Interfaces:**
- Consumes:
  - `data_to_csv_v1.run()` (existing data pull function)
  - `scoring.load_engagement_data(path)`, `scoring.load_request_master(path)`, `scoring.merge_datasets(eng, rm)`, `scoring.compute_health_scores(merged)`, `scoring.export_health_json(scored, path)` from Tasks 1–3
  - `render.render_dashboard(json_path, output_path)` from Task 4
- Produces: CLI entry point that runs the full pipeline

- [ ] **Step 1: Write failing test for the build pipeline**

Create `tests/test_build_dashboard.py`:

```python
import subprocess
import sys


def test_build_dashboard_skip_pull_help():
    result = subprocess.run(
        [sys.executable, "build_dashboard.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--skip-pull" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate
pytest tests/test_build_dashboard.py -v
```

Expected: FAIL — file not found or missing `--help` flag.

- [ ] **Step 3: Implement `build_dashboard.py`**

Create `build_dashboard.py`:

```python
import argparse
import sys
from pathlib import Path

from scoring import (
    load_engagement_data,
    load_request_master,
    merge_datasets,
    compute_health_scores,
    export_health_json,
)
from render import render_dashboard

DATA_DIR = Path("data")
ENGAGEMENT_CSV = DATA_DIR / "databricksaracade.csv"
REQUEST_MASTER_CSV = DATA_DIR / "request_master.csv"
HEALTH_JSON = DATA_DIR / "arcade_health.json"
DASHBOARD_HTML = Path("arcade_health_dashboard.html")


def main():
    parser = argparse.ArgumentParser(
        description="Build the Arcade Health Dashboard"
    )
    parser.add_argument(
        "--skip-pull",
        action="store_true",
        help="Skip data pull from Databricks/Sheets, use existing CSVs",
    )
    args = parser.parse_args()

    # Stage 1: Data Pull
    if not args.skip_pull:
        print("Stage 1: Pulling fresh data from Databricks and Google Sheets...")
        try:
            from data_to_csv_v1 import run as refresh_data
            refresh_data()
        except Exception as e:
            print(f"Data pull failed: {e}")
            print("Run with --skip-pull to use existing CSVs.")
            sys.exit(1)
    else:
        print("Stage 1: Skipping data pull (using existing CSVs)")

    # Verify CSVs exist
    for path in [ENGAGEMENT_CSV, REQUEST_MASTER_CSV]:
        if not path.exists():
            print(f"Error: {path} not found. Run without --skip-pull to fetch data.")
            sys.exit(1)

    # Stage 2: Score
    print("Stage 2: Computing health scores...")
    engagement = load_engagement_data(str(ENGAGEMENT_CSV))
    rm = load_request_master(str(REQUEST_MASTER_CSV))
    merged = merge_datasets(engagement, rm)
    scored = compute_health_scores(merged)
    result = export_health_json(scored, str(HEALTH_JSON))
    print(f"  Scored {result['summary']['total_arcades']} arcades")
    print(f"  Status breakdown: {result['summary']['by_status']}")
    print(f"  Average health score: {result['summary']['avg_health_score']}")
    print(f"  Saved to {HEALTH_JSON}")

    # Stage 3: Render
    print("Stage 3: Rendering dashboard...")
    output = render_dashboard(str(HEALTH_JSON), str(DASHBOARD_HTML))
    print(f"  Dashboard saved to {output}")
    print()
    print(f"Done! Open {DASHBOARD_HTML} in a browser.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate
pytest tests/test_build_dashboard.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full pipeline with `--skip-pull` against real data**

```bash
source .venv/bin/activate
python build_dashboard.py --skip-pull
```

Expected output:
```
Stage 1: Skipping data pull (using existing CSVs)
Stage 2: Computing health scores...
  Scored 563 arcades
  Status breakdown: {...}
  Average health score: XX.X
  Saved to data/arcade_health.json
Stage 3: Rendering dashboard...
  Dashboard saved to arcade_health_dashboard.html

Done! Open arcade_health_dashboard.html in a browser.
```

- [ ] **Step 6: Open the dashboard in a browser and verify**

```bash
open arcade_health_dashboard.html
```

Verify:
- Summary bar shows correct counts
- Table loads with all arcades
- Sorting works on each column
- Status filter checkboxes filter the table
- TDP and Owner dropdowns filter
- Search narrows by name
- Clicking a row expands the detail view with score bars, deployment links, and sales data
- Unowned arcades show "Unknown" in the owner column

- [ ] **Step 7: Commit**

```bash
git add build_dashboard.py tests/test_build_dashboard.py
git commit -m "feat: add build_dashboard.py entry point for full pipeline"
```

- [ ] **Step 8: Run all tests to verify nothing is broken**

```bash
source .venv/bin/activate
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 9: Final commit with any fixes**

If any tests failed, fix and commit:

```bash
git add -A
git commit -m "fix: address test failures from integration"
```
