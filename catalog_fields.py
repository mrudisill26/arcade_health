"""Shared helpers for merged catalog CSV field access."""

from __future__ import annotations

from merge_palist_requestmaster import GEMINI_DEMO_DESCRIPTION, rm_column_key


def rm_field(row: dict[str, str], name: str) -> str:
    """Read a Request Master column from a merged row (rm_ prefixed, spaces → underscores)."""
    return (row.get(rm_column_key(name)) or "").strip()


def display_heading(row: dict[str, str]) -> str:
    return (row.get("Heading") or rm_field(row, "Final Demo Title") or "").strip()


def demo_description(row: dict[str, str]) -> str:
    """Prefer Gemini-generated description, then manual Demo Description."""
    return rm_field(row, GEMINI_DEMO_DESCRIPTION) or rm_field(row, "Demo Description")


def metadata_text(row: dict[str, str]) -> str:
    parts = [
        display_heading(row),
        row.get("Summary", ""),
        demo_description(row),
        row.get("Product", ""),
        rm_field(row, "Primary Product"),
        row.get("Vertical", ""),
        rm_field(row, "Verticals"),
        row.get("Solutions", ""),
        rm_field(row, "Primary Audience"),
        rm_field(row, "Personas"),
        rm_field(row, "Pain Points"),
        rm_field(row, "SEOWords"),
    ]
    return " ".join(part for part in parts if part)
