import os
import threading

import customtkinter as ctk

from video_trimmer.core.pipeline import ProcessingPipeline, build_jobs
from video_trimmer.models.job import VideoJob
from video_trimmer.models.settings import AppSettings
from video_trimmer.ui.log_panel import LogPanel
from video_trimmer.ui.queue_panel import FileQueuePanel
from video_trimmer.ui.source_panel import SourcePanel
from video_trimmer.ui.transcode_panel import TranscodeSettingsPanel
from video_trimmer.ui.trim_panel import TrimSettingsPanel


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Video Trim & Transcode")
        self.geometry("860x960")
        self.resizable(True, True)

        self._jobs: list[VideoJob] = []
        self._pipeline: ProcessingPipeline | None = None
        self._cancel_event = threading.Event()

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        outer = ctk.CTkScrollableFrame(self)
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        # Header
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            header,
            text="Video Trim & Transcode",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left", padx=4)

        # Panels
        self._source_panel = SourcePanel(outer, corner_radius=8)
        self._source_panel.pack(fill="x", pady=4)

        self._trim_panel = TrimSettingsPanel(outer, corner_radius=8)
        self._trim_panel.pack(fill="x", pady=4)

        self._transcode_panel = TranscodeSettingsPanel(outer, corner_radius=8)
        self._transcode_panel.pack(fill="x", pady=4)

        # Action buttons
        btn_frame = ctk.CTkFrame(outer, fg_color="transparent")
        btn_frame.pack(fill="x", pady=6)

        self._start_btn = ctk.CTkButton(
            btn_frame, text="▶  Start Processing",
            width=200, height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#22c55e", hover_color="#16a34a",
            command=self._on_start,
        )
        self._start_btn.pack(side="left", padx=(4, 8))

        self._cancel_btn = ctk.CTkButton(
            btn_frame, text="✕  Cancel",
            width=120, height=40,
            font=ctk.CTkFont(size=14),
            fg_color="#ef4444", hover_color="#dc2626",
            state="disabled",
            command=self._on_cancel,
        )
        self._cancel_btn.pack(side="left")

        # Overall progress bar
        self._overall_bar = ctk.CTkProgressBar(outer, height=12)
        self._overall_bar.set(0)
        self._overall_bar.pack(fill="x", padx=4, pady=(4, 0))

        self._overall_label = ctk.CTkLabel(outer, text="", font=ctk.CTkFont(size=11))
        self._overall_label.pack(anchor="w", padx=8)

        # File queue
        self._queue_panel = FileQueuePanel(outer, corner_radius=8)
        self._queue_panel.pack(fill="x", pady=4)

        # Log
        self._log_panel = LogPanel(outer, corner_radius=8)
        self._log_panel.pack(fill="both", expand=True, pady=4)

    # ── Actions ────────────────────────────────────────────────────────────

    def _on_start(self):
        source_path, source_mode = self._source_panel.get_source()
        if not source_path:
            self._show_error("Please select a source file or folder.")
            return

        if not source_path.exists():
            self._show_error(f"Source path does not exist:\n{source_path}")
            return

        trim_folder = self._trim_panel.get_trim_folder()
        tc_folder = self._transcode_panel.get_transcode_folder()

        if trim_folder and not trim_folder.exists():
            self._show_error(f"Trim output folder does not exist:\n{trim_folder}")
            return
        if tc_folder and not tc_folder.exists():
            self._show_error(f"Transcode output folder does not exist:\n{tc_folder}")
            return

        settings = AppSettings(
            source_path=source_path,
            source_mode=source_mode,
            trim_output_folder=trim_folder,
            trim_output_format=self._trim_panel.get_format(),
            transcode_output_folder=tc_folder,
            transcode_format=self._transcode_panel.get_format(),
            transcode_codec=self._transcode_panel.get_codec(),
            transcode_crf=self._transcode_panel.get_crf(),
            transcode_profile=self._transcode_panel.get_profile(),
            black_threshold=self._trim_panel.get_threshold(),
            black_min_duration=self._trim_panel.get_min_duration(),
        )

        self._jobs = build_jobs(settings)
        if not self._jobs:
            self._show_error("No video files found at the selected source.")
            return

        self._log_panel.clear()
        self._queue_panel.set_jobs(self._jobs)
        self._overall_bar.set(0)
        self._overall_label.configure(text=f"0 / {len(self._jobs)} files complete")

        self._cancel_event.clear()
        self._start_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")

        self._pipeline = ProcessingPipeline(
            jobs=self._jobs,
            settings=settings,
            on_job_update=self._on_job_update,
            on_log=self._log_panel.append,
            on_complete=self._on_complete,
            cancel_event=self._cancel_event,
        )
        self._pipeline.start()

    def _on_cancel(self):
        self._cancel_event.set()
        self._log_panel.append("Cancelling… waiting for current operation to finish.")
        self._cancel_btn.configure(state="disabled")

    def _on_job_update(self, job: VideoJob):
        """Called from worker thread — dispatch to GUI thread."""
        self.after(0, self._apply_job_update, job)

    def _apply_job_update(self, job: VideoJob):
        self._queue_panel.update_job(job)
        done = sum(1 for j in self._jobs if j.status.value >= 4)
        total = len(self._jobs)
        if total > 0:
            avg_progress = sum(j.overall_progress for j in self._jobs) / total
            self._overall_bar.set(avg_progress)
            self._overall_label.configure(text=f"{done} / {total} files complete")

    def _on_complete(self):
        self.after(0, self._finish_ui)

    def _finish_ui(self):
        self._start_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._overall_bar.set(1.0)
        done = sum(1 for j in self._jobs if j.status.value == 4)
        errors = sum(1 for j in self._jobs if j.status.value == 5)
        self._log_panel.append(
            f"\n── Complete: {done} succeeded, {errors} failed ──"
        )

    def _show_error(self, msg: str):
        win = ctk.CTkToplevel(self)
        win.title("Error")
        win.geometry("420x160")
        win.grab_set()
        ctk.CTkLabel(win, text=msg, wraplength=380).pack(pady=24, padx=20)
        ctk.CTkButton(win, text="OK", command=win.destroy).pack(pady=8)
