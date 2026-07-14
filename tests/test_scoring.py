import pandas as pd
import numpy as np
import pytest
from scoring import (
    load_engagement_data,
    load_request_master,
    merge_datasets,
    find_request_status_column,
    score_engagement,
    score_freshness,
    score_metadata,
    score_sales,
    compute_health_scores,
    export_health_json,
)


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
        '"Destination Channels","Demo Description","Request Status"\n'
        '"Arcade Alpha","Arcade Alpha | Business Intro","Alice Smith","Team A",'
        '"Business Intro","CY26Q1","https://cta.example.com","https://drupal.example.com",'
        '"https://rhac.example.com","https://public.example.com","OpenShift","Virtualization",'
        '"Web, Social","A demo about OpenShift","IE Published"\n'
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
    assert alpha["has_rm_match"] == True
    assert alpha["is_ie_published"] == True
    assert alpha["rm_status"] == "IE Published"


def test_find_request_status_column_ignores_timestamps(sample_rm_csv):
    df = load_request_master(sample_rm_csv)
    df["Status Open Timestamp"] = "2026-01-01"
    assert find_request_status_column(df) == "Request Status"


def test_merge_prefers_ie_published_on_duplicate_join_key(sample_engagement_csv, tmp_path):
    csv_path = tmp_path / "request_master_dup.csv"
    csv_path.write_text(
        '"Final Demo Title","Join Key","Creator Name","Creator Team",'
        '"Final Content Type","Quarter","CTALink","Drupal Page URL",'
        '"RHAC page","Public Site Link","Primary Product","TDP",'
        '"Destination Channels","Demo Description","Request Status"\n'
        '"Arcade Alpha Draft","Arcade Alpha | Business Intro","Draft Owner","Draft Team",'
        '"Business Intro","CY25Q4","","","","","OpenShift","Virtualization",'
        '"Web","Draft version","In Progress"\n'
        '"Arcade Alpha","Arcade Alpha | Business Intro","Alice Smith","Team A",'
        '"Business Intro","CY26Q1","https://cta.example.com","https://drupal.example.com",'
        '"https://rhac.example.com","https://public.example.com","OpenShift","Virtualization",'
        '"Web, Social","Published version","IE Published"\n'
        '"Arcade Alpha Retired","Arcade Alpha | Business Intro","Retired Owner","Retired Team",'
        '"Business Intro","CY24Q4","","","","","OpenShift","Virtualization",'
        '"Web","Retired version","IE Retired"\n'
    )
    eng = load_engagement_data(sample_engagement_csv)
    rm = load_request_master(str(csv_path))
    merged = merge_datasets(eng, rm)
    alpha = merged[merged["arcade_display_key"] == "Arcade Alpha | Business Intro"].iloc[0]
    assert alpha["owner"] == "Alice Smith"
    assert alpha["is_ie_published"] == True
    assert alpha["is_ie_retired"] == True
    assert alpha["all_rm_statuses"] == ["IE Published", "IE Retired", "In Progress"]


def test_merge_keeps_all_status_rows_without_join_key(tmp_path):
    csv_path = tmp_path / "request_master_no_key.csv"
    csv_path.write_text(
        '"Final Demo Title","Join Key","Creator Name","Creator Team",'
        '"Final Content Type","Quarter","Request Status"\n'
        '"Draft A","","Owner A","Team A","Business Intro","CY26Q1","IE Received"\n'
        '"Draft B","","Owner B","Team B","Business Intro","CY26Q1","Closed"\n'
    )
    df = load_request_master(str(csv_path))
    from scoring import _prepare_request_master
    prepared = _prepare_request_master(df)
    assert len(prepared) == 2


def test_merge_matches_non_ie_published_status(sample_engagement_csv, tmp_path):
    csv_path = tmp_path / "request_master_draft.csv"
    csv_path.write_text(
        '"Final Demo Title","Join Key","Creator Name","Creator Team",'
        '"Final Content Type","Quarter","CTALink","Drupal Page URL",'
        '"RHAC page","Public Site Link","Primary Product","TDP",'
        '"Destination Channels","Demo Description","Request Status"\n'
        '"Arcade Beta","Arcade Beta","Bob Jones","Team B",'
        '"Technical Walkthrough","CY25Q2","","https://drupal.example.com",'
        '"","","RHEL","AI Platform",'
        '"Web","Beta draft","In Progress"\n'
    )
    eng = load_engagement_data(sample_engagement_csv)
    rm = load_request_master(str(csv_path))
    merged = merge_datasets(eng, rm)
    beta = merged[merged["arcade_display_key"] == "Arcade Beta"].iloc[0]
    assert beta["has_rm_match"] == True
    assert beta["owner"] == "Bob Jones"
    assert beta["is_ie_published"] == False
    assert beta["rm_status"] == "In Progress"


def test_merge_matches_ie_retired_status(sample_engagement_csv, tmp_path):
    csv_path = tmp_path / "request_master_retired.csv"
    csv_path.write_text(
        '"Final Demo Title","Join Key","Creator Name","Creator Team",'
        '"Final Content Type","Quarter","CTALink","Drupal Page URL",'
        '"RHAC page","Public Site Link","Primary Product","TDP",'
        '"Destination Channels","Demo Description","Request Status"\n'
        '"Arcade Beta","Arcade Beta","Retired Owner","Retired Team",'
        '"Technical Walkthrough","CY23Q4","","https://drupal.example.com",'
        '"","","RHEL","AI Platform",'
        '"Web","Retired demo","IE Retired"\n'
    )
    eng = load_engagement_data(sample_engagement_csv)
    rm = load_request_master(str(csv_path))
    merged = merge_datasets(eng, rm)
    beta = merged[merged["arcade_display_key"] == "Arcade Beta"].iloc[0]
    assert beta["has_rm_match"] == True
    assert beta["owner"] == "Retired Owner"
    assert beta["is_ie_retired"] == True
    assert beta["is_ie_published"] == False
    assert beta["rm_status"] == "IE Retired"


def test_merge_datasets_unmatched_arcade(sample_engagement_csv, sample_rm_csv):
    eng = load_engagement_data(sample_engagement_csv)
    rm = load_request_master(sample_rm_csv)
    merged = merge_datasets(eng, rm)
    beta = merged[merged["arcade_display_key"] == "Arcade Beta"].iloc[0]
    assert beta["has_rm_match"] == False
    assert pd.isna(beta["owner"]) or beta["owner"] == ""


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
    assert alpha > beta


def test_score_sales_neutral_when_no_data(merged_df):
    scores = score_sales(merged_df)
    beta = scores[merged_df["arcade_display_key"] == "Arcade Beta"].iloc[0]
    assert beta == 50


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


def test_export_health_json_structure(merged_df, sample_rm_csv, tmp_path):
    import json
    scored = compute_health_scores(merged_df)
    rm = load_request_master(sample_rm_csv)
    output_path = str(tmp_path / "health.json")
    result = export_health_json(scored, output_path, request_master=rm)

    assert "generated_at" in result
    assert "summary" in result
    assert "arcades" in result
    assert result["summary"]["total_arcades"] == 2
    assert "request_master_row_counts_by_status" in result["summary"]
    assert result["summary"]["request_master_row_counts_by_status"]["IE Published"] == 1
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
    import json
    scored = compute_health_scores(merged_df)
    output_path = str(tmp_path / "health.json")
    export_health_json(scored, output_path)

    with open(output_path) as f:
        data = json.load(f)
    assert data["summary"]["total_arcades"] == 2
