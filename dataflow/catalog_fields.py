"""Shared helpers for merged catalog CSV field access."""

from __future__ import annotations


def rm_field(row: dict[str, str], name: str) -> str:
    """Read a Request Master column from a merged row (rm_ prefixed, spaces → underscores)."""
    return (row.get(f"rm_{name.replace(' ', '_')}") or "").strip()


def display_heading(row: dict[str, str]) -> str:
    return (row.get("Heading") or rm_field(row, "Final Demo Title") or "").strip()


def metadata_text(row: dict[str, str]) -> str:
    parts = [
        display_heading(row),
        row.get("Summary", ""),
        rm_field(row, "Demo Description"),
        row.get("Product", ""),
        rm_field(row, "Primary Product"),
        row.get("Vertical", ""),
        rm_field(row, "Verticals"),
        row.get("Solutions", ""),
    ]
    return " ".join(part for part in parts if part)
