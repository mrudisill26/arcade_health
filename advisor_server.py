#!/usr/bin/env python3
"""FastAPI server for RCARS-style advisor queries with SSE streaming."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from advisor.jobs import job_store
from advisor.pipeline import run_pipeline
from advisor_index import DEFAULT_INDEX_PATH, connect, get_meta, init_db, list_assets, row_to_asset
from build_index import index_assets
from merge_palist_requestmaster import DEFAULT_LIVE_IE_PUBLISHED_OUTPUT

app = FastAPI(title="Portfolio Advisor", version="0.1.0")


class QueryRequest(BaseModel):
    query: str


def load_assets(index_path: Path = DEFAULT_INDEX_PATH) -> list[dict[str, Any]]:
    conn = connect(index_path)
    init_db(conn)
    return [row_to_asset(row) for row in list_assets(conn)]


@app.get("/advisor/health")
def health() -> dict[str, Any]:
    conn = connect(DEFAULT_INDEX_PATH)
    init_db(conn)
    assets = list_assets(conn)
    return {
        "status": "ok",
        "asset_count": len(assets),
        "last_indexed_at": get_meta(conn, "last_indexed_at"),
        "merged_source": get_meta(conn, "merged_source"),
    }


@app.post("/advisor/query")
def submit_query(body: QueryRequest) -> dict[str, str]:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    assets = load_assets()
    job = job_store.create(query)
    pipeline = run_pipeline(query, assets)
    thread = threading.Thread(target=job_store.run, args=(job, pipeline), daemon=True)
    thread.start()
    return {"job_id": job.job_id}


@app.get("/advisor/query/{job_id}/stream")
def stream_query(job_id: str) -> StreamingResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    def event_generator():
        sent = 0
        while True:
            current = job_store.get(job_id)
            if current is None:
                break
            while sent < len(current.events):
                payload = current.events[sent]
                sent += 1
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if current.done:
                if current.error:
                    error_payload = {"phase": "ERROR", "message": current.error}
                    yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                break
            threading.Event().wait(0.2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/advisor/reindex")
def reindex() -> dict[str, str]:
    thread = threading.Thread(
        target=index_assets,
        kwargs={
            "merged_path": DEFAULT_LIVE_IE_PUBLISHED_OUTPUT,
            "index_path": DEFAULT_INDEX_PATH,
            "use_fallback_scan": not __import__("os").environ.get("ANTHROPIC_API_KEY"),
        },
        daemon=True,
    )
    thread.start()
    return {"status": "started"}
