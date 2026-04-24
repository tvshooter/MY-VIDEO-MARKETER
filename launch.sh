#!/usr/bin/env bash
# Launch the Video Trim & Transcode app
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3.12 -m video_trimmer "$@"
