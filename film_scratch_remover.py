#!/usr/bin/env python3
"""
Film Scratch Remover
====================
Detects and removes vertical scratch lines from scanned film footage.

Scratches appear as narrow, dark, vertical columns caused by debris or damage
on the film gate during scanning. This tool:
  1. Detects scratch columns by comparing each column's brightness against
     its local neighbourhood (Z-score of column darkness deviation).
  2. Repairs detected columns with OpenCV inpainting (TELEA or Navier-Stokes).

Supports single images and video files. For professional workflows, process
image sequences by running on each frame individually (or pipe via FFmpeg).

Dependencies:
    pip install opencv-python-headless numpy

Usage:
    python film_scratch_remover.py input.jpg output.jpg
    python film_scratch_remover.py input.mov output.mov
    python film_scratch_remover.py input.mp4 output.mp4 --sensitivity 1.5
    python film_scratch_remover.py input.tif output.tif --debug
"""

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_scratch_mask(frame: np.ndarray,
                        sensitivity: float = 2.0,
                        min_height_ratio: float = 0.3,
                        expand_px: int = 1) -> np.ndarray:
    """
    Return a uint8 mask (255 = scratch) for vertical scratch columns.

    Algorithm
    ---------
    1. Convert to grayscale and compute the mean brightness of every column.
    2. Smooth those column means with a wide Gaussian to estimate the
       "expected" brightness at each horizontal position.
    3. Flag columns whose actual mean is significantly below the expected
       value (Z-score > sensitivity).
    4. Verify each candidate column: at least `min_height_ratio` of its
       pixels must be darker than 85 % of the expected column brightness.
    5. Dilate the mask horizontally by `expand_px` to cover scratch edges.

    Parameters
    ----------
    frame           : BGR image as a numpy array.
    sensitivity     : Z-score threshold; lower → more columns flagged.
                      Typical range: 1.5 (aggressive) – 3.0 (conservative).
    min_height_ratio: Fraction of frame height that must be dark for a
                      column to be accepted as a scratch (0–1).
    expand_px       : How many pixels to dilate the mask left/right.

    Returns
    -------
    mask : np.ndarray, shape (H, W), dtype uint8, values 0 or 255.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape

    # --- Step 1: per-column mean brightness ---
    col_means = gray.mean(axis=0)           # shape (W,)

    # --- Step 2: smoothed (expected) column brightness ---
    # Kernel must be wide enough to span several scratches without being
    # biased by them; ~5 % of frame width, minimum 21 px, forced odd.
    ksize = max(21, w // 20)
    if ksize % 2 == 0:
        ksize += 1
    smoothed = cv2.GaussianBlur(
        col_means.reshape(1, -1).astype(np.float32),
        (ksize, 1), 0
    ).flatten()

    # --- Step 3: Z-score of darkness deviation ---
    deviation = smoothed - col_means        # positive = darker than expected
    std = deviation.std()
    if std < 1e-6:
        return np.zeros((h, w), dtype=np.uint8)

    z_scores = (deviation - deviation.mean()) / std
    candidate_cols = np.where(z_scores > sensitivity)[0]

    # --- Step 4: height verification ---
    mask = np.zeros((h, w), dtype=np.uint8)
    for c in candidate_cols:
        expected_brightness = float(smoothed[c])
        dark_pixels = (gray[:, c] < expected_brightness * 0.85).sum()
        if dark_pixels / h >= min_height_ratio:
            mask[:, c] = 255

    # --- Step 5: dilate to cover edges ---
    if expand_px > 0 and mask.any():
        kernel = np.ones((1, 2 * expand_px + 1), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

    return mask


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def inpaint_scratches(frame: np.ndarray,
                      mask: np.ndarray,
                      method: str = 'telea',
                      radius: int = 3) -> np.ndarray:
    """
    Inpaint scratch regions using OpenCV.

    Parameters
    ----------
    frame  : BGR image.
    mask   : uint8 mask (255 = repair here).
    method : 'telea'  → cv2.INPAINT_TELEA  (fast, generally excellent)
             'ns'     → cv2.INPAINT_NS      (Navier-Stokes, smoother on
                                              low-texture areas)
    radius : Search radius for inpainting in pixels (default 3).

    Returns
    -------
    Repaired BGR image.
    """
    if not mask.any():
        return frame
    flag = cv2.INPAINT_TELEA if method == 'telea' else cv2.INPAINT_NS
    return cv2.inpaint(frame, mask, inpaintRadius=radius, flags=flag)


# ---------------------------------------------------------------------------
# Per-frame processing
# ---------------------------------------------------------------------------

def process_frame(frame: np.ndarray,
                  sensitivity: float,
                  min_height_ratio: float,
                  method: str,
                  radius: int,
                  verbose: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect and remove scratches from one frame.

    Returns (repaired_frame, scratch_mask).
    """
    mask = detect_scratch_mask(frame, sensitivity, min_height_ratio)

    if verbose:
        n_cols = int((mask.max(axis=0) > 0).sum())
        print(f"    scratch columns detected: {n_cols}")

    repaired = inpaint_scratches(frame, mask, method, radius)
    return repaired, mask


# ---------------------------------------------------------------------------
# Image entry point
# ---------------------------------------------------------------------------

def process_image(input_path: str,
                  output_path: str,
                  sensitivity: float,
                  min_height_ratio: float,
                  method: str,
                  radius: int,
                  debug: bool) -> bool:
    frame = cv2.imread(input_path)
    if frame is None:
        print(f"ERROR: cannot read image: {input_path}")
        return False

    print(f"Image  : {input_path}")
    repaired, mask = process_frame(
        frame, sensitivity, min_height_ratio, method, radius, verbose=True
    )

    cv2.imwrite(output_path, repaired)
    print(f"Output : {output_path}")

    if debug:
        stem = Path(output_path).stem
        mask_path = str(Path(output_path).parent / (stem + "_scratch_mask.png"))
        cv2.imwrite(mask_path, mask)
        print(f"Mask   : {mask_path}")

    return True


# ---------------------------------------------------------------------------
# Video entry point
# ---------------------------------------------------------------------------

def process_video(input_path: str,
                  output_path: str,
                  sensitivity: float,
                  min_height_ratio: float,
                  method: str,
                  radius: int,
                  debug: bool) -> bool:
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"ERROR: cannot open video: {input_path}")
        return False

    fps    = cap.get(cv2.CAP_PROP_FPS) or 24.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Video  : {input_path}")
    print(f"Size   : {width}x{height}  FPS: {fps:.3f}  Frames: {total}")

    ext = Path(output_path).suffix.lower()
    fourcc = cv2.VideoWriter_fourcc(*('MJPG' if ext in ('.avi', '.mjpg') else 'mp4v'))
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not out.isOpened():
        print(f"ERROR: cannot create output video: {output_path}")
        cap.release()
        return False

    frame_num = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_num += 1

            verbose = debug and frame_num == 1
            repaired, _ = process_frame(
                frame, sensitivity, min_height_ratio, method, radius, verbose
            )
            out.write(repaired)

            if frame_num % 25 == 0 or frame_num == total:
                pct = frame_num / max(total, 1) * 100
                bar = '#' * int(pct / 2)
                sys.stdout.write(
                    f"\r  [{bar:<50}] {frame_num}/{total} ({pct:.1f}%)"
                )
                sys.stdout.flush()
    finally:
        cap.release()
        out.release()

    print(f"\nOutput : {output_path}")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.dpx', '.exr'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.mxf', '.m4v', '.mjpg'}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='film_scratch_remover',
        description='Remove vertical scratch lines from scanned film footage.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SENSITIVITY GUIDE
  1.5  Aggressive — catches faint scratches, may repair some clean columns.
  2.0  Default    — good balance for typical heavy gate scratches.
  2.5  Moderate   — use when the image has fine vertical texture (fabric, etc.)
  3.0  Conservative — only the most obvious, very dark scratches.

EXAMPLES
  python film_scratch_remover.py damaged.jpg repaired.jpg
  python film_scratch_remover.py scan.tif    clean.tif  --sensitivity 1.5
  python film_scratch_remover.py raw.mov     fixed.mov  --method ns
  python film_scratch_remover.py raw.mp4     fixed.mp4  --sensitivity 2.5 --debug
""")
    p.add_argument('input',  help='Input image or video file path.')
    p.add_argument('output', help='Output image or video file path.')
    p.add_argument(
        '--sensitivity', type=float, default=2.0, metavar='N',
        help='Detection Z-score threshold. Lower = more sensitive. (default: 2.0)'
    )
    p.add_argument(
        '--min-height', type=float, default=0.3, metavar='RATIO',
        help='Minimum fraction of frame height a scratch must span (default: 0.3).'
    )
    p.add_argument(
        '--method', choices=['telea', 'ns'], default='telea',
        help='Inpainting algorithm: telea (default, fast) or ns (Navier-Stokes).'
    )
    p.add_argument(
        '--radius', type=int, default=3, metavar='PX',
        help='Inpainting search radius in pixels (default: 3).'
    )
    p.add_argument(
        '--debug', action='store_true',
        help='Save scratch mask alongside output (image mode only).'
    )
    return p


def main():
    args = build_parser().parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: input file not found: {args.input}")
        sys.exit(1)

    ext = Path(args.input).suffix.lower()

    if ext in IMAGE_EXTS:
        ok = process_image(
            args.input, args.output,
            sensitivity=args.sensitivity,
            min_height_ratio=args.min_height,
            method=args.method,
            radius=args.radius,
            debug=args.debug,
        )
    elif ext in VIDEO_EXTS:
        ok = process_video(
            args.input, args.output,
            sensitivity=args.sensitivity,
            min_height_ratio=args.min_height,
            method=args.method,
            radius=args.radius,
            debug=args.debug,
        )
    else:
        # Unknown extension — try video, then image.
        print(f"Unknown extension '{ext}'; trying as video …")
        ok = process_video(
            args.input, args.output,
            sensitivity=args.sensitivity,
            min_height_ratio=args.min_height,
            method=args.method,
            radius=args.radius,
            debug=args.debug,
        )
        if not ok:
            ok = process_image(
                args.input, args.output,
                sensitivity=args.sensitivity,
                min_height_ratio=args.min_height,
                method=args.method,
                radius=args.radius,
                debug=args.debug,
            )

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
