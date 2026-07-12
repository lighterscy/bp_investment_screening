"""Small runtime tracing helpers."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TraceEvent:
    name: str
    elapsed_seconds: float


class Tracer:
    def log(self, message: str) -> None:
        print(message, flush=True)

    @contextmanager
    def step(self, message: str):
        start = time.perf_counter()
        self.log(f"[start] {message}")
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.log(f"[done] {message} ({elapsed:.2f}s)")


class NullTracer(Tracer):
    def log(self, message: str) -> None:
        return
