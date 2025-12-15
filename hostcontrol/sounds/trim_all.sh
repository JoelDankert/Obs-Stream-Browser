#!/bin/bash

set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$SRC_DIR/trimmed"

mkdir -p "$OUT_DIR"

# trim all mp3s (recurses one level into subfolders is not required; flat dir)
shopt -s nullglob
for f in "$SRC_DIR"/*.mp3; do
  name="$(basename "$f")"
  ffmpeg -y -hide_banner -loglevel error \
    -i "$f" \
    -af "silenceremove=start_periods=1:start_threshold=-45dB:start_duration=0.02" \
    "$OUT_DIR/$name"
done

echo "Trimmed files written to $OUT_DIR"
