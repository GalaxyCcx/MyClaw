from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    name: str
    status: str  # "success" | "error" | "warning"
    detail: str = ""
    duration_ms: float = 0.0


class InitJobCollector:
    def __init__(self):
        self.jobs: list[JobResult] = []

    def clear(self):
        self.jobs.clear()

    def run_job(self, name: str, func: Callable[[], Any]) -> JobResult:
        start = time.perf_counter()
        try:
            result = func()
            elapsed = (time.perf_counter() - start) * 1000
            if isinstance(result, JobResult):
                job = JobResult(
                    name=name,
                    status=result.status,
                    detail=result.detail,
                    duration_ms=round(elapsed, 1),
                )
            else:
                detail = str(result) if result is not None else "OK"
                job = JobResult(name=name, status="success", detail=detail, duration_ms=round(elapsed, 1))
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            job = JobResult(name=name, status="error", detail=str(e), duration_ms=round(elapsed, 1))
            logger.error("Init job '%s' failed: %s", name, e)

        self.jobs.append(job)
        logger.info("Init job '%s': %s (%.1fms)", name, job.status, job.duration_ms)
        return job

    def to_dict_list(self) -> list[dict]:
        return [
            {
                "name": j.name,
                "status": j.status,
                "detail": j.detail,
                "duration_ms": j.duration_ms,
            }
            for j in self.jobs
        ]


init_collector = InitJobCollector()
