#!/usr/bin/env python3
"""Pull Request_Master + PAList, then merge live PAList with IE Published rows."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from IE_metadata_datapull import DEFAULT_OUTPUT as DEFAULT_REQUEST_MASTER
from IE_metadata_datapull import DEFAULT_RANGE, DEFAULT_SPREADSHEET_ID, sheet_to_csv
from merge_palist_requestmaster import (
    DEFAULT_LIVE_IE_PUBLISHED_OUTPUT,
    DEFAULT_PALIST,
    merge_live_and_ie_published,
    write_csv,
)
from osspa_palist_datapull import OSSPA_CSVS, gitlab_csv_to_local

DEFAULT_OUTPUT = DEFAULT_LIVE_IE_PUBLISHED_OUTPUT


def pull_request_master(
    spreadsheet_id: str,
    range_name: str,
    output_path: Path,
) -> Path:
    print(f"Fetching {range_name!r} from spreadsheet {spreadsheet_id}...")
    sheet_to_csv(spreadsheet_id, range_name, output_path)
    row_count = max(len(output_path.read_text(encoding="utf-8").splitlines()) - 1, 0)
    print(f"  Saved {row_count} data rows to {output_path}")
    return output_path


def pull_palist(output_path: Path) -> Path:
    source = OSSPA_CSVS["PAList.csv"]
    if source.output_path != output_path:
        source = type(source)(source.repo_path, output_path)
    gitlab_csv_to_local(source, "PAList.csv")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pull Request_Master and PAList, then write a merged CSV of "
            "live PAList assets and IE Published Request Master rows."
        ),
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=DEFAULT_SPREADSHEET_ID,
        help=f"Google Sheets spreadsheet ID (default: {DEFAULT_SPREADSHEET_ID})",
    )
    parser.add_argument(
        "--range",
        default=DEFAULT_RANGE,
        help=f"Request_Master sheet tab (default: {DEFAULT_RANGE})",
    )
    parser.add_argument(
        "--request-master",
        type=Path,
        default=DEFAULT_REQUEST_MASTER,
        help=f"Request_Master CSV path (default: {DEFAULT_REQUEST_MASTER})",
    )
    parser.add_argument(
        "--palist",
        type=Path,
        default=DEFAULT_PALIST,
        help=f"PAList CSV path (default: {DEFAULT_PALIST})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Merged output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--skip-pull",
        action="store_true",
        help="Skip remote pulls and merge from existing local CSV files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.skip_pull:
        pull_request_master(args.spreadsheet_id, args.range, args.request_master)
        pull_palist(args.palist)

    merged = merge_live_and_ie_published(args.palist, args.request_master)
    write_csv(merged, args.output)

    sources = Counter(row["source"] for row in merged)
    print(f"Merged {len(merged)} rows to {args.output}")
    for source, count in sources.most_common():
        print(f"  {source}: {count}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
