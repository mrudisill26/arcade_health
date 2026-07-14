import json
import pytest
from pathlib import Path
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
    assert "ARCADE_DATA" in html


def test_theme_css_exists_and_contains_tokens():
    theme_path = Path(__file__).parent.parent / "static" / "theme.css"
    assert theme_path.exists(), "static/theme.css must exist"
    content = theme_path.read_text()
    assert ":root" in content
    required_tokens = [
        "--bg-page", "--bg-surface", "--bg-surface-raised", "--bg-input",
        "--text-primary", "--text-secondary", "--text-muted", "--text-on-color",
        "--status-healthy", "--status-watch", "--status-refresh",
        "--status-replace", "--status-retire",
        "--link-color", "--border-default", "--border-input",
        "--font-family", "--font-family-heading", "--font-family-mono",
        "--font-size-xs", "--font-size-sm", "--font-size-md",
        "--font-size-lg", "--font-size-xl", "--font-size-2xl",
        "--font-weight-normal", "--font-weight-medium",
        "--font-weight-semibold", "--font-weight-bold",
        "--space-xs", "--space-sm", "--space-md",
        "--space-lg", "--space-xl", "--space-2xl",
        "--radius-sm", "--radius-md", "--radius-pill", "--radius-circle",
    ]
    for token in required_tokens:
        assert token in content, f"Missing token: {token}"


def test_render_html_uses_css_tokens(sample_health_json, tmp_path):
    import re
    output = str(tmp_path / "dashboard.html")
    render_dashboard(sample_health_json, output)
    with open(output) as f:
        html = f.read()

    assert "var(--bg-page)" in html
    assert "var(--text-primary)" in html
    assert "var(--status-healthy)" in html
    assert "var(--font-family)" in html
    assert "var(--space-lg)" in html
    assert "var(--radius-md)" in html

    style_match = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    assert style_match, "No <style> block found"
    style_block = style_match.group(1)

    lines_after_root = style_block.split("}" , 1)[-1] if ":root" in style_block else style_block
    hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    violations = []
    for i, line in enumerate(lines_after_root.splitlines()):
        if hex_pattern.search(line):
            violations.append(line.strip())
    assert not violations, f"Hardcoded hex colors found outside :root block:\n" + "\n".join(violations[:10])
