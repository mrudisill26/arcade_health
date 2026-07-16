"""Resolve asset references in user queries."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from advisor.acronyms import STOP_WORDS


def extract_significant_words(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{2,}", text.lower())
    return [word for word in words if word not in STOP_WORDS]


def resolve_asset(query: str, assets: list[dict]) -> dict | None:
    query_lower = query.lower()

    ppid_match = re.search(r"\b(\d{2,4})\b", query)
    if ppid_match:
        ppid = ppid_match.group(1)
        for asset in assets:
            if (asset.get("ppid") or "") == ppid:
                return asset

    paname_match = re.search(r"\b(\d{2,4}-[a-z0-9-]+)\b", query_lower)
    if paname_match:
        token = paname_match.group(1)
        for asset in assets:
            paname = (asset.get("paname") or "").lower()
            if paname == token or paname.endswith(token):
                return asset

    url_match = re.search(r"portfolio/detail/([a-z0-9-]+)", query_lower)
    if url_match:
        slug = url_match.group(1)
        for asset in assets:
            url = (asset.get("canonical_url") or "").lower()
            if slug in url:
                return asset
            detail = (asset.get("detail_page") or "").lower()
            if slug in detail:
                return asset

    words = extract_significant_words(query)
    if len(words) >= 3:
        best = None
        best_score = 0
        for asset in assets:
            heading = (asset.get("heading") or "").lower()
            score = sum(1 for word in words if word in heading)
            if score >= 3 and score > best_score:
                best = asset
                best_score = score
        if best:
            return best

    return None
