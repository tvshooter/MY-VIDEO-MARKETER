import re
from pathlib import Path
from typing import Callable

from video_trimmer.utils.ffmpeg_runner import FFmpegRunner
from video_trimmer.utils.file_utils import probe_duration


BLACKDETECT_RE = re.compile(
    r"\[blackdetect @ [0-9a-fx]+\] "
    r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)"
)


class BlackDetector:
    def detect_trailing_black(
        self,
        source_path: Path,
        threshold: float,
        min_duration: float,
        trailing_tolerance: float,
        runner: FFmpegRunner,
        log: Callable[[str], None] | None = None,
    ) -> float | None:
        """
        Return the trim point (seconds) at which trailing black begins, or None.

        Inter-scene black is ignored — only black that extends to the end of the
        clip (within trailing_tolerance seconds) is considered trailing.
        """
        _log = log or (lambda msg: None)

        duration = probe_duration(source_path)
        if duration <= 0:
            raise ValueError(f"Could not determine duration of {source_path.name}")

        _log(f"Duration: {duration:.2f}s  threshold={threshold}  min_dur={min_duration}s")

        cmd = [
            "ffmpeg", "-i", str(source_path),
            "-vf", f"blackdetect=d={min_duration}:pix_th={threshold}",
            "-an", "-f", "null", "-",
        ]
        _rc, _stdout, stderr = runner.run_capture(cmd)

        intervals: list[tuple[float, float, float]] = []
        for line in stderr.splitlines():
            m = BLACKDETECT_RE.search(line)
            if m:
                bs = float(m.group(1))
                be = float(m.group(2))
                bd = float(m.group(3))
                intervals.append((bs, be, bd))
                _log(f"  Black segment: {bs:.2f}s – {be:.2f}s  (dur={bd:.2f}s)")

        if not intervals:
            _log("No black segments detected.")
            return None

        # Find intervals whose end reaches (or nearly reaches) the clip end
        trailing = [iv for iv in intervals if iv[1] >= duration - trailing_tolerance]

        if not trailing:
            _log("No trailing black detected (all black is between scenes).")
            return None

        # Sort by start time; find earliest contiguous trailing block by walking
        # backward through all intervals to merge adjacent segments
        trailing.sort(key=lambda x: x[0])
        earliest_start = trailing[0][0]

        for iv in reversed(intervals):
            if iv[1] < earliest_start - trailing_tolerance:
                break
            if iv[0] < earliest_start:
                earliest_start = iv[0]

        # Safety guard: don't trim if result would be nearly empty
        if earliest_start < 1.0:
            _log("Trim point is within first second — skipping (possibly all-black source).")
            return None

        _log(f"Trailing black starts at {earliest_start:.3f}s — will trim here.")
        return earliest_start
