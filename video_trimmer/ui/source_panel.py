from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk


class SourcePanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._mode = ctk.StringVar(value="file")

        ctk.CTkLabel(self, text="SOURCE", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4)
        )

        self._path_var = ctk.StringVar()
        self._entry = ctk.CTkEntry(self, textvariable=self._path_var, width=480, placeholder_text="Select a file or folder…")
        self._entry.grid(row=1, column=0, columnspan=2, padx=(12, 6), pady=4, sticky="ew")

        self._browse_btn = ctk.CTkButton(self, text="Browse…", width=90, command=self._browse)
        self._browse_btn.grid(row=1, column=2, padx=(0, 12), pady=4)

        ctk.CTkRadioButton(self, text="Single file", variable=self._mode, value="file",
                           command=self._on_mode_change).grid(
            row=2, column=0, padx=(12, 0), pady=(2, 10), sticky="w"
        )
        ctk.CTkRadioButton(self, text="Folder (batch)", variable=self._mode, value="folder",
                           command=self._on_mode_change).grid(
            row=2, column=1, padx=(4, 0), pady=(2, 10), sticky="w"
        )

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _on_mode_change(self):
        self._path_var.set("")

    def _browse(self):
        if self._mode.get() == "file":
            path = filedialog.askopenfilename(
                title="Select video file",
                filetypes=[
                    ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mxf *.ts *.mts *.m2ts"),
                    ("All files", "*.*"),
                ],
            )
        else:
            path = filedialog.askdirectory(title="Select folder containing videos")
        if path:
            self._path_var.set(path)

    def get_source(self) -> tuple[Path | None, str]:
        p = self._path_var.get().strip()
        return (Path(p) if p else None), self._mode.get()
