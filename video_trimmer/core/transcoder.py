import threading
from pathlib import Path
from typing import Callable

from video_trimmer.utils.ffmpeg_runner import FFmpegRunner
from video_trimmer.utils.file_utils import probe_duration


class Transcoder:
    def transcode(
        self,
        source_path: Path,
        output_path: Path,
        codec: str,
        crf: int,
        profile: str,
        runner: FFmpegRunner,
        progress_callback: Callable[[float], None],
        cancel_event: threading.Event,
    ) -> Path:
        """Transcode source_path to output_path using the specified codec/profile."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = probe_duration(source_path)

        cmd = ["ffmpeg", "-y", "-i", str(source_path)]
        cmd += self._build_video_args(codec, crf, profile)
        cmd += self._build_audio_args(codec)
        cmd += self._build_container_args(codec, output_path)
        cmd.append(str(output_path))

        rc = runner.run_with_progress(cmd, duration, progress_callback, cancel_event)
        if rc != 0 and not cancel_event.is_set():
            raise RuntimeError(f"FFmpeg transcode failed (exit {rc}) for {source_path.name}")

        return output_path

    def _build_video_args(self, codec: str, crf: int, profile: str) -> list[str]:
        if codec == "copy":
            return ["-c:v", "copy"]
        if codec == "libx264":
            return ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium"]
        if codec == "libx265":
            return ["-c:v", "libx265", "-crf", str(crf), "-preset", "medium", "-tag:v", "hvc1"]
        if codec == "libvpx-vp9":
            return ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0"]
        if codec == "prores_ks":
            p = profile if profile else "3"  # default ProRes 422 HQ
            return ["-c:v", "prores_ks", "-profile:v", p, "-vendor", "apl0", "-pix_fmt", "yuv422p10le"]
        if codec == "dnxhd":
            p = profile if profile else "dnxhr_sq"
            return ["-c:v", "dnxhd", "-profile:v", p, "-pix_fmt", "yuv422p"]
        return ["-c:v", codec]

    def _build_audio_args(self, codec: str) -> list[str]:
        if codec == "copy":
            return ["-c:a", "copy"]
        if codec == "libvpx-vp9":
            return ["-c:a", "libopus"]
        if codec in ("prores_ks", "dnxhd"):
            return ["-c:a", "pcm_s16le"]
        return ["-c:a", "aac", "-b:a", "192k"]

    def _build_container_args(self, codec: str, output_path: Path) -> list[str]:
        ext = output_path.suffix.lower()
        if ext == ".mp4":
            return ["-movflags", "+faststart"]
        return []
