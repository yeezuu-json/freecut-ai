"""Global download queue manager for video downloads.

Owns all QThread objects so downloads survive dialog close/reopen.
Supports concurrent downloads (configurable) and a FIFO queue.

Usage
-----
    mgr = VideoDownloadManager.instance()
    job_id = mgr.enqueue(url, quality="best")
    mgr.cancel(job_id)

Signals (connect from any widget)
---------------------------------
    job_added(job_id, url, title)
    job_progress(job_id, pct, message)
    job_finished(job_id, success, output_path_str)
    job_removed(job_id)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from app.logger import get_logger
from services.video_download_service import VideoDownloadService, DEFAULT_DOWNLOAD_DIR

logger = get_logger(__name__)

MAX_CONCURRENT = 3   # max parallel downloads


class JobStatus(Enum):
    QUEUED      = auto()
    DOWNLOADING = auto()
    DONE        = auto()
    FAILED      = auto()
    CANCELLED   = auto()


@dataclass
class DownloadJob:
    id: str
    url: str
    quality: str
    output_dir: Path
    title: str = ""
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    message: str = "Queued"
    output_path: str = ""
    error: str = ""
    playlist: bool = False        # download all videos from profile/playlist
    max_downloads: int = 0        # 0 = unlimited (when playlist=True)


class _DownloadWorker(QObject):
    progress_changed = Signal(int, str)
    finished         = Signal(object)   # DownloadResult
    failed           = Signal(str)

    def __init__(self, job: DownloadJob) -> None:
        super().__init__()
        self.job     = job
        self._service = VideoDownloadService(output_dir=job.output_dir)

    def run(self) -> None:
        try:
            result = self._service.download(
                url           = self.job.url,
                quality       = self.job.quality,
                on_progress   = lambda p, m: self.progress_changed.emit(p, m),
                playlist      = self.job.playlist,
                max_downloads = self.job.max_downloads,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self._service.cancel()


class VideoDownloadManager(QObject):
    """Application-wide singleton for background video downloads."""

    job_added    = Signal(str, str, str)    # job_id, url, title
    job_progress = Signal(str, int, str)    # job_id, pct, message
    job_finished = Signal(str, bool, str)   # job_id, success, output_path
    job_removed  = Signal(str)              # job_id

    _instance: Optional["VideoDownloadManager"] = None

    @classmethod
    def instance(cls) -> "VideoDownloadManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._jobs: dict[str, DownloadJob] = {}           # all jobs (ordered)
        self._active: dict[str, tuple[QThread, _DownloadWorker]] = {}

    # ── public API ────────────────────────────────────────────────────────────

    def enqueue(
        self,
        url: str,
        quality: str = "best",
        output_dir: Optional[Path] = None,
        title: str = "",
        playlist: bool = False,
        max_downloads: int = 0,
    ) -> str:
        """Add a URL to the queue and start it if a slot is free. Returns job_id."""
        job_id = str(uuid.uuid4())
        job = DownloadJob(
            id            = job_id,
            url           = url,
            quality       = quality,
            output_dir    = output_dir or DEFAULT_DOWNLOAD_DIR,
            title         = title or url,
            playlist      = playlist,
            max_downloads = max_downloads,
        )
        self._jobs[job_id] = job
        logger.info("Enqueued download: %s  url=%s", job_id[:8], url)
        self.job_added.emit(job_id, url, job.title)
        self._try_start_next()
        return job_id

    def cancel(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        if job_id in self._active:
            _, worker = self._active[job_id]
            worker.cancel()
        job.status = JobStatus.CANCELLED
        job.message = "Cancelled"
        self.job_progress.emit(job_id, job.progress, "Cancelled")

    def remove(self, job_id: str) -> None:
        self.cancel(job_id)
        self._jobs.pop(job_id, None)
        self.job_removed.emit(job_id)

    def jobs(self) -> list[DownloadJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        return self._jobs.get(job_id)

    # ── internal ──────────────────────────────────────────────────────────────

    def _try_start_next(self) -> None:
        """Start queued jobs up to MAX_CONCURRENT."""
        running = sum(
            1 for j in self._jobs.values()
            if j.status == JobStatus.DOWNLOADING
        )
        for job in list(self._jobs.values()):
            if running >= MAX_CONCURRENT:
                break
            if job.status != JobStatus.QUEUED:
                continue
            self._start_job(job)
            running += 1

    def _start_job(self, job: DownloadJob) -> None:
        job.status  = JobStatus.DOWNLOADING
        job.message = "Starting…"
        self.job_progress.emit(job.id, 0, "Starting…")

        worker = _DownloadWorker(job)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.progress_changed.connect(
            lambda p, m, jid=job.id: self._on_progress(jid, p, m)
        )
        worker.finished.connect(
            lambda result, jid=job.id: self._on_finished(jid, result)
        )
        worker.failed.connect(
            lambda err, jid=job.id: self._on_failed(jid, err)
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda jid=job.id: self._active.pop(jid, None))
        thread.finished.connect(self._try_start_next)

        self._active[job.id] = (thread, worker)
        logger.info("Starting download job %s", job.id[:8])
        thread.start()

    def _on_progress(self, job_id: str, pct: int, msg: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.progress = pct
            job.message  = msg
        self.job_progress.emit(job_id, pct, msg)

    def _on_finished(self, job_id: str, result) -> None:
        job = self._jobs.get(job_id)
        if job:
            if result.success:
                job.status     = JobStatus.DONE
                job.output_path = str(result.output_path)
                job.title      = result.title or job.title
                job.progress   = 100
                job.message    = "Done"
            else:
                job.status  = JobStatus.FAILED
                job.error   = result.error
                job.message = f"Failed: {result.error[:60]}"
        self.job_finished.emit(
            job_id,
            result.success,
            str(result.output_path) if result.success else "",
        )

    def _on_failed(self, job_id: str, error: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.status  = JobStatus.FAILED
            job.error   = error
            job.message = f"Failed: {error[:60]}"
        self.job_finished.emit(job_id, False, "")