"""Sonnet rationale generation for top candidates."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from catalog_fields import rm_field

RATIONALE_MODEL = os.environ.get("RCARS_RATIONALE_MODEL", "claude-sonnet-4-6")
RATIONALE_TOP_N = int(os.environ.get("RCARS_RATIONALE_TOP_N", "5"))


def build_rationale_prompt(query: str, candidates: list[dict]) -> str:
    blocks = []
    for index, candidate in enumerate(candidates, start=1):
        analysis = candidate.get("analysis") or {}
        metadata = candidate.get("metadata") or {}
        blocks.append(
            f"--- Candidate {index} ---\n"
            f"Asset ID: {candidate.get('asset_id')}\n"
            f"Heading: {candidate.get('heading')}\n"
            f"Summary: {analysis.get('summary')}\n"
            f"Topics: {', '.join(analysis.get('topics') or [])}\n"
            f"Products: {', '.join(analysis.get('products') or [])}\n"
            f"Audience: {analysis.get('audience')}\n"
            f"Key Modules: {', '.join(analysis.get('key_modules') or [])}\n"
            f"Event Fit: {', '.join(analysis.get('event_fit') or [])}\n"
            f"Format Notes: {analysis.get('format_notes')}\n"
            f"Duration: {analysis.get('estimated_duration_minutes')}\n"
            f"URL: {candidate.get('canonical_url')}\n"
            f"RM Description: {rm_field(metadata, 'Demo Description')[:800]}\n"
        )
    return f"""Generate recommendation rationales for the user's request.

Return ONLY JSON with this shape:
{{
  "assessment": "overall response",
  "top_picks": ["asset_id", ...],
  "content_gaps": ["topic not covered well", ...],
  "candidates": [
    {{
      "asset_id": "...",
      "why_it_fits": "...",
      "how_to_use": "...",
      "suggested_format": "...",
      "duration_notes": "...",
      "caveats": "..."
    }}
  ]
}}

## Request
{query}

## Candidates
{''.join(blocks)}
"""


def generate_rationale(query: str, candidates: list[dict]) -> dict[str, Any]:
    top = candidates[:RATIONALE_TOP_N]
    if not top:
        return {
            "assessment": "No relevant candidates to rationale.",
            "top_picks": [],
            "content_gaps": [],
            "candidates": [],
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_rationale(top)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=RATIONALE_MODEL,
            max_tokens=2500,
            messages=[{"role": "user", "content": build_rationale_prompt(query, top)}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        payload = json.loads(text)
    except Exception:
        return _fallback_rationale(top)

    rationale_by_id = {
        item["asset_id"]: item for item in payload.get("candidates", []) if item.get("asset_id")
    }
    enriched: list[dict] = []
    for candidate in top:
        updated = dict(candidate)
        rationale = rationale_by_id.get(candidate["asset_id"], {})
        updated["rationale"] = rationale
        updated["tier"] = "green"
        enriched.append(updated)

    return {
        "assessment": payload.get("assessment", ""),
        "top_picks": payload.get("top_picks", []),
        "content_gaps": payload.get("content_gaps", []),
        "candidates": enriched,
    }


def _fallback_rationale(candidates: list[dict]) -> dict[str, Any]:
    enriched = []
    for candidate in candidates:
        analysis = candidate.get("analysis") or {}
        enriched.append(
            {
                **candidate,
                "tier": "green",
                "rationale": {
                    "asset_id": candidate["asset_id"],
                    "why_it_fits": analysis.get("summary", ""),
                    "how_to_use": candidate.get("canonical_url", ""),
                    "suggested_format": analysis.get("format_notes", ""),
                    "duration_notes": str(analysis.get("estimated_duration_minutes") or ""),
                    "caveats": "",
                },
            }
        )
    return {
        "assessment": "Fallback rationale generated from indexed summaries.",
        "top_picks": [item["asset_id"] for item in enriched],
        "content_gaps": [],
        "candidates": enriched,
    }
