from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from video_trimmer.models.settings import (
    CODEC_IDS,
    PRORES_PROFILES,
    DNXHD_PROFILES,
)


FORMAT_OPTIONS = ["MP4", "MOV", "MKV", "AVI", "WebM"]
FORMAT_VALUES = {"MP4": "mp4", "MOV": "mov", "MKV": "mkv", "AVI": "avi", "WebM": "webm"}

CODEC_OPTIONS = list(CODEC_IDS.keys())

# Codec → forced container (None = user's choice)
CODEC_FORCED_FORMAT = {
    "libvpx-vp9": "WebM",
    "prores_ks": "MOV",
}

# Codec → profile list
CODEC_PROFILES: dict[str, dict[str, str]] = {
    "prores_ks": PRORES_PROFILES,
    "dnxhd": DNXHD_PROFILES,
}


class TranscodeSettingsPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        ctk.CTkLabel(self, text="TRANSCODE SETTINGS", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4)
        )

        # Output folder
        ctk.CTkLabel(self, text="Transcode output folder:").grid(row=1, column=0, padx=(12, 6), pady=4, sticky="w")
        self._folder_var = ctk.StringVar()
        self._folder_entry = ctk.CTkEntry(self, textvariable=self._folder_var, width=340, placeholder_text="Same folder as source")
        self._folder_entry.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(self, text="Browse…", width=90, command=self._browse_folder).grid(row=1, column=2, padx=(0, 12), pady=4)

        # Format
        ctk.CTkLabel(self, text="Output format:").grid(row=2, column=0, padx=(12, 6), pady=4, sticky="w")
        self._format_menu = ctk.CTkOptionMenu(self, values=FORMAT_OPTIONS, width=180, command=self._on_format_change)
        self._format_menu.set("MP4")
        self._format_menu.grid(row=2, column=1, padx=4, pady=4, sticky="w")

        # Codec
        ctk.CTkLabel(self, text="Video codec:").grid(row=3, column=0, padx=(12, 6), pady=4, sticky="w")
        self._codec_menu = ctk.CTkOptionMenu(self, values=CODEC_OPTIONS, width=220, command=self._on_codec_change)
        self._codec_menu.set("H.264 (libx264)")
        self._codec_menu.grid(row=3, column=1, padx=4, pady=4, sticky="w")

        # CRF slider
        self._crf_row_label = ctk.CTkLabel(self, text="Quality (CRF):")
        self._crf_row_label.grid(row=4, column=0, padx=(12, 6), pady=4, sticky="w")
        self._crf_label = ctk.CTkLabel(self, text="23", width=50)
        self._crf_slider = ctk.CTkSlider(
            self, from_=0, to=51, number_of_steps=51,
            command=lambda v: self._crf_label.configure(text=str(int(v)))
        )
        self._crf_slider.set(23)
        self._crf_slider.grid(row=4, column=1, padx=4, pady=4, sticky="ew")
        self._crf_label.grid(row=4, column=2, padx=(0, 12), pady=4)

        # Profile dropdown (hidden unless ProRes or DNxHD selected)
        self._profile_row_label = ctk.CTkLabel(self, text="Profile:")
        self._profile_menu = ctk.CTkOptionMenu(self, values=["—"], width=220)
        self._profile_menu.set("—")
        # Profile row is hidden initially; shown via _on_codec_change

        self.columnconfigure(1, weight=1)

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select transcode output folder")
        if path:
            self._folder_var.set(path)

    def _on_format_change(self, _value: str):
        pass  # Format changes are user-driven unless codec forces one

    def _on_codec_change(self, codec_label: str):
        codec_id = CODEC_IDS.get(codec_label, "")

        # Force container for VP9 and ProRes
        forced = CODEC_FORCED_FORMAT.get(codec_id)
        if forced:
            self._format_menu.set(forced)
            self._format_menu.configure(state="disabled")
        else:
            self._format_menu.configure(state="normal")

        # CRF not applicable for ProRes / DNxHD / copy
        if codec_id in ("prores_ks", "dnxhd", "copy"):
            self._crf_slider.configure(state="disabled")
            self._crf_row_label.configure(text_color="gray")
            self._crf_label.configure(text_color="gray")
        else:
            self._crf_slider.configure(state="normal")
            self._crf_row_label.configure(text_color=("gray10", "gray90"))
            self._crf_label.configure(text_color=("gray10", "gray90"))

        # Show / hide profile selector
        if codec_id in CODEC_PROFILES:
            profiles = list(CODEC_PROFILES[codec_id].keys())
            self._profile_menu.configure(values=profiles)
            self._profile_menu.set(profiles[0])
            self._profile_row_label.grid(row=5, column=0, padx=(12, 6), pady=(4, 10), sticky="w")
            self._profile_menu.grid(row=5, column=1, padx=4, pady=(4, 10), sticky="w")
        else:
            self._profile_row_label.grid_remove()
            self._profile_menu.grid_remove()

    def get_transcode_folder(self) -> Path | None:
        p = self._folder_var.get().strip()
        return Path(p) if p else None

    def get_format(self) -> str:
        return FORMAT_VALUES[self._format_menu.get()]

    def get_codec(self) -> str:
        return CODEC_IDS[self._codec_menu.get()]

    def get_crf(self) -> int:
        return int(self._crf_slider.get())

    def get_profile(self) -> str:
        codec_id = CODEC_IDS.get(self._codec_menu.get(), "")
        if codec_id in CODEC_PROFILES:
            label = self._profile_menu.get()
            return CODEC_PROFILES[codec_id].get(label, "")
        return ""
