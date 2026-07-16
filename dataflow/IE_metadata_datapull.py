#!/usr/bin/env python3
"""Pull Google Sheet Request_Master tab via GWS CLI → CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from merge_palist_requestmaster import RM_COLUMNS

DEFAULT_SPREADSHEET_ID = "1t7TJtTL-jbUaCVKVLMMOahbKcL5b1IyCf3uUSCmQo4A"
DEFAULT_RANGE = "Request_Master"
DEFAULT_OUTPUT = Path("data/request_master.csv")


def flatten_cell(value: str) -> str:
    """Collapse multiline/indented sheet cells onto a single CSV row."""
    if not value:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return re.sub(r"\s+", " ", " ".join(line for line in lines if line)).strip()


def fetch_sheet_json(spreadsheet_id: str, range_name: str) -> list[list[str]]:
    params = json.dumps({"spreadsheetId": spreadsheet_id, "range": range_name})
    result = subprocess.run(
        ["gws", "sheets", "spreadsheets", "values", "get", "--params", params],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gws sheets get failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    payload = json.loads(result.stdout)
    values = payload.get("values") or payload.get("response", {}).get("values")
    if values is None:
        # gws may wrap the API response differently
        if "values" in payload:
            values = payload["values"]
        else:
            raise RuntimeError(f"Unexpected gws response shape: {list(payload.keys())}")
    return values


def project_columns(rows: list[list[str]], columns: list[str]) -> tuple[list[list[str]], list[str]]:
    """Keep only the requested header columns; warn on missing names."""
    if not rows:
        return [], []
    header = [flatten_cell(cell) for cell in rows[0]]
    index_by_name = {name: idx for idx, name in enumerate(header)}
    missing = [col for col in columns if col not in index_by_name]
    projected: list[list[str]] = [list(columns)]
    for raw in rows[1:]:
        projected.append(
            [
                flatten_cell(raw[index_by_name[col]]) if col in index_by_name and index_by_name[col] < len(raw) else ""
                for col in columns
            ]
        )
    return projected, missing


def sheet_to_csv(spreadsheet_id: str, range_name: str, output_path: Path) -> Path:
    rows = fetch_sheet_json(spreadsheet_id, range_name)
    if not rows:
        raise RuntimeError(f"No rows returned for range {range_name!r}")

    projected, missing = project_columns(rows, RM_COLUMNS)
    if missing:
        print(
            "Warning: Request_Master missing columns: " + ", ".join(missing),
            file=sys.stderr,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        for row in projected:
            writer.writerow(row)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull Request_Master sheet to CSV via gws.")
    parser.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    parser.add_argument("--range", default=DEFAULT_RANGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sheet_to_csv(args.spreadsheet_id, args.range, args.output)
    row_count = max(len(args.output.read_text(encoding="utf-8").splitlines()) - 1, 0)
    print(f"Wrote {row_count} data rows to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
