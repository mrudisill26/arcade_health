#!/usr/bin/env python3
"""Merge PAList catalog rows with Request Master metadata on ppid."""

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

RM_COLUMNS = [
    "Status",
    "Final Demo Title",
    "Final Content Type",
    "Public Site Link",
    "Production Link",
    "Drupal Page URL",
    "RHAC page",
    "Origin Type",
    "Primary Product",
    "Product",
    "Content Type",
    "Marketing Program",
    "TDP",
    "Sales Tactic",
    "Verticals",
    "Event",
    "Creator Name",
    "Creator Team",
    "Creation Link",
    "Quarter",
    "Demo Description",
    "Language",
    "Duration",
    "CTALink",
    "Creator Employee Advocacy Link",
    "Latest Prod Link",
    "Number",
]

OUTPUT_COLUMNS = [
    "source",
    "canonical_url",
    *PALIST_COLUMNS,
    *(f"rm_{col.replace(' ', '_')}" for col in RM_COLUMNS),
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


def extract_ppid_from_rm(row: dict[str, str]) -> str:
    for field in ("RHAC page", "Public Site Link", "Drupal Page URL"):
        ppid = extract_ppid_from_url(row.get(field, ""))
        if ppid:
            return ppid
    return ""


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
        key = f"rm_{col.replace(' ', '_')}"
        row[key] = rm_row.get(col, "") if rm_row else ""
    return row


def index_rm_by_ppid(rm_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rm_rows:
        ppid = extract_ppid_from_rm(row)
        if not ppid:
            continue
        existing = indexed.get(ppid)
        if existing is None or (
            row.get("Status") == IE_PUBLISHED_STATUS
            and existing.get("Status") != IE_PUBLISHED_STATUS
        ):
            indexed[ppid] = row
    return indexed


def merge(palist_path: Path, request_master_path: Path) -> list[dict[str, str]]:
    palist_rows = read_csv(palist_path)
    rm_rows = read_csv(request_master_path)
    rm_by_ppid = index_rm_by_ppid(rm_rows)

    merged: list[dict[str, str]] = []
    seen_rm_ppids: set[str] = set()
    matched_rm_rows: set[int] = set()

    for palist_row in palist_rows:
        ppid = (palist_row.get("ppid") or "").strip()
        rm_row = rm_by_ppid.get(ppid)
        if rm_row:
            seen_rm_ppids.add(ppid)
            matched_rm_rows.add(id(rm_row))
            source = "PAList+RM"
        else:
            source = "PAList only"
        merged.append(build_row(source, palist_row, rm_row))

    for ppid, rm_row in rm_by_ppid.items():
        if ppid in seen_rm_ppids:
            continue
        merged.append(build_row("RM only", empty_palist_row(), rm_row))
        matched_rm_rows.add(id(rm_row))

    for rm_row in rm_rows:
        if id(rm_row) in matched_rm_rows:
            continue
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
