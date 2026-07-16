"""Haiku triage scoring for vector search candidates."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from catalog_fields import demo_description, rm_field

TRIAGE_MODEL = os.environ.get("RCARS_TRIAGE_MODEL", "claude-haiku-4-5")
TRIAGE_CUTOFF = int(os.environ.get("RCARS_TRIAGE_CUTOFF", "30"))


def compact_candidate(asset: dict) -> dict[str, Any]:
    analysis = asset.get("analysis") or {}
    metadata = asset.get("metadata") or {}
    duration = analysis.get("estimated_duration_minutes")
    duration_label = f"{duration} min" if duration else "unknown"
    return {
        "asset_id": asset.get("asset_id"),
        "heading": asset.get("heading") or metadata.get("Heading") or rm_field(metadata, "Final Demo Title"),
        "summary": analysis.get("summary") or metadata.get("Summary") or demo_description(metadata),
        "topics": analysis.get("topics") or [],
        "products": analysis.get("products") or [],
        "category": analysis.get("category") or metadata.get("Vertical") or rm_field(metadata, "Verticals") or "",
        "content_type": analysis.get("content_type")
        or metadata.get("ProductType")
        or rm_field(metadata, "Final Content Type")
        or "",
        "audience": analysis.get("audience") or rm_field(metadata, "Primary Audience") or "",
        "duration": duration_label,
        "canonical_url": asset.get("canonical_url") or "",
    }


def build_triage_prompt(query: str, candidates: list[dict]) -> str:
    blocks = []
    for index, candidate in enumerate(candidates, start=1):
        compact = compact_candidate(candidate)
        blocks.append(
            f"--- Candidate {index} ---\n"
            f"Asset ID: {compact['asset_id']}\n"
            f"Heading: {compact['heading']}\n"
            f"Summary: {compact['summary']}\n"
            f"Topics: {', '.join(compact['topics'])}\n"
            f"Products: {', '.join(compact['products'])}\n"
            f"Category: {compact['category']}\n"
            f"Content Type: {compact['content_type']}\n"
            f"Audience: {compact['audience']}\n"
            f"Duration: {compact['duration']}\n"
        )
    return f"""You are evaluating RHDP portfolio catalog items for relevance to a user's request.

Be strict: a partial topic overlap is not relevance. If the content does
not meaningfully address what the user is asking for, mark it as not
relevant.

Return ONLY a JSON array with objects:
{{"asset_id": "...", "relevance_score": 0-100, "relevant": true/false, "one_line_reason": "..."}}

## Request
{query}

## Candidates
{''.join(blocks)}
"""


def triage_candidates(query: str, candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_triage(candidates)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=TRIAGE_MODEL,
            max_tokens=1800,
            messages=[{"role": "user", "content": build_triage_prompt(query, candidates)}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        scored = json.loads(text)
    except Exception:
        return _fallback_triage(candidates)

    by_id = {item["asset_id"]: item for item in scored if item.get("asset_id")}
    triaged: list[dict] = []
    for candidate in candidates:
        result = by_id.get(candidate["asset_id"], {})
        relevance_score = int(result.get("relevance_score", 0))
        relevant = bool(result.get("relevant", relevance_score >= TRIAGE_CUTOFF))
        updated = dict(candidate)
        updated["relevance_score"] = relevance_score
        updated["relevant"] = relevant
        updated["one_line_reason"] = result.get("one_line_reason", "")
        updated["tier"] = "yellow" if relevant and relevance_score >= TRIAGE_CUTOFF else "white"
        triaged.append(updated)

    triaged.sort(key=lambda item: item.get("relevance_score", 0), reverse=True)
    return triaged


def _fallback_triage(candidates: list[dict]) -> list[dict]:
    triaged: list[dict] = []
    for candidate in candidates:
        distance = candidate.get("vector_distance", 1.0)
        score = max(0, int((1 - distance) * 100))
        relevant = score >= TRIAGE_CUTOFF
        updated = dict(candidate)
        updated["relevance_score"] = score
        updated["relevant"] = relevant
        updated["one_line_reason"] = "Fallback score from vector distance"
        updated["tier"] = "yellow" if relevant else "white"
        triaged.append(updated)
    triaged.sort(key=lambda item: item["relevance_score"], reverse=True)
    return triaged
