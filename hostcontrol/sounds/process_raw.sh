#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RAW_DIR="$BASE_DIR/raw"
OUT_DIR="$BASE_DIR"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found" >&2
  exit 1
fi

shopt -s nullglob
files=("$RAW_DIR"/*.mp3)
if [ ${#files[@]} -eq 0 ]; then
  echo "No .mp3 files in $RAW_DIR" >&2
  exit 0
fi

for in_file in "${files[@]}"; do
  name="$(basename "$in_file")"
  tmp_out="$(mktemp -p /tmp "soundproc.XXXXXX.mp3")"

  ffmpeg -hide_banner -loglevel error -y \
    -i "$in_file" \
    -af "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB:stop_periods=1:stop_silence=0.20:stop_threshold=-45dB,loudnorm=I=-16:TP=-1.5:LRA=11" \
    -ar 48000 -ac 2 -b:a 192k \
    "$tmp_out"

  mv -f "$tmp_out" "$OUT_DIR/$name"
done
