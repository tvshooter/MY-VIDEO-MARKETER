from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk


FORMAT_OPTIONS = ["Keep Original", "MP4", "MOV", "MKV", "AVI"]
FORMAT_VALUES = {"Keep Original": "keep", "MP4": "mp4", "MOV": "mov", "MKV": "mkv", "AVI": "avi"}


class TrimSettingsPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        ctk.CTkLabel(self, text="TRIM SETTINGS", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4)
        )

        # Output folder
        ctk.CTkLabel(self, text="Trimmed output folder:").grid(row=1, column=0, padx=(12, 6), pady=4, sticky="w")
        self._folder_var = ctk.StringVar(value="")
        self._folder_entry = ctk.CTkEntry(self, textvariable=self._folder_var, width=340, placeholder_text="Same folder as source")
        self._folder_entry.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(self, text="Browse…", width=90, command=self._browse_folder).grid(row=1, column=2, padx=(0, 12), pady=4)

        # Output format
        ctk.CTkLabel(self, text="Output format:").grid(row=2, column=0, padx=(12, 6), pady=4, sticky="w")
        self._format_menu = ctk.CTkOptionMenu(self, values=FORMAT_OPTIONS, width=200)
        self._format_menu.set("Keep Original")
        self._format_menu.grid(row=2, column=1, padx=4, pady=4, sticky="w")

        # Black threshold slider
        ctk.CTkLabel(self, text="Black threshold:").grid(row=3, column=0, padx=(12, 6), pady=4, sticky="w")
        self._threshold_label = ctk.CTkLabel(self, text="0.10", width=50)
        self._threshold_slider = ctk.CTkSlider(
            self, from_=0.01, to=0.50, number_of_steps=49,
            command=lambda v: self._threshold_label.configure(text=f"{v:.2f}")
        )
        self._threshold_slider.set(0.10)
        self._threshold_slider.grid(row=3, column=1, padx=4, pady=4, sticky="ew")
        self._threshold_label.grid(row=3, column=2, padx=(0, 12), pady=4)

        # Min black duration slider
        ctk.CTkLabel(self, text="Min black duration:").grid(row=4, column=0, padx=(12, 6), pady=(4, 10), sticky="w")
        self._mindur_label = ctk.CTkLabel(self, text="2.0s", width=50)
        self._mindur_slider = ctk.CTkSlider(
            self, from_=0.5, to=10.0, number_of_steps=19,
            command=lambda v: self._mindur_label.configure(text=f"{v:.1f}s")
        )
        self._mindur_slider.set(2.0)
        self._mindur_slider.grid(row=4, column=1, padx=4, pady=(4, 10), sticky="ew")
        self._mindur_label.grid(row=4, column=2, padx=(0, 12), pady=(4, 10))

        self.columnconfigure(1, weight=1)

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select trimmed output folder")
        if path:
            self._folder_var.set(path)

    def get_trim_folder(self) -> Path | None:
        p = self._folder_var.get().strip()
        return Path(p) if p else None

    def get_format(self) -> str:
        return FORMAT_VALUES[self._format_menu.get()]

    def get_threshold(self) -> float:
        return round(self._threshold_slider.get(), 2)

    def get_min_duration(self) -> float:
        return round(self._mindur_slider.get(), 1)
