#!/usr/bin/env python3
"""Pull osspa-site ArchitectureList CSVs from GitLab → local data/."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITLAB_REPO_BASE = (
    "https://gitlab.com/osspa/osspa-site/-/raw/main/src/app"
)


@dataclass(frozen=True)
class OsspaCsvSource:
    repo_path: str
    output_path: Path


OSSPA_CSVS: dict[str, OsspaCsvSource] = {
    "PAList.csv": OsspaCsvSource(
        "ArchitectureList/PAList.csv",
        Path("data/palist.csv"),
    ),
    "PlatformList.csv": OsspaCsvSource(
        "ArchitectureList/PlatformList.csv",
        Path("data/platformlist.csv"),
    ),
    "TypeList.csv": OsspaCsvSource(
        "ArchitectureList/TypeList.csv",
        Path("data/typelist.csv"),
    ),
    "SolutionList.csv": OsspaCsvSource(
        "ArchitectureList/SolutionList.csv",
        Path("data/solutionlist.csv"),
    ),
    "ProductList.csv": OsspaCsvSource(
        "ArchitectureList/ProductList.csv",
        Path("data/productlist.csv"),
    ),
    "DetailLink.csv": OsspaCsvSource(
        "ArchitectureDetail/DetailLink.csv",
        Path("data/detaillink.csv"),
    ),
}


def flatten_cell(value: str) -> str:
    if not value:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return re.sub(r"\s+", " ", " ".join(line for line in lines if line)).strip()


def fetch_csv_text(repo_path: str) -> str:
    url = f"{GITLAB_REPO_BASE}/{repo_path}"
    request = Request(url, headers={"User-Agent": "dataflow/1.0"})
    try:
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} fetching {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc


def normalize_rows(text: str) -> list[list[str]]:
    reader = csv.reader(text.splitlines())
    return [[flatten_cell(cell) for cell in row] for row in reader]


def write_csv(rows: list[list[str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerows(rows)


def gitlab_csv_to_local(source: OsspaCsvSource, label: str) -> Path:
    print(f"Fetching {label} from GitLab...")
    text = fetch_csv_text(source.repo_path)
    rows = normalize_rows(text)
    write_csv(rows, source.output_path)
    data_rows = max(len(rows) - 1, 0)
    print(f"  Saved {data_rows} data rows to {source.output_path}")
    return source.output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull osspa ArchitectureList CSVs from GitLab.")
    parser.add_argument(
        "--file",
        choices=sorted(OSSPA_CSVS.keys()),
        help="Pull a single CSV (default: all)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = (
        {args.file: OSSPA_CSVS[args.file]}
        if args.file
        else OSSPA_CSVS
    )
    for label, source in targets.items():
        gitlab_csv_to_local(source, label)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
