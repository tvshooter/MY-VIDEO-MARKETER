from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppSettings:
    source_path: Path | None = None
    source_mode: str = "file"               # "file" | "folder"

    trim_output_folder: Path | None = None
    trim_output_format: str = "keep"        # "keep" | "mp4" | "mov" | "mkv" | "avi"

    transcode_output_folder: Path | None = None
    transcode_format: str = "mp4"
    transcode_codec: str = "libx264"
    transcode_crf: int = 23
    transcode_profile: str = ""             # for ProRes / DNxHD profiles

    black_threshold: float = 0.10
    black_min_duration: float = 2.0
    trailing_tolerance: float = 0.5


FORMAT_EXTENSIONS = {
    "keep": None,
    "mp4": ".mp4",
    "mov": ".mov",
    "mkv": ".mkv",
    "avi": ".avi",
    "webm": ".webm",
}

CODEC_IDS = {
    "H.264 (libx264)": "libx264",
    "H.265 (libx265)": "libx265",
    "VP9 (libvpx-vp9)": "libvpx-vp9",
    "Apple ProRes": "prores_ks",
    "Avid DNxHD/DNxHR": "dnxhd",
    "Copy (remux)": "copy",
}

PRORES_PROFILES = {
    "ProRes 422 Proxy": "0",
    "ProRes 422 LT": "1",
    "ProRes 422": "2",
    "ProRes 422 HQ": "3",
    "ProRes 4444": "4",
    "ProRes 4444 XQ": "5",
}

DNXHD_PROFILES = {
    "DNxHD 36 (1080p 29.97)": "dnxhd_1080p_29.97_36Mbps",
    "DNxHD 115 (1080p 29.97)": "dnxhd_1080p_29.97_115Mbps",
    "DNxHD 185 (1080p 29.97)": "dnxhd_1080p_29.97_185Mbps",
    "DNxHD 185x (1080p 29.97)": "dnxhd_1080p_29.97_185Mbps_10bit",
    "DNxHR LB": "dnxhr_lb",
    "DNxHR SQ": "dnxhr_sq",
    "DNxHR HQ": "dnxhr_hq",
    "DNxHR HQX": "dnxhr_hqx",
    "DNxHR 444": "dnxhr_444",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mxf", ".ts", ".mts", ".m2ts"}
