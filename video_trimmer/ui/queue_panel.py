import customtkinter as ctk

from video_trimmer.models.job import VideoJob, JobStatus, STATUS_LABELS, STATUS_COLORS


class JobRow(ctk.CTkFrame):
    def __init__(self, master, job: VideoJob, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._job_id = job.id

        name = job.source_path.name
        display = name if len(name) <= 48 else f"…{name[-47:]}"
        self._name_label = ctk.CTkLabel(self, text=display, anchor="w", width=340,
                                        font=ctk.CTkFont(size=11))
        self._name_label.grid(row=0, column=0, padx=(4, 8), pady=2, sticky="w")

        self._status_label = ctk.CTkLabel(
            self, text=STATUS_LABELS[job.status], width=110,
            fg_color=STATUS_COLORS[job.status], corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"), text_color="white"
        )
        self._status_label.grid(row=0, column=1, padx=4, pady=2)

        self._progress_bar = ctk.CTkProgressBar(self, width=160, height=10)
        self._progress_bar.set(0)
        self._progress_bar.grid(row=0, column=2, padx=(4, 8), pady=2)

        self._pct_label = ctk.CTkLabel(self, text="0%", width=36, font=ctk.CTkFont(size=11))
        self._pct_label.grid(row=0, column=3, padx=(0, 4), pady=2)

    def update(self, job: VideoJob):
        self._status_label.configure(
            text=STATUS_LABELS[job.status],
            fg_color=STATUS_COLORS[job.status],
        )
        p = job.overall_progress
        self._progress_bar.set(p)
        self._pct_label.configure(text=f"{int(p * 100)}%")


class FileQueuePanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._rows: dict[str, JobRow] = {}

        ctk.CTkLabel(self, text="FILES TO PROCESS", font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 4)
        )

        self._scroll = ctk.CTkScrollableFrame(self, height=160)
        self._scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._empty_label = ctk.CTkLabel(
            self._scroll, text="No files loaded yet.", text_color="gray"
        )
        self._empty_label.pack(pady=20)

    def set_jobs(self, jobs: list[VideoJob]):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._rows.clear()

        if not jobs:
            self._empty_label = ctk.CTkLabel(
                self._scroll, text="No files loaded yet.", text_color="gray"
            )
            self._empty_label.pack(pady=20)
            return

        for job in jobs:
            row = JobRow(self._scroll, job)
            row.pack(fill="x", pady=1)
            self._rows[job.id] = row

    def update_job(self, job: VideoJob):
        row = self._rows.get(job.id)
        if row:
            row.update(job)
