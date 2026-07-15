#!/usr/bin/env python3
"""SQLite index store for advisor assets."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

DEFAULT_INDEX_PATH = Path("data/advisor_index.sqlite")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path = DEFAULT_INDEX_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            asset_id TEXT PRIMARY KEY,
            ppid TEXT,
            paname TEXT,
            heading TEXT,
            source TEXT,
            canonical_url TEXT,
            detail_page TEXT,
            content_source TEXT,
            metadata_json TEXT,
            parsed_text TEXT,
            content_hash TEXT,
            analysis_json TEXT,
            embed_text TEXT,
            embedding BLOB,
            scanned_at TEXT,
            indexed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()


def get_asset(conn: sqlite3.Connection, asset_id: str) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM assets WHERE asset_id = ?", (asset_id,)
    ).fetchone()
    return row


def list_assets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM assets ORDER BY asset_id").fetchall()


def upsert_asset(conn: sqlite3.Connection, record: dict) -> None:
    conn.execute(
        """
        INSERT INTO assets (
            asset_id, ppid, paname, heading, source, canonical_url, detail_page,
            content_source, metadata_json, parsed_text, content_hash, analysis_json,
            embed_text, embedding, scanned_at, indexed_at
        ) VALUES (
            :asset_id, :ppid, :paname, :heading, :source, :canonical_url, :detail_page,
            :content_source, :metadata_json, :parsed_text, :content_hash, :analysis_json,
            :embed_text, :embedding, :scanned_at, :indexed_at
        )
        ON CONFLICT(asset_id) DO UPDATE SET
            ppid=excluded.ppid,
            paname=excluded.paname,
            heading=excluded.heading,
            source=excluded.source,
            canonical_url=excluded.canonical_url,
            detail_page=excluded.detail_page,
            content_source=excluded.content_source,
            metadata_json=excluded.metadata_json,
            parsed_text=excluded.parsed_text,
            content_hash=excluded.content_hash,
            analysis_json=excluded.analysis_json,
            embed_text=excluded.embed_text,
            embedding=excluded.embedding,
            scanned_at=excluded.scanned_at,
            indexed_at=excluded.indexed_at
        """,
        record,
    )
    conn.commit()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO index_meta (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (key, value),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM index_meta WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def embedding_to_blob(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def blob_to_embedding(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def row_to_asset(row: sqlite3.Row) -> dict:
    asset = dict(row)
    asset["metadata"] = json.loads(asset.pop("metadata_json") or "{}")
    asset["analysis"] = json.loads(asset.pop("analysis_json") or "{}")
    if asset.get("embedding"):
        asset["embedding"] = blob_to_embedding(asset["embedding"])
    else:
        asset["embedding"] = None
    return asset
