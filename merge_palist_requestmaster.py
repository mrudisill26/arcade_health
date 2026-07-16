#!/usr/bin/env python3
"""Merge PAList catalog rows with Request Master metadata.

Join strategy (in order):
1. Portfolio ppid from RM URLs (RHAC / Public / Drupal / Production), or Join Key
   only when it is a bare numeric id / paname (`123-slug`) — Join Key is usually a title.
2. Secondary: unique normalized title match between PAList Heading and
   RM Join Key / Final Demo Title, skipped when URL ppids would conflict.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_PALIST = Path("data/palist.csv")
DEFAULT_REQUEST_MASTER = Path("data/request_master.csv")
DEFAULT_OUTPUT = Path("data/merged_assets.csv")
DEFAULT_LIVE_IE_PUBLISHED_OUTPUT = Path("data/merged_live_and_ie_published.csv")

IE_PUBLISHED_STATUS = "IE Published"
ARCHITECT_PORTFOLIO_BASE = "https://www.redhat.com/architect/portfolio/detail/"

PALIST_COLUMNS = [
    "ppid",
    "PAName",
    "Heading",
    "islive",
    "isnew",
    "showInCatalog",
    "Summary",
    "Vertical",
    "Solutions",
    "Platform",
    "Product",
    "ProductType",
    "Image1Url",
    "DetailPage",
    "Status",
    "externalUrl",
    "isRedirected",
]

# Request Master columns to keep (sheet letters documented for operators).
RM_COLUMNS = [
    "Status",  # A
    "Public Site Link",  # B
    "Production Link",  # C
    "Final Content Type",  # D
    "Drupal Page URL",  # F
    "RHAC page",  # G
    "Final Demo Title",  # H
    "Publish states",  # S
    "Featured Start Date",  # U
    "Featured End Date",  # V
    "Origin Type",  # AF
    "Primary Product",  # AO
    "Product",  # AP
    "Marketing Program",  # AV
    "TDP",  # AW
    "Sales Tactic",  # AX
    "Verticals",  # AY
    "Event",  # AZ
    "Primary Audience",  # BA
    "Personas",  # BB
    "Pain Points",  # BC
    "Creator Name",  # BH
    "Creator Team",  # BJ
    "Quarter",  # BL
    "Demo Description",  # BM
    "Demo Description (Gemini generated)",  # BN
    "Language",  # BO
    "Duration",  # BP
    "SEOWords",  # BQ
    "CTALink",  # BV
    "Join Key",  # CA
    "Number",  # CB
    "Metadata",  # CC
]

GEMINI_DEMO_DESCRIPTION = "Demo Description (Gemini generated)"


def rm_column_key(col: str) -> str:
    return f"rm_{col.replace(' ', '_')}"


OUTPUT_COLUMNS = [
    "source",
    "canonical_url",
    *PALIST_COLUMNS,
    *(rm_column_key(col) for col in RM_COLUMNS),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def extract_ppid_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    if not path:
        return ""
    slug = path.split("/")[-1]
    match = re.match(r"^(\d+)(?:-|$)", slug)
    if match:
        return match.group(1)
    return ""


def normalize_title(text: str) -> str:
    """Light title normalization for secondary joins (keeps parenthetical variants)."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9()|&+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_ppid_from_join_key(join_key: str) -> str:
    """Join Key is usually a title; only treat as ppid when clearly numeric/paname."""
    token = (join_key or "").strip()
    if not token:
        return ""
    if token.isdigit():
        return token
    match = re.match(r"^(\d{2,4})-[a-z0-9-]+$", token.lower())
    if match:
        return match.group(1)
    return ""


def extract_ppid_from_rm(row: dict[str, str]) -> str:
    """Primary join id: URL portfolio ppid, or Join Key only when it is a real id."""
    join_ppid = extract_ppid_from_join_key(row.get("Join Key", ""))
    if join_ppid:
        return join_ppid
    for field in ("RHAC page", "Public Site Link", "Drupal Page URL", "Production Link"):
        ppid = extract_ppid_from_url(row.get(field, ""))
        if ppid:
            return ppid
    return ""


def prefer_rm_row(
    existing: dict[str, str] | None,
    candidate: dict[str, str],
) -> dict[str, str]:
    if existing is None:
        return candidate
    if (
        candidate.get("Status") == IE_PUBLISHED_STATUS
        and existing.get("Status") != IE_PUBLISHED_STATUS
    ):
        return candidate
    return existing


def index_rm_by_ppid(rm_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rm_rows:
        ppid = extract_ppid_from_rm(row)
        if not ppid:
            continue
        indexed[ppid] = prefer_rm_row(indexed.get(ppid), row)
    return indexed


def index_rm_by_unique_title(
    rm_rows: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Map normalized Join Key / Final Demo Title → RM row when the title is unique."""
    buckets: dict[str, list[dict[str, str]]] = {}
    for row in rm_rows:
        seen_keys: set[str] = set()
        for field in ("Join Key", "Final Demo Title"):
            key = normalize_title(row.get(field, ""))
            if len(key) < 8 or key in seen_keys:
                continue
            seen_keys.add(key)
            buckets.setdefault(key, []).append(row)

    unique: dict[str, dict[str, str]] = {}
    for key, rows in buckets.items():
        deduped: list[dict[str, str]] = []
        seen_ids: set[int] = set()
        for row in rows:
            if id(row) in seen_ids:
                continue
            seen_ids.add(id(row))
            deduped.append(row)
        if len(deduped) != 1:
            continue
        unique[key] = deduped[0]
    return unique


def find_rm_for_palist(
    palist_row: dict[str, str],
    rm_by_ppid: dict[str, dict[str, str]],
    rm_by_title: dict[str, dict[str, str]],
    claimed_rm_ids: set[int],
) -> dict[str, str] | None:
    ppid = (palist_row.get("ppid") or "").strip()
    if ppid:
        rm_row = rm_by_ppid.get(ppid)
        if rm_row is not None and id(rm_row) not in claimed_rm_ids:
            return rm_row

    title = normalize_title(palist_row.get("Heading") or "")
    if len(title) < 8:
        return None
    rm_row = rm_by_title.get(title)
    if rm_row is None or id(rm_row) in claimed_rm_ids:
        return None

    rm_ppid = extract_ppid_from_rm(rm_row)
    # Title match is only a fill-in: never override a URL/id that points elsewhere.
    if rm_ppid and ppid and rm_ppid != ppid:
        return None
    if rm_ppid and rm_ppid in rm_by_ppid and rm_ppid != ppid:
        return None
    return rm_row


def canonical_url(palist_row: dict[str, str], rm_row: dict[str, str] | None) -> str:
    if rm_row:
        for field in ("Drupal Page URL", "RHAC page", "Public Site Link", "Production Link"):
            url = (rm_row.get(field) or "").strip()
            if url:
                return url
    detail = (palist_row.get("DetailPage") or "").strip()
    paname = (palist_row.get("PAName") or "").strip()
    if detail and paname:
        slug = paname.split("-", 1)[-1] if "-" in paname else paname
        if detail.endswith(".adoc"):
            slug = detail.removesuffix(".adoc").split("/")[-1]
        return f"{ARCHITECT_PORTFOLIO_BASE}{slug}"
    if paname:
        slug = paname.split("-", 1)[-1] if "-" in paname else paname
        return f"{ARCHITECT_PORTFOLIO_BASE}{slug}"
    return ""


def empty_palist_row() -> dict[str, str]:
    return {col: "" for col in PALIST_COLUMNS}


def build_row(
    source: str,
    palist_row: dict[str, str],
    rm_row: dict[str, str] | None,
) -> dict[str, str]:
    row: dict[str, str] = {"source": source}
    row["canonical_url"] = canonical_url(palist_row, rm_row)
    for col in PALIST_COLUMNS:
        row[col] = palist_row.get(col, "")
    for col in RM_COLUMNS:
        row[rm_column_key(col)] = rm_row.get(col, "") if rm_row else ""
    return row


def merge(palist_path: Path, request_master_path: Path) -> list[dict[str, str]]:
    palist_rows = read_csv(palist_path)
    rm_rows = read_csv(request_master_path)
    rm_by_ppid = index_rm_by_ppid(rm_rows)
    rm_by_title = index_rm_by_unique_title(rm_rows)

    merged: list[dict[str, str]] = []
    claimed_rm_ids: set[int] = set()
    seen_rm_ppids: set[str] = set()

    for palist_row in palist_rows:
        rm_row = find_rm_for_palist(
            palist_row,
            rm_by_ppid,
            rm_by_title,
            claimed_rm_ids,
        )
        if rm_row:
            claimed_rm_ids.add(id(rm_row))
            ppid = extract_ppid_from_rm(rm_row) or (palist_row.get("ppid") or "").strip()
            if ppid:
                seen_rm_ppids.add(ppid)
            source = "PAList+RM"
        else:
            source = "PAList only"
        merged.append(build_row(source, palist_row, rm_row))

    for ppid, rm_row in rm_by_ppid.items():
        if id(rm_row) in claimed_rm_ids:
            continue
        if ppid in seen_rm_ppids:
            continue
        claimed_rm_ids.add(id(rm_row))
        merged.append(build_row("RM only", empty_palist_row(), rm_row))

    for rm_row in rm_rows:
        if id(rm_row) in claimed_rm_ids:
            continue
        claimed_rm_ids.add(id(rm_row))
        merged.append(build_row("RM only", empty_palist_row(), rm_row))

    return merged


def merge_live_and_ie_published(
    palist_path: Path,
    request_master_path: Path,
) -> list[dict[str, str]]:
    all_rows = merge(palist_path, request_master_path)
    live_palist = [
        row for row in all_rows if (row.get("islive") or "").upper() == "TRUE"
    ]
    rm_only_ie = [
        row
        for row in all_rows
        if row["source"] == "RM only" and row.get("rm_Status") == IE_PUBLISHED_STATUS
    ]
    return live_palist + rm_only_ie


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge PAList with Request Master.")
    parser.add_argument("--palist", type=Path, default=DEFAULT_PALIST)
    parser.add_argument("--request-master", type=Path, default=DEFAULT_REQUEST_MASTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--live-ie-published",
        action="store_true",
        help="Write live PAList + IE Published merge instead of full merge",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.live_ie_published:
        rows = merge_live_and_ie_published(args.palist, args.request_master)
        output = DEFAULT_LIVE_IE_PUBLISHED_OUTPUT
    else:
        rows = merge(args.palist, args.request_master)
        output = args.output
    write_csv(rows, output)
    print(f"Wrote {len(rows)} rows to {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
