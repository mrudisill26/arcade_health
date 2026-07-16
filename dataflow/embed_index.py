#!/usr/bin/env python3
"""Build embedding text and vectors for indexed assets."""

from __future__ import annotations

import json
from typing import Any

from catalog_fields import demo_description, display_heading, rm_field

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None


def get_embed_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def build_embed_text(row: dict[str, str], analysis: dict[str, Any], parsed_text: str) -> str:
    heading = display_heading(row)
    topics = ", ".join(analysis.get("topics") or [])
    products = ", ".join(analysis.get("products") or [])
    description = demo_description(row)
    audience = rm_field(row, "Primary Audience") or analysis.get("audience") or ""
    personas = rm_field(row, "Personas")
    pain_points = rm_field(row, "Pain Points")
    seo = rm_field(row, "SEOWords")
    parts = [
        heading,
        analysis.get("summary") or "",
        description,
        f"Topics: {topics}" if topics else "",
        f"Products: {products}" if products else "",
        f"Type: {analysis.get('content_type') or ''}",
        f"Vertical: {row.get('Vertical') or rm_field(row, 'Verticals') or ''}",
        f"Solutions: {row.get('Solutions') or ''}",
        f"Audience: {audience}" if audience else "",
        f"Personas: {personas}" if personas else "",
        f"Pain points: {pain_points}" if pain_points else "",
        f"SEO: {seo}" if seo else "",
        parsed_text[:2000],
    ]
    return ". ".join(part.strip() for part in parts if part and str(part).strip())


def embed_texts(texts: list[str]):
    import numpy as np

    model = get_embed_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return np.asarray(vectors, dtype=np.float32)


def analysis_to_json(analysis: dict[str, Any]) -> str:
    return json.dumps(analysis, ensure_ascii=False)
