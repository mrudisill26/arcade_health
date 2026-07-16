"""Vector search over indexed assets."""

from __future__ import annotations

import os

import numpy as np

from advisor.acronyms import expand_acronyms
from embed_index import embed_texts

VECTOR_CUTOFF = float(os.environ.get("RCARS_VECTOR_CUTOFF", "0.55"))
TOP_K = int(os.environ.get("RCARS_VECTOR_TOP_K", "15"))


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(1.0 - np.dot(a, b))


def search_by_embedding(
    assets: list[dict],
    query_vector: np.ndarray,
    *,
    cutoff: float = VECTOR_CUTOFF,
    top_k: int = TOP_K,
    exclude_asset_ids: set[str] | None = None,
) -> list[dict]:
    exclude_asset_ids = exclude_asset_ids or set()
    results: list[dict] = []
    for asset in assets:
        if asset["asset_id"] in exclude_asset_ids:
            continue
        vector = asset.get("embedding")
        if vector is None:
            continue
        distance = cosine_distance(query_vector, vector)
        if distance <= cutoff:
            candidate = dict(asset)
            candidate["vector_distance"] = distance
            results.append(candidate)
    results.sort(key=lambda item: item["vector_distance"])
    return results[:top_k]


def search_by_text(
    assets: list[dict],
    query: str,
    *,
    cutoff: float = VECTOR_CUTOFF,
    top_k: int = TOP_K,
    exclude_asset_ids: set[str] | None = None,
) -> list[dict]:
    expanded = expand_acronyms(query)
    query_vector = embed_texts([expanded])[0]
    return search_by_embedding(
        assets,
        query_vector,
        cutoff=cutoff,
        top_k=top_k,
        exclude_asset_ids=exclude_asset_ids,
    )
