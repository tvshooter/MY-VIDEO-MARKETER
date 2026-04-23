#!/usr/bin/env bash
set -e

echo "=== Video Trim & Transcode — Setup ==="

echo "→ Installing system packages (ffmpeg, python3-tk)…"
apt-get install -y python3-tk ffmpeg

echo "→ Installing Python dependencies…"
python3.12 -m pip install customtkinter==5.2.2 --break-system-packages

echo "→ Making launcher executable…"
chmod +x "$(dirname "$0")/launch.sh"

echo "→ Installing desktop launcher…"
DESKTOP_SRC="$(dirname "$0")/video_trimmer.desktop"
DESKTOP_DEST="$HOME/.local/share/applications/video_trimmer.desktop"
mkdir -p "$HOME/.local/share/applications"
cp "$DESKTOP_SRC" "$DESKTOP_DEST"
update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true

echo ""
echo "Done! Launch the app with:"
echo "  ./launch.sh"
echo "  — or double-click 'Video Trim & Transcode' in your app launcher."
