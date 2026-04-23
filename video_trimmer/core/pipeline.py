import threading
import uuid
from pathlib import Path
from typing import Callable

from video_trimmer.core.black_detector import BlackDetector
from video_trimmer.core.transcoder import Transcoder
from video_trimmer.core.trimmer import Trimmer
from video_trimmer.models.job import VideoJob, JobStatus
from video_trimmer.models.settings import AppSettings
from video_trimmer.utils.ffmpeg_runner import FFmpegRunner
from video_trimmer.utils.file_utils import (
    collect_video_files,
    get_output_extension,
    make_output_path,
)


def build_jobs(settings: AppSettings) -> list[VideoJob]:
    """Discover source files and create a VideoJob for each."""
    if not settings.source_path:
        return []
    files = collect_video_files(settings.source_path)
    return [
        VideoJob(id=str(uuid.uuid4()), source_path=f)
        for f in files
    ]


class ProcessingPipeline:
    def __init__(
        self,
        jobs: list[VideoJob],
        settings: AppSettings,
        on_job_update: Callable[[VideoJob], None],
        on_log: Callable[[str], None],
        on_complete: Callable[[], None],
        cancel_event: threading.Event,
    ):
        self._jobs = jobs
        self._settings = settings
        self._on_job_update = on_job_update
        self._on_log = on_log
        self._on_complete = on_complete
        self._cancel = cancel_event

        self._runner = FFmpegRunner(log_callback=on_log)
        self._detector = BlackDetector()
        self._trimmer = Trimmer()
        self._transcoder = Transcoder()

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return t

    def _run(self):
        s = self._settings
        for job in self._jobs:
            if self._cancel.is_set():
                break
            try:
                self._process_job(job, s)
            except Exception as exc:
                job.status = JobStatus.ERROR
                job.error_message = str(exc)
                self._on_log(f"ERROR: {exc}")
                self._on_job_update(job)

        self._on_complete()

    def _process_job(self, job: VideoJob, s: AppSettings):
        src = job.source_path
        self._on_log(f"\n── {src.name} ──")

        # 1. Detect trailing black
        job.status = JobStatus.DETECTING
        self._on_job_update(job)

        trim_point = self._detector.detect_trailing_black(
            source_path=src,
            threshold=s.black_threshold,
            min_duration=s.black_min_duration,
            trailing_tolerance=s.trailing_tolerance,
            runner=self._runner,
            log=self._on_log,
        )
        job.trim_point_seconds = trim_point
        if self._cancel.is_set():
            return

        # 2. Trim
        job.status = JobStatus.TRIMMING
        self._on_job_update(job)

        trim_folder = s.trim_output_folder or src.parent
        trim_ext = get_output_extension(src, s.trim_output_format)
        trim_out = make_output_path(src, trim_folder, "_trimmed", trim_ext)

        def trim_progress(v: float):
            job.progress_trim = v
            self._on_job_update(job)

        job.trim_output_path = self._trimmer.trim(
            source_path=src,
            trim_point=trim_point,
            output_path=trim_out,
            output_format=s.trim_output_format,
            runner=self._runner,
            progress_callback=trim_progress,
            cancel_event=self._cancel,
        )
        if self._cancel.is_set():
            return

        self._on_log(f"Trimmed → {trim_out.name}")

        # 3. Transcode
        job.status = JobStatus.TRANSCODING
        self._on_job_update(job)

        tc_folder = s.transcode_output_folder or src.parent
        tc_ext = f".{s.transcode_format}"
        tc_out = make_output_path(src, tc_folder, "_transcoded", tc_ext)

        def tc_progress(v: float):
            job.progress_transcode = v
            self._on_job_update(job)

        job.transcode_output_path = self._transcoder.transcode(
            source_path=job.trim_output_path,
            output_path=tc_out,
            codec=s.transcode_codec,
            crf=s.transcode_crf,
            profile=s.transcode_profile,
            runner=self._runner,
            progress_callback=tc_progress,
            cancel_event=self._cancel,
        )
        if self._cancel.is_set():
            return

        self._on_log(f"Transcoded → {tc_out.name}")
        job.status = JobStatus.DONE
        self._on_job_update(job)
