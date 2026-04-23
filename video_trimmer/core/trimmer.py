import shutil
import threading
from pathlib import Path
from typing import Callable

from video_trimmer.utils.ffmpeg_runner import FFmpegRunner
from video_trimmer.utils.file_utils import probe_duration


class Trimmer:
    def trim(
        self,
        source_path: Path,
        trim_point: float | None,
        output_path: Path,
        output_format: str,
        runner: FFmpegRunner,
        progress_callback: Callable[[float], None],
        cancel_event: threading.Event,
    ) -> Path:
        """
        Trim source_path to trim_point seconds and write to output_path.

        If trim_point is None: copy the source unchanged.
        If format matches source: stream-copy (fast, no re-encode).
        If format differs: re-encode at high quality for the trim step.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if trim_point is None:
            shutil.copy2(source_path, output_path)
            progress_callback(1.0)
            return output_path

        same_format = source_path.suffix.lower() == output_path.suffix.lower()
        duration = probe_duration(source_path)

        if same_format:
            # Stream copy — fast and lossless
            cmd = [
                "ffmpeg", "-y",
                "-i", str(source_path),
                "-t", str(trim_point),
                "-c", "copy",
                "-copyts",
                "-avoid_negative_ts", "make_zero",
                str(output_path),
            ]
        else:
            # Re-encode at high quality to convert format during trim
            cmd = [
                "ffmpeg", "-y",
                "-i", str(source_path),
                "-t", str(trim_point),
                "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                "-c:a", "aac", "-b:a", "256k",
                str(output_path),
            ]

        rc = runner.run_with_progress(cmd, trim_point or duration, progress_callback, cancel_event)
        if rc != 0 and not cancel_event.is_set():
            raise RuntimeError(f"FFmpeg trim failed (exit {rc}) for {source_path.name}")

        return output_path
