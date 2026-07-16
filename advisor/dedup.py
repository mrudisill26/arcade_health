"""Deduplicate vector search candidates."""

from __future__ import annotations

SOURCE_PRIORITY = {
    "PAList+RM": 3,
    "PAList only": 2,
    "RM only": 1,
}


def _dedup_key(asset: dict) -> str:
    url = (asset.get("canonical_url") or "").strip().lower()
    if url:
        return f"url:{url}"
    content_hash = (asset.get("content_hash") or "").strip()
    if content_hash:
        return f"hash:{content_hash}"
    return f"id:{asset.get('asset_id')}"


def dedup_candidates(candidates: list[dict]) -> list[dict]:
    best_by_key: dict[str, dict] = {}
    for candidate in candidates:
        key = _dedup_key(candidate)
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = candidate
            continue

        cand_score = (
            SOURCE_PRIORITY.get(candidate.get("source", ""), 0),
            -candidate.get("vector_distance", 999),
        )
        exist_score = (
            SOURCE_PRIORITY.get(existing.get("source", ""), 0),
            -existing.get("vector_distance", 999),
        )
        if cand_score > exist_score:
            best_by_key[key] = candidate

    deduped = list(best_by_key.values())
    deduped.sort(key=lambda item: item.get("vector_distance", 999))
    return deduped
