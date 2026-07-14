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
    "Demo Description (Gemini generated)",
]

SALES_AGG = {
    "total_sales_uv": ("sales_uv_unique", "sum"),
    "total_sales_mt_uv": ("sales_mt_uv_unique", "sum"),
    "total_inquiries": ("sales_inquiries_sum", "sum"),
    "total_contacts": ("sales_contacts_sum", "sum"),
    "total_opps": ("sales_mt_opps_sum", "sum"),
    "total_wins": ("sales_mt_wins_sum", "sum"),
    "total_opp_value": ("sales_mt_opp_value_syb_sum", "sum"),
    "total_won_value": ("sales_mt_won_value_syb_sum", "sum"),
    "total_pages_touched": ("sales_distinct_pages_touched", "sum"),
}
SALES_METRIC_COLUMNS = list(SALES_AGG.keys()) + ["opp_value_per_player"]

IE_PUBLISHED_STATUS = "IE Published"
IE_RETIRED_STATUS = "IE Retired"
IE_REVIEWED_STATUS = "IE Reviewed"
IE_RECEIVED_STATUS = "IE Received"
CLOSED_STATUS = "Closed"

# Known Request Master Status dropdown values (sheet column "Status")
REQUEST_MASTER_STATUS_ORDER = [
    "IE Open",
    "IE Approved",
    IE_RECEIVED_STATUS,
    IE_REVIEWED_STATUS,
    IE_PUBLISHED_STATUS,
    IE_RETIRED_STATUS,
    CLOSED_STATUS,
]


def find_request_status_column(df: pd.DataFrame) -> str | None:
    """Return the Request Master workflow Status column, not timestamp columns."""
    for col in df.columns:
        if col.strip().lower() == "status":
            return col
    for col in df.columns:
        lower = col.lower()
        if "status" in lower and "timestamp" not in lower:
            return col
    return None


def _find_status_column(df: pd.DataFrame) -> str | None:
    return find_request_status_column(df)


def _normalize_join_key(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


def _normalize_rm_status(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


def summarize_request_master_statuses(request_master: pd.DataFrame) -> dict[str, int]:
    """Count rows per Status dropdown value in the Request Master sheet."""
    status_col = find_request_status_column(request_master)
    if not status_col:
        return {}

    counts = (
        request_master[status_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
        .value_counts()
        .to_dict()
    )
    return {k: int(v) for k, v in counts.items()}


def _build_rm_status_lookups(
    request_master: pd.DataFrame,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Map Join Key and normalized demo title to all Status values on matching RM rows."""
    status_col = find_request_status_column(request_master)
    by_join_key: dict[str, set[str]] = {}
    by_norm_title: dict[str, set[str]] = {}

    if not status_col:
        return {}, {}

    for _, row in request_master.iterrows():
        status = _normalize_rm_status(row.get(status_col))
        if not status:
            continue

        join_key = _normalize_join_key(row.get("Join Key"))
        if join_key:
            by_join_key.setdefault(join_key, set()).add(status)

        title = _normalize_name(row.get("Final Demo Title", ""))
        if title:
            by_norm_title.setdefault(title, set()).add(status)

    return (
        {k: sorted(v) for k, v in by_join_key.items()},
        {k: sorted(v) for k, v in by_norm_title.items()},
    )


def _statuses_for_arcade(
    arcade_key: str,
    by_join_key: dict[str, list[str]],
    by_norm_title: dict[str, list[str]],
) -> list[str]:
    statuses = set(by_join_key.get(arcade_key, []))
    norm = _normalize_name(arcade_key)
    if norm:
        statuses.update(by_norm_title.get(norm, []))
    return sorted(statuses)


def _dedupe_rm_prefer_ie_published(rm: pd.DataFrame, subset: str) -> pd.DataFrame:
    """When multiple RM rows share a join key, keep IE Published for metadata."""
    if subset not in rm.columns or len(rm) == 0:
        return rm

    deduped = rm.copy()
    if "rm_status" not in deduped.columns:
        deduped["rm_status"] = ""

    has_key = deduped[subset].notna() & (
        deduped[subset].astype(str).str.strip() != ""
    )
    with_key = deduped[has_key].copy()
    without_key = deduped[~has_key].copy()

    if len(with_key) > 0:
        with_key["_rm_priority"] = (
            with_key["rm_status"] == IE_PUBLISHED_STATUS
        ).astype(int)
        with_key = with_key.sort_values("_rm_priority", ascending=False)
        with_key = with_key.drop_duplicates(subset=subset, keep="first")
        with_key = with_key.drop(columns=["_rm_priority"])

    return pd.concat([with_key, without_key], ignore_index=True)


def _prepare_request_master(request_master: pd.DataFrame) -> pd.DataFrame:
    rm = request_master.copy()
    status_col = find_request_status_column(rm)
    if status_col:
        rm = rm.rename(columns={status_col: "rm_status"})
    else:
        rm["rm_status"] = ""

    cols = [c for c in RM_COLS if c in rm.columns]
    if "rm_status" not in cols:
        cols.append("rm_status")
    rm = rm[cols].copy()
    return _dedupe_rm_prefer_ie_published(rm, "Join Key")


def merge_datasets(
    engagement: pd.DataFrame, request_master: pd.DataFrame
) -> pd.DataFrame:
    rm = _prepare_request_master(request_master)
    status_by_join_key, status_by_norm_title = _build_rm_status_lookups(request_master)

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
            sales_agg = sales.groupby("arcade_display_key").agg(**SALES_AGG).reset_index()
            sales_agg["has_sales_data"] = True
            arcade_agg = arcade_agg.merge(
                sales_agg, on="arcade_display_key", how="left"
            )
            arcade_agg["has_sales_data"] = arcade_agg["has_sales_data"].fillna(False)
        else:
            arcade_agg["has_sales_data"] = False
            for c in SALES_METRIC_COLUMNS:
                arcade_agg[c] = np.nan
    else:
        arcade_agg["has_sales_data"] = False
        for c in SALES_METRIC_COLUMNS:
            arcade_agg[c] = np.nan

    arcade_agg["opp_value_per_player"] = (
        arcade_agg["total_opp_value"] / arcade_agg["total_players"].replace(0, np.nan)
    ).round(1)

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

    # Pass 2: normalized fallback (prefer IE Published on title collisions)
    rm_remaining = rm[~rm["Join Key"].isin(pass1_matched)].copy()
    rm_remaining["_norm"] = rm_remaining["Final Demo Title"].apply(_normalize_name)
    norm_lookup = _dedupe_rm_prefer_ie_published(rm_remaining, "_norm").set_index("_norm")

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
    merged["rm_status"] = merged.get("rm_status", pd.Series(dtype=str)).fillna("")
    merged["all_rm_statuses"] = merged["arcade_display_key"].apply(
        lambda key: _statuses_for_arcade(key, status_by_join_key, status_by_norm_title)
    )
    # If join picked a primary status but lookup found more, keep the full set
    for idx in merged.index:
        if merged.loc[idx, "rm_status"] and merged.loc[idx, "rm_status"] not in merged.loc[idx, "all_rm_statuses"]:
            merged.at[idx, "all_rm_statuses"] = sorted(
                set(merged.loc[idx, "all_rm_statuses"]) | {merged.loc[idx, "rm_status"]}
            )
    merged["is_ie_published"] = merged["all_rm_statuses"].apply(
        lambda statuses: IE_PUBLISHED_STATUS in statuses
    )
    merged["is_ie_retired"] = merged["all_rm_statuses"].apply(
        lambda statuses: IE_RETIRED_STATUS in statuses
    )
    merged["is_ie_reviewed"] = merged["all_rm_statuses"].apply(
        lambda statuses: IE_REVIEWED_STATUS in statuses
    )
    merged["is_ie_received"] = merged["all_rm_statuses"].apply(
        lambda statuses: IE_RECEIVED_STATUS in statuses
    )
    merged["is_closed"] = merged["all_rm_statuses"].apply(
        lambda statuses: CLOSED_STATUS in statuses
    )
    merged["owner"] = merged.get("Creator Name", pd.Series(dtype=str))
    merged["team"] = merged.get("Creator Team", pd.Series(dtype=str))
    merged["content_type"] = merged.get("Final Content Type", pd.Series(dtype=str))
    merged["quarter_created"] = merged.get("Quarter", pd.Series(dtype=str))
    merged["cta_link"] = merged.get("CTALink", pd.Series(dtype=str))
    merged["drupal_url"] = merged.get("Drupal Page URL", pd.Series(dtype=str))
    merged["rhac_url"] = merged.get("RHAC page", pd.Series(dtype=str))
    merged["public_site"] = merged.get("Public Site Link", pd.Series(dtype=str))
    merged["description"] = merged.get("Demo Description", pd.Series(dtype=str))
    merged["gemini_description"] = merged.get(
        "Demo Description (Gemini generated)", pd.Series(dtype=str)
    )
    merged["destination_channels"] = merged.get("Destination Channels", pd.Series(dtype=str))

    return merged


WEIGHTS = {
    "engagement": 0.35,
    "freshness": 0.25,
    "metadata": 0.20,
    "sales": 0.20,
}


def score_engagement(df: pd.DataFrame) -> pd.Series:
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
    player_score = np.clip(player_ratio * 50, 0, 100)

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
    if not isinstance(name, str):
        return 0.0

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

    ver_match = re.search(r"\b(\d+\.\d+)\b", name)
    if ver_match:
        return 10.0

    return 0.0


def score_freshness(df: pd.DataFrame) -> pd.Series:
    now = datetime.now()
    scores = pd.Series(100.0, index=df.index)

    for idx in df.index:
        quarter = df.loc[idx, "quarter_created"] if "quarter_created" in df.columns else None
        first_month = df.loc[idx, "first_month"] if "first_month" in df.columns else None

        creation_date = _quarter_to_date(quarter) if isinstance(quarter, str) else None
        if creation_date is None and pd.notna(first_month):
            creation_date = pd.Timestamp(first_month).to_pydatetime()

        if creation_date is None:
            scores.iloc[idx] = 40.0
            continue

        age_months = (now.year - creation_date.year) * 12 + (now.month - creation_date.month)

        if age_months <= 12:
            age_score = 100.0
        elif age_months <= 18:
            age_score = 100.0 - ((age_months - 12) / 6) * 40
        else:
            age_score = max(60.0 - (age_months - 18) * 5, 10.0)

        version_penalty = _extract_version_age_penalty(
            df.loc[idx, "arcade_display_key"], now
        )

        scores.iloc[idx] = max(age_score - version_penalty, 0)

    return scores.round(1)


def score_metadata(df: pd.DataFrame) -> pd.Series:
    max_per_item = 20.0

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

    no_rm_mask = ~df["has_rm_match"]
    raw[no_rm_mask] = np.minimum(raw[no_rm_mask], 40.0)

    return raw.round(1)


def score_sales(df: pd.DataFrame) -> pd.Series:
    scores = pd.Series(50.0, index=df.index)

    has_sales = df["has_sales_data"] == True
    if not has_sales.any():
        return scores

    sales_df = df[has_sales]

    opp_per_player = (
        sales_df["total_opp_value"] / sales_df["total_players"].replace(0, np.nan)
    ).fillna(0)
    median_opp = opp_per_player.median()
    if median_opp > 0:
        relative = (opp_per_player / median_opp).clip(0, 3)
        sales_score = (relative / 3 * 70 + 30).round(1)
    else:
        sales_score = pd.Series(50.0, index=sales_df.index)

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


def export_health_json(
    scored_df: pd.DataFrame,
    output_path: str,
    request_master: pd.DataFrame | None = None,
) -> dict:
    status_counts = scored_df["status"].value_counts().to_dict()
    for s in ["Healthy", "Watch", "Refresh", "Replace", "Retire"]:
        status_counts.setdefault(s, 0)

    unowned = int(
        ((scored_df["owner"].isna()) | (scored_df["owner"] == "")).sum()
    )
    ie_published_df = (
        scored_df[scored_df["is_ie_published"]]
        if "is_ie_published" in scored_df.columns
        else scored_df.iloc[0:0]
    )
    ie_published_count = len(ie_published_df)
    ie_retired_count = int(scored_df.get("is_ie_retired", pd.Series(dtype=bool)).sum())
    rm_status_counts = (
        scored_df["rm_status"].replace("", "No RM match").value_counts().to_dict()
        if "rm_status" in scored_df.columns
        else {}
    )
    request_master_row_counts = (
        summarize_request_master_statuses(request_master)
        if request_master is not None
        else {}
    )
    matched_arcades_by_rm_status: dict[str, int] = {}
    if "all_rm_statuses" in scored_df.columns:
        for statuses in scored_df["all_rm_statuses"]:
            for status in statuses or []:
                if status:
                    matched_arcades_by_rm_status[status] = (
                        matched_arcades_by_rm_status.get(status, 0) + 1
                    )

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total_arcades": len(scored_df),
            "by_status": {k: int(v) for k, v in status_counts.items()},
            "by_rm_status": {k: int(v) for k, v in rm_status_counts.items()},
            "request_master_row_counts_by_status": request_master_row_counts,
            "matched_arcades_by_rm_status": matched_arcades_by_rm_status,
            "unowned_count": unowned,
            "ie_published_count": ie_published_count,
            "ie_retired_count": ie_retired_count,
            "avg_health_score": round(float(scored_df["health_score"].mean()), 1),
            "avg_health_score_ie_published": (
                round(float(ie_published_df["health_score"].mean()), 1)
                if ie_published_count > 0
                else None
            ),
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
                "rm_status": _safe_str(row.get("rm_status")),
                "all_rm_statuses": list(row.get("all_rm_statuses") or []),
                "is_ie_published": bool(row.get("is_ie_published", False)),
                "is_ie_retired": bool(row.get("is_ie_retired", False)),
                "is_ie_reviewed": bool(row.get("is_ie_reviewed", False)),
                "is_ie_received": bool(row.get("is_ie_received", False)),
                "is_closed": bool(row.get("is_closed", False)),
                "owner": _safe_str(row.get("owner")),
                "team": _safe_str(row.get("team")),
                "product": _safe_str(row.get("product")),
                "tdp": _safe_str(row.get("tdp")),
                "content_type": _safe_str(row.get("content_type")),
                "quarter_created": _safe_str(row.get("quarter_created")),
                "description": _safe_str(row.get("description")),
                "gemini_description": _safe_str(row.get("gemini_description")),
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
                "total_sales_uv": _safe_float(row.get("total_sales_uv")),
                "total_sales_mt_uv": _safe_float(row.get("total_sales_mt_uv")),
                "total_inquiries": _safe_float(row.get("total_inquiries")),
                "total_contacts": _safe_float(row.get("total_contacts")),
                "total_opps": _safe_float(row.get("total_opps")),
                "total_wins": _safe_float(row.get("total_wins")),
                "total_opp_value": _safe_float(row.get("total_opp_value")),
                "total_won_value": _safe_float(row.get("total_won_value")),
                "total_pages_touched": _safe_float(row.get("total_pages_touched")),
                "opp_value_per_player": _safe_float(row.get("opp_value_per_player")),
            },
        }
        result["arcades"].append(arcade)

    result["arcades"].sort(key=lambda a: a["health_score"] or 0, reverse=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    return result
