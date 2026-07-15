"""Duration-aware reranking after triage."""

from __future__ import annotations

import math
import re

HARD_KEYWORDS = (
    "hard limit",
    "strict",
    "maximum",
    "no more than",
    "at most",
    "cannot exceed",
    "must be under",
)


def extract_target_duration_minutes(query: str) -> tuple[int | None, bool]:
    lower = query.lower()
    hard = any(keyword in lower for keyword in HARD_KEYWORDS)

    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|\s)?hour", lower)
    if hour_match:
        return int(float(hour_match.group(1)) * 60), hard

    minute_match = re.search(r"(\d+)\s*(?:-|\s)?min", lower)
    if minute_match:
        return int(minute_match.group(1)), hard

    return None, hard


def apply_duration_penalty(
    candidates: list[dict],
    query: str,
) -> list[dict]:
    target, hard = extract_target_duration_minutes(query)
    if target is None:
        return candidates

    coefficient = 0.15 if hard else 0.08
    floor = 0.6 if hard else 0.7
    reranked: list[dict] = []

    for candidate in candidates:
        analysis = candidate.get("analysis") or {}
        duration = analysis.get("estimated_duration_minutes")
        score = candidate.get("relevance_score", 0)
        adjusted = score
        if duration and analysis.get("duration_source") == "curated" and duration > 0:
            ratio = max(duration, target) / max(min(duration, target), 1)
            penalty = min(coefficient * math.log(ratio), 1 - floor)
            adjusted = max(score * (1 - penalty), score * floor)
        updated = dict(candidate)
        updated["adjusted_score"] = adjusted
        reranked.append(updated)

    reranked.sort(
        key=lambda item: item.get("adjusted_score", item.get("relevance_score", 0)),
        reverse=True,
    )
    return reranked
