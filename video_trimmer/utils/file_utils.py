import subprocess
from pathlib import Path

from video_trimmer.models.settings import VIDEO_EXTENSIONS


def probe_duration(path: Path) -> float:
    """Return video duration in seconds via ffprobe, or 0 on failure."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def collect_video_files(path: Path) -> list[Path]:
    """Collect all video files from a file or directory."""
    if path.is_file():
        return [path] if path.suffix.lower() in VIDEO_EXTENSIONS else []
    files = sorted(
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    )
    return files


def make_output_path(source: Path, output_folder: Path, suffix: str, extension: str) -> Path:
    """Build output path, adding numeric suffix if file already exists."""
    base = output_folder / f"{source.stem}{suffix}{extension}"
    if not base.exists():
        return base
    counter = 1
    while True:
        candidate = output_folder / f"{source.stem}{suffix}_{counter}{extension}"
        if not candidate.exists():
            return candidate
        counter += 1


def get_output_extension(source: Path, format_setting: str) -> str:
    """Resolve the output file extension from a format setting string."""
    if format_setting == "keep":
        return source.suffix.lower()
    return f".{format_setting}"
