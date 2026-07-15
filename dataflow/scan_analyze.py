#!/usr/bin/env python3
"""LLM scan analysis for catalog assets (RCARS scan equivalent)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from catalog_fields import display_heading, rm_field

SCAN_MODEL = os.environ.get("RCARS_SCAN_MODEL", "claude-sonnet-4-6")

ANALYSIS_SCHEMA = {
    "summary": "2-3 sentence overview",
    "topics": ["technical topic"],
    "products": ["Red Hat product"],
    "content_type": "workshop|demo|architecture|interactive_experience|walkthrough|other",
    "category": "Security|AI|Virtualization|etc",
    "audience": "who this is for",
    "estimated_duration_minutes": None,
    "duration_source": "curated|estimated",
    "format_notes": "demo vs hands-on vs autoplay",
    "event_fit": ["event type"],
    "key_modules": ["section or workflow name"],
}


def parse_duration_minutes(value: str) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


def build_scan_prompt(row: dict[str, str], parsed_text: str) -> str:
    metadata_bits = [
        f"Heading: {display_heading(row)}",
        f"Summary: {row.get('Summary') or ''}",
        f"ProductType: {row.get('ProductType') or ''}",
        f"Products: {row.get('Product') or rm_field(row, 'Primary Product') or rm_field(row, 'Product') or ''}",
        f"Vertical: {row.get('Vertical') or rm_field(row, 'Verticals') or ''}",
        f"RM Content Type: {rm_field(row, 'Content Type') or rm_field(row, 'Final Content Type') or ''}",
        f"RM Duration: {rm_field(row, 'Duration') or ''}",
        f"Source: {row.get('source') or ''}",
    ]
    return f"""Analyze this Red Hat portfolio catalog asset and return ONLY valid JSON matching this schema:
{json.dumps(ANALYSIS_SCHEMA, indent=2)}

Use curated duration from RM Duration when present (duration_source=curated).
Otherwise estimate duration (duration_source=estimated) or null if unknown.

## Metadata
{chr(10).join(metadata_bits)}

## Content
{parsed_text[:8000]}
"""


def normalize_analysis(raw: dict[str, Any], row: dict[str, str]) -> dict[str, Any]:
    curated = parse_duration_minutes(rm_field(row, "Duration"))
    estimated = raw.get("estimated_duration_minutes")
    if curated is not None:
        duration = curated
        duration_source = "curated"
    elif isinstance(estimated, (int, float)):
        duration = int(estimated)
        duration_source = raw.get("duration_source") or "estimated"
    else:
        duration = None
        duration_source = raw.get("duration_source") or "estimated"

    def as_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    return {
        "summary": str(raw.get("summary") or row.get("Summary") or rm_field(row, "Demo Description") or "").strip(),
        "topics": as_list(raw.get("topics")),
        "products": as_list(raw.get("products")),
        "content_type": str(raw.get("content_type") or row.get("ProductType") or "other").strip(),
        "category": str(raw.get("category") or "").strip(),
        "audience": str(raw.get("audience") or "").strip(),
        "estimated_duration_minutes": duration,
        "duration_source": duration_source,
        "format_notes": str(raw.get("format_notes") or "").strip(),
        "event_fit": as_list(raw.get("event_fit")),
        "key_modules": as_list(raw.get("key_modules")),
    }


def analyze_with_anthropic(row: dict[str, str], parsed_text: str) -> dict[str, Any]:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package required for scan analysis") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is required")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_scan_prompt(row, parsed_text)
    response = client.messages.create(
        model=SCAN_MODEL,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    raw = json.loads(text)
    return normalize_analysis(raw, row)


def fallback_analysis(row: dict[str, str], parsed_text: str) -> dict[str, Any]:
    products = [
        part.strip()
        for part in re.split(r"[,;]", row.get("Product") or rm_field(row, "Primary Product") or "")
        if part.strip()
    ]
    return normalize_analysis(
        {
            "summary": row.get("Summary") or rm_field(row, "Demo Description") or parsed_text[:400],
            "topics": [],
            "products": products,
            "content_type": row.get("ProductType") or rm_field(row, "Content Type") or "other",
            "category": row.get("Vertical") or "",
            "audience": "",
            "estimated_duration_minutes": parse_duration_minutes(rm_field(row, "Duration")),
            "duration_source": "curated" if rm_field(row, "Duration") else "estimated",
            "format_notes": rm_field(row, "Final Content Type") or "",
            "event_fit": [],
            "key_modules": [],
        },
        row,
    )
