#!/usr/bin/env python3
"""
Film Transfer Color Correction — GUI
--------------------------------------
Point-and-click launcher for the film color correction pipeline.
Drag folders, set settings, press Run.

Pipeline per job:
  Gray World color balance → Gamma → Auto Levels → Noise Reduction (optional)
  → ProRes .mov  OR  corrected TIFF folder

Requirements:
    pip install Pillow numpy
    pip install opencv-python   ← required for noise reduction
    brew install ffmpeg
"""

import os
import re
import sys
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from PIL import Image

# OpenCV is optional — noise reduction controls are disabled if not installed
try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# ─── Configuration defaults ───────────────────────────────────────────────────

GAMMA_DEFAULT            = 1.8
CLIP_DEFAULT             = 0.1
FPS_DEFAULT              = 17.0
SAMPLE_FRAME_COUNT       = 7
PRORES_PROFILES          = {"Proxy (0)": 0, "LT (1)": 1, "422 (2)": 2, "HQ (3)": 3}
PRORES_DEFAULT           = "422 (2)"
NR_STRENGTH_DEFAULT      = 10
NR_STRENGTH_MIN          = 1
NR_STRENGTH_MAX          = 30

# ─── Helpers ──────────────────────────────────────────────────────────────────

def disk_free_str(path):
    """Return a human-readable free-space string for the drive containing path."""
    try:
        if not path or not os.path.exists(path):
            return "—"
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024 ** 3)
        total_gb = stat.total / (1024 ** 3)
        return f"{free_gb:.1f} GB free of {total_gb:.1f} GB"
    except Exception:
        return "—"


def get_tif_frames(job_folder):
    frames = [
        f for f in os.listdir(job_folder)
        if f.lower().endswith('.tif') and not f.startswith('.')
    ]
    def frame_number(fname):
        m = re.search(r'(\d+)\.tif$', fname, re.IGNORECASE)
        return int(m.group(1)) if m else 0
    frames.sort(key=frame_number)
    return frames


def gray_world_correction(frame_files, job_folder, log):
    total = len(frame_files)
    sample_count = min(SAMPLE_FRAME_COUNT, total)
    indices = (
        [int(round(i * (total - 1) / (sample_count - 1))) for i in range(sample_count)]
        if sample_count > 1 else [total // 2]
    )
    r_means, g_means, b_means = [], [], []
    for i in indices:
        img = Image.open(os.path.join(job_folder, frame_files[i])).convert('RGB')
        arr = np.array(img, dtype=np.float32)
        r_means.append(arr[:, :, 0].mean())
        g_means.append(arr[:, :, 1].mean())
        b_means.append(arr[:, :, 2].mean())
    r_mean = np.mean(r_means)
    g_mean = np.mean(g_means)
    b_mean = np.mean(b_means)
    gray   = (r_mean + g_mean + b_mean) / 3.0
    r_scale = gray / r_mean if r_mean > 0 else 1.0
    g_scale = gray / g_mean if g_mean > 0 else 1.0
    b_scale = gray / b_mean if b_mean > 0 else 1.0
    log(f"    Sampled {sample_count} frames")
    log(f"    Channel means  → R:{r_mean:.1f}  G:{g_mean:.1f}  B:{b_mean:.1f}")
    log(f"    Scale factors  → R:{r_scale:.3f}  G:{g_scale:.3f}  B:{b_scale:.3f}")
    return r_scale, g_scale, b_scale


def apply_gamma(arr, gamma):
    normalized = arr / 255.0
    lifted = np.power(np.clip(normalized, 0, 1), 1.0 / gamma)
    return lifted * 255.0


def apply_auto_levels(arr, clip_percent):
    result = np.zeros_like(arr)
    clip_low  = clip_percent / 100.0
    clip_high = 1.0 - clip_low
    for ch in range(3):
        channel = arr[:, :, ch]
        lo = np.quantile(channel, clip_low)
        hi = np.quantile(channel, clip_high)
        stretched = (channel - lo) / (hi - lo) * 255.0 if hi > lo else channel
        result[:, :, ch] = np.clip(stretched, 0, 255)
    return result


def apply_noise_reduction(arr_uint8, strength):
    """
    Non-Local Means denoising on an RGB uint8 NumPy array.

    strength maps to the NLM 'h' parameter (filter strength).
    Higher values remove more noise but soften fine detail.
    Typical range: 1–30. Default: 10.
    """
    bgr = cv2.cvtColor(arr_uint8, cv2.COLOR_RGB2BGR)
    denoised = cv2.fastNlMeansDenoisingColored(
        bgr, None,
        h=float(strength),
        hColor=float(strength),
        templateWindowSize=7,
        searchWindowSize=21,
    )
    return cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)


def process_frame(input_path, output_path, r_scale, g_scale, b_scale, gamma, clip,
                  nr_enabled=False, nr_strength=NR_STRENGTH_DEFAULT):
    """Color-correct one TIFF frame, optionally apply noise reduction, save."""
    img = Image.open(input_path).convert('RGB')
    arr = np.array(img, dtype=np.float32)

    # Gray world color balance
    arr[:, :, 0] = np.clip(arr[:, :, 0] * r_scale, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * g_scale, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * b_scale, 0, 255)

    # Gamma lift
    arr = apply_gamma(arr, gamma)

    # Auto levels
    arr = apply_auto_levels(arr, clip)

    # Noise reduction (after color correction, before save)
    if nr_enabled:
        arr = apply_noise_reduction(arr.astype(np.uint8), nr_strength).astype(np.float32)

    Image.fromarray(arr.astype(np.uint8)).save(output_path, format='TIFF')


def assemble_mov(corrected_folder, job_name, fps, output_folder, prores_profile, log):
    input_pattern = os.path.join(corrected_folder, "frame_%05d.tif")
    output_path   = os.path.join(output_folder, f"{job_name}.mov")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-c:v", "prores_ks",
        "-profile:v", str(prores_profile),
        "-pix_fmt", "yuv422p10le",
        output_path
    ]
    log(f"    Assembling {job_name}.mov ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"    ✗ FFmpeg error:\n{result.stderr[-800:]}")
        return False
    log(f"    ✓ Saved: {output_path}")
    return True


def cleanup_temp(corrected_folder, log):
    """Delete the temp corrected frames folder after a successful .mov assembly."""
    try:
        shutil.rmtree(corrected_folder)
        log(f"    ✓ Temp frames deleted: {corrected_folder}")
    except Exception as e:
        log(f"    ⚠  Could not delete temp folder: {e}")


def move_tiff_output(src_dir, dest_dir, log):
    """
    Move corrected TIFF frames from temp dir to a named output subfolder.
    Uses shutil.move — a rename on the same filesystem (fast, atomic).
    Raises FileExistsError if dest_dir already exists to prevent silent overwrites.
    """
    if os.path.exists(dest_dir):
        raise FileExistsError(
            f"Output folder already exists: {dest_dir}\n"
            "Delete or rename it before re-running this job."
        )
    shutil.move(src_dir, dest_dir)
    log(f"    ✓ Corrected TIFFs saved: {dest_dir}")


# ─── GUI ──────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Film Transfer Color Correction")
        self.resizable(False, False)
        self._stop_flag = threading.Event()
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        PAD = 12

        # ── Header ───────────────────────────────────────────────────────────
        header = tk.Frame(self, bg="#1c1c1e")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 0))
        tk.Label(
            header,
            text="🎞  Film Transfer Color Correction",
            font=("SF Pro Display", 16, "bold"),
            bg="#1c1c1e", fg="white",
            pady=14, padx=PAD
        ).pack(side="left")

        # ── Main body ─────────────────────────────────────────────────────────
        body = tk.Frame(self, padx=PAD, pady=PAD, bg="#f2f2f7")
        body.grid(row=1, column=0, sticky="nsew")

        # ── Folders section ──────────────────────────────────────────────────
        self._section_label(body, "Folders", row=0)

        # Watch Folder
        self.watch_var = tk.StringVar()
        self.watch_disk_var = tk.StringVar(value="—")
        self._folder_row(body, "Watch folder", self.watch_var, self.watch_disk_var,
                         row=1, tooltip="Folder containing one subfolder per reel")

        # Temp Frames Folder
        self.temp_var = tk.StringVar()
        self.temp_disk_var = tk.StringVar(value="—")
        self._folder_row(body, "Temp frames", self.temp_var, self.temp_disk_var,
                         row=2, tooltip="Where corrected frames are written during processing")

        # Output Folder
        self.output_var = tk.StringVar(value="/Volumes/Current Film Projects/AUTO COLOR CORRECT")
        self.output_disk_var = tk.StringVar(value="—")
        self._folder_row(body, "Output folder", self.output_var, self.output_disk_var,
                         row=3, tooltip="Where finished .mov files or corrected TIFF folders are saved")

        sep1 = ttk.Separator(body, orient="horizontal")
        sep1.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(10, 6))

        # ── Settings section ─────────────────────────────────────────────────
        self._section_label(body, "Settings", row=5)

        settings_frame = tk.Frame(body, bg="#f2f2f7")
        settings_frame.grid(row=6, column=0, columnspan=4, sticky="w", pady=(4, 0))

        # Frame rate
        tk.Label(settings_frame, text="Frame rate (fps)", bg="#f2f2f7",
                 font=("SF Pro Text", 11)).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.fps_var = tk.StringVar(value=str(FPS_DEFAULT))
        self.fps_entry = tk.Entry(settings_frame, textvariable=self.fps_var, width=8,
                                  font=("SF Pro Text", 11))
        self.fps_entry.grid(row=0, column=1, sticky="w", padx=(0, 24))

        # Gamma
        tk.Label(settings_frame, text="Gamma", bg="#f2f2f7",
                 font=("SF Pro Text", 11)).grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.gamma_var = tk.StringVar(value=str(GAMMA_DEFAULT))
        gamma_entry = tk.Entry(settings_frame, textvariable=self.gamma_var, width=8,
                               font=("SF Pro Text", 11))
        gamma_entry.grid(row=0, column=3, sticky="w", padx=(0, 24))

        # Auto levels clip %
        tk.Label(settings_frame, text="Auto levels clip %", bg="#f2f2f7",
                 font=("SF Pro Text", 11)).grid(row=0, column=4, sticky="w", padx=(0, 8))
        self.clip_var = tk.StringVar(value=str(CLIP_DEFAULT))
        clip_entry = tk.Entry(settings_frame, textvariable=self.clip_var, width=8,
                              font=("SF Pro Text", 11))
        clip_entry.grid(row=0, column=5, sticky="w", padx=(0, 24))

        # ProRes profile
        tk.Label(settings_frame, text="ProRes profile", bg="#f2f2f7",
                 font=("SF Pro Text", 11)).grid(row=0, column=6, sticky="w", padx=(0, 8))
        self.prores_var = tk.StringVar(value=PRORES_DEFAULT)
        self.prores_menu = ttk.Combobox(settings_frame, textvariable=self.prores_var,
                                        values=list(PRORES_PROFILES.keys()),
                                        state="readonly", width=10,
                                        font=("SF Pro Text", 11))
        self.prores_menu.grid(row=0, column=7, sticky="w")

        sep2 = ttk.Separator(body, orient="horizontal")
        sep2.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(10, 6))

        # ── Noise Reduction section ──────────────────────────────────────────
        nr_title = "Noise Reduction" if _CV2_AVAILABLE else "Noise Reduction  (requires: pip install opencv-python)"
        nr_frame = ttk.LabelFrame(body, text=nr_title, padding=(10, 6))
        nr_frame.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(4, 6))

        self.nr_enabled_var = tk.BooleanVar(value=False)
        nr_cb = ttk.Checkbutton(
            nr_frame,
            text="Enable noise reduction",
            variable=self.nr_enabled_var,
            command=self._on_nr_toggle,
            state="normal" if _CV2_AVAILABLE else "disabled",
        )
        nr_cb.grid(row=0, column=0, sticky="w", padx=(0, 24))

        tk.Label(nr_frame, text="Strength (1–30):",
                 font=("SF Pro Text", 11)).grid(row=0, column=1, sticky="w", padx=(0, 6))

        self.nr_strength_var = tk.IntVar(value=NR_STRENGTH_DEFAULT)
        self.nr_strength_entry = tk.Entry(nr_frame, textvariable=self.nr_strength_var,
                                          width=5, font=("SF Pro Text", 11))
        self.nr_strength_entry.grid(row=0, column=2, sticky="w", padx=(0, 10))

        self.nr_strength_scale = ttk.Scale(
            nr_frame,
            from_=NR_STRENGTH_MIN, to=NR_STRENGTH_MAX,
            orient="horizontal",
            variable=self.nr_strength_var,
            length=160,
        )
        self.nr_strength_scale.grid(row=0, column=3, sticky="w")

        tk.Label(nr_frame,
                 text="Higher = smoother / less grain detail",
                 font=("SF Pro Text", 9), fg="#888"
                 ).grid(row=0, column=4, sticky="w", padx=(12, 0))

        # Clamp scale value to integer on change
        self.nr_strength_var.trace_add("write", self._clamp_nr_strength)

        # ── Output Format section ────────────────────────────────────────────
        fmt_frame = ttk.LabelFrame(body, text="Output Format", padding=(10, 6))
        fmt_frame.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(4, 6))

        self.output_fmt_var = tk.StringVar(value="prores")

        ttk.Radiobutton(
            fmt_frame, text="ProRes .mov",
            variable=self.output_fmt_var, value="prores",
            command=self._on_output_fmt_change,
        ).grid(row=0, column=0, sticky="w", padx=(0, 24))

        ttk.Radiobutton(
            fmt_frame, text="Corrected TIFFs folder",
            variable=self.output_fmt_var, value="tiffs",
            command=self._on_output_fmt_change,
        ).grid(row=0, column=1, sticky="w")

        sep3 = ttk.Separator(body, orient="horizontal")
        sep3.grid(row=10, column=0, columnspan=4, sticky="ew", pady=(6, 6))

        # ── Progress + Log ───────────────────────────────────────────────────
        self._section_label(body, "Progress", row=11)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(body, variable=self.progress_var,
                                            maximum=100, length=560)
        self.progress_bar.grid(row=12, column=0, columnspan=4, sticky="ew", pady=(4, 6))

        self.progress_label = tk.Label(body, text="Ready.", bg="#f2f2f7",
                                       font=("SF Pro Text", 10), fg="#555")
        self.progress_label.grid(row=13, column=0, columnspan=4, sticky="w")

        # Log
        self.log_text = tk.Text(body, height=14, width=78, state="disabled",
                                font=("Menlo", 10), bg="#1c1c1e", fg="#d4d4d4",
                                relief="flat", bd=0, padx=8, pady=6)
        self.log_text.grid(row=14, column=0, columnspan=4, sticky="ew", pady=(6, 0))

        scrollbar = ttk.Scrollbar(body, command=self.log_text.yview)
        scrollbar.grid(row=14, column=4, sticky="ns", pady=(6, 0))
        self.log_text.config(yscrollcommand=scrollbar.set)

        sep4 = ttk.Separator(body, orient="horizontal")
        sep4.grid(row=15, column=0, columnspan=4, sticky="ew", pady=(10, 6))

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_frame = tk.Frame(body, bg="#f2f2f7")
        btn_frame.grid(row=16, column=0, columnspan=4, sticky="e")

        self.stop_btn = tk.Button(btn_frame, text="Stop", width=10,
                                  command=self._stop,
                                  font=("SF Pro Text", 12),
                                  bg="#e5e5ea", fg="#1c1c1e",
                                  relief="flat", bd=0, padx=12, pady=6,
                                  state="disabled")
        self.stop_btn.pack(side="right", padx=(8, 0))

        self.run_btn = tk.Button(btn_frame, text="▶  Run",
                                 command=self._start_processing,
                                 font=("SF Pro Text", 12, "bold"),
                                 bg="#007aff", fg="white",
                                 relief="flat", bd=0, padx=16, pady=6,
                                 activebackground="#0051a8", activeforeground="white",
                                 cursor="hand2")
        self.run_btn.pack(side="right")

        # ── Refresh disk space on any folder change ───────────────────────────
        for var in (self.watch_var, self.temp_var, self.output_var):
            var.trace_add("write", lambda *_: self._refresh_disk_space())

        # Set initial enabled/disabled states
        self._on_nr_toggle()
        self._on_output_fmt_change()
        self._refresh_disk_space()

    # ── Widget helpers ───────────────────────────────────────────────────────

    def _section_label(self, parent, text, row):
        tk.Label(parent, text=text.upper(),
                 font=("SF Pro Text", 9, "bold"),
                 bg="#f2f2f7", fg="#888",
                 anchor="w").grid(row=row, column=0, columnspan=4, sticky="w",
                                  pady=(8, 2))

    def _folder_row(self, parent, label, string_var, disk_var, row, tooltip=""):
        tk.Label(parent, text=label, bg="#f2f2f7",
                 font=("SF Pro Text", 11), width=14, anchor="e"
                 ).grid(row=row, column=0, sticky="e", padx=(0, 6), pady=3)

        entry = tk.Entry(parent, textvariable=string_var, width=42,
                         font=("SF Pro Text", 11))
        entry.grid(row=row, column=1, sticky="ew", pady=3)

        browse_btn = tk.Button(
            parent, text="Browse…",
            command=lambda v=string_var: self._browse_folder(v),
            font=("SF Pro Text", 10),
            bg="#e5e5ea", fg="#1c1c1e",
            relief="flat", bd=0, padx=8, pady=3,
            cursor="hand2"
        )
        browse_btn.grid(row=row, column=2, padx=(6, 0), pady=3)

        disk_label = tk.Label(parent, textvariable=disk_var, bg="#f2f2f7",
                              font=("SF Pro Text", 9), fg="#888", width=22, anchor="w")
        disk_label.grid(row=row, column=3, sticky="w", padx=(10, 0))

    def _browse_folder(self, string_var):
        chosen = filedialog.askdirectory(title="Select folder")
        if chosen:
            string_var.set(chosen)

    def _refresh_disk_space(self):
        pairs = [
            (self.watch_var,  self.watch_disk_var),
            (self.temp_var,   self.temp_disk_var),
            (self.output_var, self.output_disk_var),
        ]
        for path_var, disk_var in pairs:
            disk_var.set(disk_free_str(path_var.get()))

    # ── Noise Reduction callbacks ─────────────────────────────────────────────

    def _on_nr_toggle(self):
        """Enable or disable strength controls based on the NR checkbox."""
        enabled = self.nr_enabled_var.get() and _CV2_AVAILABLE
        state = "normal" if enabled else "disabled"
        self.nr_strength_entry.config(state=state)
        self.nr_strength_scale.config(state=state)

    def _clamp_nr_strength(self, *_):
        """Keep the NR strength IntVar within [1, 30] and integer."""
        try:
            v = int(round(float(self.nr_strength_var.get())))
            v = max(NR_STRENGTH_MIN, min(NR_STRENGTH_MAX, v))
            self.nr_strength_var.set(v)
        except (ValueError, tk.TclError):
            self.nr_strength_var.set(NR_STRENGTH_DEFAULT)

    # ── Output format callback ────────────────────────────────────────────────

    def _on_output_fmt_change(self):
        """Grey out fps/ProRes controls when TIFF output is selected."""
        is_prores = (self.output_fmt_var.get() == "prores")
        self.fps_entry.config(state="normal" if is_prores else "disabled")
        self.prores_menu.config(state="readonly" if is_prores else "disabled")

    # ── Logging ──────────────────────────────────────────────────────────────

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _set_progress(self, pct, label=""):
        self.progress_var.set(pct)
        if label:
            self.progress_label.config(text=label)

    # ── Run / Stop ───────────────────────────────────────────────────────────

    def _start_processing(self):
        # Validate folders
        watch  = self.watch_var.get().strip()
        temp   = self.temp_var.get().strip()
        output = self.output_var.get().strip()

        if not watch or not os.path.isdir(watch):
            messagebox.showerror("Missing folder", "Please choose a valid Watch folder.")
            return
        if not temp:
            messagebox.showerror("Missing folder", "Please choose a Temp frames folder.")
            return
        if not output:
            messagebox.showerror("Missing folder", "Please choose an Output folder.")
            return

        # Validate color correction settings
        try:
            gamma = float(self.gamma_var.get())
            clip  = float(self.clip_var.get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Gamma and Clip % must be numbers.")
            return

        # Validate output format + format-specific settings
        output_fmt = self.output_fmt_var.get()
        fps            = FPS_DEFAULT
        prores_profile = PRORES_PROFILES[PRORES_DEFAULT]

        if output_fmt == "prores":
            try:
                fps = float(self.fps_var.get())
            except ValueError:
                messagebox.showerror("Invalid settings", "Frame rate must be a number.")
                return
            prores_profile = PRORES_PROFILES[self.prores_var.get()]

        # Validate noise reduction settings
        nr_enabled  = self.nr_enabled_var.get()
        nr_strength = NR_STRENGTH_DEFAULT

        if nr_enabled:
            if not _CV2_AVAILABLE:
                messagebox.showerror(
                    "Missing dependency",
                    "Noise reduction requires opencv-python.\n\n"
                    "Install it with:\n    pip install opencv-python"
                )
                return
            try:
                nr_strength = int(self.nr_strength_var.get())
                if not (NR_STRENGTH_MIN <= nr_strength <= NR_STRENGTH_MAX):
                    raise ValueError
            except (ValueError, tk.TclError):
                messagebox.showerror(
                    "Invalid setting",
                    f"Noise reduction strength must be {NR_STRENGTH_MIN}–{NR_STRENGTH_MAX}."
                )
                return

        os.makedirs(output, exist_ok=True)

        # Snapshot settings to instance vars (thread reads these)
        self._nr_enabled   = nr_enabled
        self._nr_strength  = nr_strength
        self._output_fmt   = output_fmt

        self._stop_flag.clear()
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        t = threading.Thread(
            target=self._run_pipeline,
            args=(watch, temp, output, fps, gamma, clip, prores_profile),
            daemon=True
        )
        t.start()

    def _stop(self):
        self._stop_flag.set()
        self._log("\n⚠  Stop requested — finishing current frame then halting.")
        self.stop_btn.config(state="disabled")

    def _on_done(self, success=True):
        self.run_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._refresh_disk_space()
        if success:
            self._set_progress(100, "All done!")
        else:
            self._set_progress(0, "Stopped / error — see log above.")

    # ── Pipeline (runs in background thread) ─────────────────────────────────

    def _run_pipeline(self, watch, temp, output, fps, gamma, clip, prores_profile):
        log = self._log

        nr_enabled  = self._nr_enabled
        nr_strength = self._nr_strength
        output_fmt  = self._output_fmt

        log("=" * 54)
        log("  Film Transfer Color Correction")
        log("  Gray World → Gamma → Auto Levels"
            + (" → Noise Reduction" if nr_enabled else "")
            + (" → ProRes .mov" if output_fmt == "prores" else " → TIFF folder"))
        log("=" * 54)
        log(f"  Watch  : {watch}")
        log(f"  Temp   : {temp}")
        log(f"  Output : {output}")
        log(f"  Gamma={gamma}  Clip={clip}%"
            + (f"  FPS={fps}  ProRes={prores_profile}" if output_fmt == "prores" else ""))
        if nr_enabled:
            log(f"  Noise Reduction: ON  (strength={nr_strength})")
        else:
            log(f"  Noise Reduction: OFF")

        # Find jobs
        jobs = []
        for name in sorted(os.listdir(watch)):
            if name.startswith('.') or name.startswith('_'):
                continue
            full_path = os.path.join(watch, name)
            if os.path.isdir(full_path):
                jobs.append((name, full_path))

        if not jobs:
            log("\n  No job subfolders found in watch folder.")
            self.after(0, lambda: self._on_done(False))
            return

        log(f"\n  Found {len(jobs)} job(s):")
        for job_name, _ in jobs:
            log(f"    • {job_name}")

        total_jobs = len(jobs)
        for job_idx, (job_name, job_folder) in enumerate(jobs):
            if self._stop_flag.is_set():
                log("\n  Stopped by user.")
                break

            log(f"\n{'─'*54}")
            log(f"  Job  : {job_name}  ({job_idx+1}/{total_jobs})")
            log(f"  Gamma: {gamma}   Clip: {clip}%")

            frame_files = get_tif_frames(job_folder)
            if not frame_files:
                log(f"  ✗ No .tif frames found — skipping.")
                continue

            log(f"  Frames: {len(frame_files)}"
                + (f" @ {fps}fps" if output_fmt == "prores" else ""))

            corrected_folder = os.path.join(temp, f"_corrected_{job_name}")
            os.makedirs(corrected_folder, exist_ok=True)

            # Step 1: Color analysis
            log(f"\n  Step 1: Gray world color balance")
            r_scale, g_scale, b_scale = gray_world_correction(frame_files, job_folder, log)

            # Step 2 & 3 (+ optional 4): Process frames
            nr_label = " + Noise Reduction" if nr_enabled else ""
            log(f"\n  Step 2 & 3{nr_label}: processing frames...")
            total_frames = len(frame_files)

            for i, fname in enumerate(frame_files):
                if self._stop_flag.is_set():
                    log("\n  Stopped by user mid-job.")
                    self.after(0, lambda: self._on_done(False))
                    return

                input_path  = os.path.join(job_folder, fname)
                output_path = os.path.join(corrected_folder, f"frame_{i+1:05d}.tif")
                process_frame(
                    input_path, output_path,
                    r_scale, g_scale, b_scale,
                    gamma, clip,
                    nr_enabled=nr_enabled,
                    nr_strength=nr_strength,
                )

                # Update progress bar
                overall_pct = (
                    (job_idx / total_jobs) +
                    ((i + 1) / total_frames / total_jobs)
                ) * 100
                frame_label = f"Job {job_idx+1}/{total_jobs}: frame {i+1}/{total_frames}"
                self.after(0, lambda p=overall_pct, l=frame_label: self._set_progress(p, l))

                if (i + 1) % 50 == 0 or (i + 1) == total_frames:
                    log(f"    {i+1}/{total_frames} frames processed")

            # Final step: assemble .mov or move TIFF folder
            if output_fmt == "prores":
                log(f"\n  Assembling ProRes .mov")
                success = assemble_mov(corrected_folder, job_name, fps,
                                       output, prores_profile, log)
                if success:
                    cleanup_temp(corrected_folder, log)
                else:
                    log(f"  ✗ Assembly failed — temp frames left in: {corrected_folder}")
            else:
                log(f"\n  Moving corrected TIFFs to output folder")
                dest = os.path.join(output, f"{job_name}_corrected")
                try:
                    move_tiff_output(corrected_folder, dest, log)
                except FileExistsError as e:
                    log(f"  ✗ {e}")
                    log(f"  ✗ Temp frames left in: {corrected_folder}")
                except Exception as e:
                    log(f"  ✗ Error moving frames: {e}")
                    log(f"  ✗ Temp frames left in: {corrected_folder}")

        log(f"\n{'='*54}")
        log(f"  All done!  {total_jobs} job(s) processed.")
        log(f"  Output: {output}")
        log("=" * 54)

        self.after(0, lambda: self._on_done(True))


# ─── Launch ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
