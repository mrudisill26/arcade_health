"""RCARS-style progressive recommendation pipeline."""

from __future__ import annotations

from typing import Any, Generator

from advisor.acronyms import expand_acronyms
from advisor.asset_resolution import resolve_asset
from advisor.dedup import dedup_candidates
from advisor.duration_rerank import apply_duration_penalty
from advisor.rationale import RATIONALE_TOP_N, generate_rationale
from advisor.triage import TRIAGE_CUTOFF, triage_candidates
from advisor.vector_search import search_by_embedding, search_by_text


def candidate_payload(asset: dict) -> dict[str, Any]:
    analysis = asset.get("analysis") or {}
    return {
        "asset_id": asset.get("asset_id"),
        "ppid": asset.get("ppid"),
        "heading": asset.get("heading"),
        "source": asset.get("source"),
        "canonical_url": asset.get("canonical_url"),
        "summary": analysis.get("summary"),
        "products": analysis.get("products"),
        "content_type": analysis.get("content_type"),
        "vector_distance": asset.get("vector_distance"),
        "relevance_score": asset.get("relevance_score"),
        "relevant": asset.get("relevant"),
        "one_line_reason": asset.get("one_line_reason"),
        "tier": asset.get("tier", "white"),
        "rationale": asset.get("rationale"),
    }


def run_pipeline(query: str, assets: list[dict]) -> Generator[dict[str, Any], None, None]:
    if not assets:
        yield {
            "phase": "NO_MATCHES",
            "message": "Index is empty. Run build_index.py first.",
            "candidates": [],
        }
        return

    resolved = resolve_asset(query, assets)
    query_results = search_by_text(assets, query)
    neighbor_results: list[dict] = []
    exclude_ids: set[str] = set()

    if resolved is not None:
        exclude_ids.add(resolved["asset_id"])
        neighbor_results = search_by_embedding(
            assets,
            resolved["embedding"],
            exclude_asset_ids=exclude_ids,
        )

    merged = dedup_candidates(query_results + neighbor_results)
    if not merged:
        yield {
            "phase": "NO_MATCHES",
            "message": (
                "No close matches found. Try focusing on core topics and "
                "technologies rather than event names or delivery constraints."
            ),
            "candidates": [],
            "resolved_asset_id": resolved["asset_id"] if resolved else None,
        }
        return

    for candidate in merged:
        candidate.setdefault("tier", "white")

    yield {
        "phase": "VECTOR_SEARCH",
        "query": expand_acronyms(query),
        "resolved_asset_id": resolved["asset_id"] if resolved else None,
        "candidates": [candidate_payload(item) for item in merged],
    }

    triaged = triage_candidates(query, merged)
    survivors = [item for item in triaged if item.get("relevant") and item.get("relevance_score", 0) >= TRIAGE_CUTOFF]
    for item in triaged:
        if item not in survivors:
            item["tier"] = "white"

    reranked = apply_duration_penalty(survivors, query)
    for item in reranked:
        item["tier"] = "yellow"

    yield {
        "phase": "TRIAGE",
        "candidates": [candidate_payload(item) for item in triaged],
    }

    rationale_result = generate_rationale(query, reranked)
    green_ids = {item["asset_id"] for item in rationale_result["candidates"]}
    final_candidates = []
    for item in triaged:
        payload = candidate_payload(item)
        if item["asset_id"] in green_ids:
            green = next(
                candidate for candidate in rationale_result["candidates"]
                if candidate["asset_id"] == item["asset_id"]
            )
            payload = candidate_payload(green)
        final_candidates.append(payload)

    yield {
        "phase": "RATIONALE",
        "assessment": rationale_result.get("assessment"),
        "content_gaps": rationale_result.get("content_gaps", []),
        "top_picks": rationale_result.get("top_picks", [])[:RATIONALE_TOP_N],
        "candidates": final_candidates,
    }

    yield {
        "phase": "COMPLETE",
        "assessment": rationale_result.get("assessment"),
        "content_gaps": rationale_result.get("content_gaps", []),
        "top_picks": rationale_result.get("top_picks", [])[:RATIONALE_TOP_N],
        "candidates": final_candidates,
    }
