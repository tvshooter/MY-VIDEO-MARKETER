import re
import subprocess
import threading
from typing import Callable


TIME_RE = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")


class FFmpegNotFoundError(RuntimeError):
    pass


class FFmpegRunner:
    def __init__(self, log_callback: Callable[[str], None] | None = None):
        self._log = log_callback or (lambda msg: None)
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
        except FileNotFoundError:
            raise FFmpegNotFoundError(
                "ffmpeg not found. Run install.sh to install it."
            )

    def run_capture(self, cmd: list[str]) -> tuple[int, str, str]:
        """Run command and return (returncode, stdout, stderr). Blocks until complete."""
        self._log(f"$ {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    def run_with_progress(
        self,
        cmd: list[str],
        duration_seconds: float,
        progress_callback: Callable[[float], None],
        cancel_event: threading.Event,
    ) -> int:
        """
        Run an FFmpeg encode command, streaming stderr and firing progress_callback(0-1).
        Returns FFmpeg exit code.
        """
        self._log(f"$ {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            if cancel_event.is_set():
                proc.terminate()
                proc.wait()
                return -1

            m = TIME_RE.search(line)
            if m and duration_seconds > 0:
                h, mn, s, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                current = h * 3600 + mn * 60 + s + cs / 100
                progress_callback(min(current / duration_seconds, 1.0))

            line = line.rstrip()
            if line:
                self._log(line)

        proc.wait()
        if not cancel_event.is_set():
            progress_callback(1.0)
        return proc.returncode
