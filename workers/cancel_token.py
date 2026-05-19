"""Cooperative cancellation for long-running background workers."""
from __future__ import annotations


class WorkerCancelled(Exception):
    """Raised when the user closes the app or stops a background job."""


class CancelToken:
    def __init__(self) -> None:
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        if self._cancelled:
            raise WorkerCancelled("Operation cancelled.")
