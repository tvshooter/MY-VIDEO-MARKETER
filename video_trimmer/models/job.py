from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path


class JobStatus(IntEnum):
    PENDING = 0
    DETECTING = 1
    TRIMMING = 2
    TRANSCODING = 3
    DONE = 4
    ERROR = 5
    SKIPPED = 6


STATUS_LABELS = {
    JobStatus.PENDING: "Pending",
    JobStatus.DETECTING: "Detecting",
    JobStatus.TRIMMING: "Trimming",
    JobStatus.TRANSCODING: "Transcoding",
    JobStatus.DONE: "Done",
    JobStatus.ERROR: "Error",
    JobStatus.SKIPPED: "No trim needed",
}

STATUS_COLORS = {
    JobStatus.PENDING: "#6b7280",
    JobStatus.DETECTING: "#3b82f6",
    JobStatus.TRIMMING: "#f59e0b",
    JobStatus.TRANSCODING: "#f97316",
    JobStatus.DONE: "#22c55e",
    JobStatus.ERROR: "#ef4444",
    JobStatus.SKIPPED: "#8b5cf6",
}


@dataclass
class VideoJob:
    id: str
    source_path: Path
    status: JobStatus = JobStatus.PENDING
    trim_output_path: Path | None = None
    transcode_output_path: Path | None = None
    trim_point_seconds: float | None = None
    error_message: str | None = None
    progress_trim: float = 0.0
    progress_transcode: float = 0.0

    @property
    def overall_progress(self) -> float:
        return (self.progress_trim + self.progress_transcode) / 2.0
