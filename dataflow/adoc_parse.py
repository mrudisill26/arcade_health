#!/usr/bin/env python3
"""Strip AsciiDoc markup to plain text for LLM analysis and embedding."""

from __future__ import annotations

import re

from catalog_fields import metadata_text

MAX_PARSED_CHARS = 12_000
THIN_CONTENT_THRESHOLD = 500


def metadata_fallback_text(row: dict[str, str]) -> str:
    return metadata_text(row)


def strip_adoc(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Drop passthrough HTML blocks
    text = re.sub(r"^\+\+\+\+.*?^\+\+\+\+", "", text, flags=re.MULTILINE | re.DOTALL)

    # Remove attribute lines
    text = re.sub(r"^:[^\n]+\n", "", text, flags=re.MULTILINE)

    # Remove include/image/link macros but keep alt/label text when present
    text = re.sub(r"image::[^\[]+\[([^\]]*)\]", r"\1", text)
    text = re.sub(r"image:[^\[]+\[([^\]]*)\]", r"\1", text)
    text = re.sub(r"include::[^\[]+\[[^\]]*\]", "", text)
    text = re.sub(r"link:[^\[]+\[([^\]]*)\]", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)

    # Headings and emphasis
    text = re.sub(r"^=+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\*\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\.\.\.\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"[*_`#|]", "", text)

    # Table separators
    text = re.sub(r"^\|===.*", " ", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)

    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def build_parsed_text(raw_content: str, row: dict[str, str]) -> str:
    parsed = strip_adoc(raw_content)
    fallback = metadata_fallback_text(row)
    if len(parsed) < THIN_CONTENT_THRESHOLD:
        parsed = f"{fallback} {parsed}".strip()
    if len(parsed) > MAX_PARSED_CHARS:
        parsed = parsed[:MAX_PARSED_CHARS]
    return parsed.strip()
