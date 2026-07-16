#!/usr/bin/env python3
"""Orchestrate fetch → parse → scan → embed → SQLite index."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from adoc_fetch import asset_id_for_row, fetch_asset_content
from adoc_parse import build_parsed_text
from advisor_index import (
    DEFAULT_INDEX_PATH,
    connect,
    embedding_to_blob,
    get_asset,
    init_db,
    list_assets,
    set_meta,
    upsert_asset,
    utc_now,
)
from catalog_fields import display_heading
from embed_index import analysis_to_json, build_embed_text, embed_texts
from merge_palist_requestmaster import DEFAULT_LIVE_IE_PUBLISHED_OUTPUT
from scan_analyze import analyze_with_anthropic, fallback_analysis


def read_merged_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def should_rescan(existing, content_hash: str, force: bool) -> bool:
    if force:
        return True
    if existing is None:
        return True
    if not existing["analysis_json"]:
        return True
    return existing["content_hash"] != content_hash


def index_assets(
    merged_path: Path,
    index_path: Path,
    *,
    asset_filter: str | None = None,
    skip_fetch: bool = False,
    skip_scan: bool = False,
    force_scan: bool = False,
    use_fallback_scan: bool = False,
) -> None:
    rows = read_merged_csv(merged_path)
    if asset_filter:
        rows = [
            row
            for row in rows
            if asset_id_for_row(row) == asset_filter
            or (row.get("ppid") or "") == asset_filter
        ]
        if not rows:
            raise RuntimeError(f"No asset matched filter {asset_filter!r}")

    conn = connect(index_path)
    init_db(conn)

    pending_embed_texts: list[str] = []
    pending_records: list[dict] = []

    for row in rows:
        asset_id = asset_id_for_row(row)
        print(f"Processing {asset_id}...")

        if skip_fetch:
            existing = get_asset(conn, asset_id)
            if existing is None:
                print(f"  Skipping unknown asset {asset_id} with --skip-fetch")
                continue
            fetch = type("Fetch", (), {
                "content_source": existing["content_source"],
                "raw_content": existing["parsed_text"] or "",
                "content_hash": existing["content_hash"] or "",
                "detail_page": existing["detail_page"] or "",
            })()
            parsed_text = existing["parsed_text"] or ""
        else:
            try:
                fetch = fetch_asset_content(row)
            except RuntimeError as exc:
                print(f"  Fetch failed: {exc}; using metadata fallback")
                fetch = fetch_asset_content({**row, "DetailPage": ""})
            parsed_text = build_parsed_text(fetch.raw_content, row)

        existing = get_asset(conn, asset_id)
        if skip_scan and existing and existing["analysis_json"]:
            analysis = json.loads(existing["analysis_json"])
        elif should_rescan(existing, fetch.content_hash, force_scan):
            try:
                if use_fallback_scan or not os.environ.get("ANTHROPIC_API_KEY"):
                    if not use_fallback_scan:
                        print("  No ANTHROPIC_API_KEY; using fallback analysis")
                    analysis = fallback_analysis(row, parsed_text)
                else:
                    analysis = analyze_with_anthropic(row, parsed_text)
            except Exception as exc:
                print(f"  Scan failed: {exc}; using fallback analysis")
                analysis = fallback_analysis(row, parsed_text)
            scanned_at = utc_now()
        else:
            analysis = json.loads(existing["analysis_json"])
            scanned_at = existing["scanned_at"]
            print("  Reusing cached analysis")

        embed_text = build_embed_text(row, analysis, parsed_text)
        pending_embed_texts.append(embed_text)
        pending_records.append(
            {
                "asset_id": asset_id,
                "ppid": row.get("ppid", ""),
                "paname": row.get("PAName", ""),
                "heading": display_heading(row),
                "source": row.get("source", ""),
                "canonical_url": row.get("canonical_url", ""),
                "detail_page": fetch.detail_page,
                "content_source": fetch.content_source,
                "metadata_json": json.dumps(row, ensure_ascii=False),
                "parsed_text": parsed_text,
                "content_hash": fetch.content_hash,
                "analysis_json": analysis_to_json(analysis),
                "embed_text": embed_text,
                "embedding": None,
                "scanned_at": scanned_at,
                "indexed_at": utc_now(),
                "_analysis": analysis,
            }
        )

    if not pending_records:
        print("No assets indexed.")
        return

    vectors = embed_texts(pending_embed_texts)
    for record, vector in zip(pending_records, vectors):
        record["embedding"] = embedding_to_blob(vector)
        record.pop("_analysis", None)
        upsert_asset(conn, record)

    set_meta(conn, "last_indexed_at", utc_now())
    set_meta(conn, "asset_count", str(len(list_assets(conn))))
    set_meta(conn, "merged_source", str(merged_path))
    print(f"Indexed {len(pending_records)} assets to {index_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build advisor search index.")
    parser.add_argument(
        "--merged",
        type=Path,
        default=DEFAULT_LIVE_IE_PUBLISHED_OUTPUT,
    )
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--asset", help="Index a single asset id or ppid")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--skip-scan", action="store_true", help="Re-embed using existing analysis")
    parser.add_argument("--force-scan", action="store_true")
    parser.add_argument(
        "--fallback-scan",
        action="store_true",
        help="Skip LLM scan and use metadata-only analysis",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index_assets(
        args.merged,
        args.index,
        asset_filter=args.asset,
        skip_fetch=args.skip_fetch,
        skip_scan=args.skip_scan,
        force_scan=args.force_scan,
        use_fallback_scan=args.fallback_scan,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
