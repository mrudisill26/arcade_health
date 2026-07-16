#!/usr/bin/env python3
"""Fetch .adoc content from portfolio-architecture-examples GitLab."""

from __future__ import annotations

import hashlib
import re
from catalog_fields import display_heading, metadata_text
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITLAB_CONTENT_BASE = (
    "https://gitlab.com/osspa/portfolio-architecture-examples/-/raw/main/"
)
DEFAULT_CACHE_DIR = Path("data/content_cache")


@dataclass
class FetchResult:
    asset_id: str
    detail_page: str
    content_source: str  # adoc | metadata_only | cache
    raw_content: str
    content_hash: str
    cache_path: Path | None


def asset_id_for_row(row: dict[str, str]) -> str:
    ppid = (row.get("ppid") or "").strip()
    if ppid:
        return ppid
    rm_number = (row.get("rm_Number") or "").strip()
    if rm_number:
        return f"rm-{rm_number}"
    heading = display_heading(row) or "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
    return f"slug-{slug[:40]}"


def cache_path_for(asset_id: str, detail_page: str, cache_dir: Path) -> Path:
    slug = detail_page.replace("/", "__").removesuffix(".adoc")
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", asset_id)
    return cache_dir / f"{safe_id}_{slug}.adoc"


def fetch_adoc_text(detail_page: str) -> str:
    url = f"{GITLAB_CONTENT_BASE}{detail_page}"
    request = Request(url, headers={"User-Agent": "dataflow-advisor/1.0"})
    try:
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def metadata_fallback_text(row: dict[str, str]) -> str:
    return metadata_text(row)


def fetch_asset_content(
    row: dict[str, str],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> FetchResult:
    asset_id = asset_id_for_row(row)
    detail_page = (row.get("DetailPage") or "").strip()
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not detail_page:
        fallback = metadata_fallback_text(row)
        return FetchResult(
            asset_id=asset_id,
            detail_page="",
            content_source="metadata_only",
            raw_content=fallback,
            content_hash=content_hash(fallback),
            cache_path=None,
        )

    path = cache_path_for(asset_id, detail_page, cache_dir)
    if not force and path.exists():
        raw = path.read_text(encoding="utf-8")
        return FetchResult(
            asset_id=asset_id,
            detail_page=detail_page,
            content_source="cache",
            raw_content=raw,
            content_hash=content_hash(raw),
            cache_path=path,
        )

    raw = fetch_adoc_text(detail_page)
    path.write_text(raw, encoding="utf-8")
    return FetchResult(
        asset_id=asset_id,
        detail_page=detail_page,
        content_source="adoc",
        raw_content=raw,
        content_hash=content_hash(raw),
        cache_path=path,
    )
