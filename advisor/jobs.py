"""In-memory job store for streaming advisor queries."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class AdvisorJob:
    job_id: str
    query: str
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, AdvisorJob] = {}
        self._lock = threading.Lock()

    def create(self, query: str) -> AdvisorJob:
        job = AdvisorJob(job_id=str(uuid.uuid4()), query=query)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> AdvisorJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def run(self, job: AdvisorJob, pipeline: Generator[dict[str, Any], None, None]) -> None:
        try:
            for event in pipeline:
                with self._lock:
                    job.events.append(event)
            with self._lock:
                job.done = True
        except Exception as exc:
            with self._lock:
                job.error = str(exc)
                job.done = True


job_store = JobStore()
