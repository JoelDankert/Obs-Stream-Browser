#!/bin/bash

BASE_DIR="$(cd "$(dirname "$0")/sounds" && pwd)"
if [ -d "$BASE_DIR/trimmed" ]; then
  SOUND_DIR="$BASE_DIR/trimmed"
else
  SOUND_DIR="$BASE_DIR"
fi

read_volume() {
  local vol="1.0"
  if [ -f "$SOUND_DIR/volume.txt" ]; then
    vol="$(cat "$SOUND_DIR/volume.txt")"
  elif [ -f "$BASE_DIR/volume.txt" ]; then
    vol="$(cat "$BASE_DIR/volume.txt")"
  fi
  echo "$vol"
}

VOLUME="$(read_volume)"

rate_limit() {
  local lock="$BASE_DIR/.play.lock"
  local stamp="$BASE_DIR/.play.ts"
  local limit="0.3"
  if [ -f "$SOUND_DIR/ratelimit.txt" ]; then
    limit="$(cat "$SOUND_DIR/ratelimit.txt")"
  elif [ -f "$BASE_DIR/ratelimit.txt" ]; then
    limit="$(cat "$BASE_DIR/ratelimit.txt")"
  fi
  (
    flock -n 9 || exit 1
    now=$(date +%s.%N)
    last=0
    [ -f "$stamp" ] && read -r last < "$stamp"
    diff=$(echo "$now - $last < $limit" | bc -l)
    if [ "$diff" -eq 1 ] 2>/dev/null || [ "$diff" = "1" ]; then
      exit 1
    fi
    echo "$now" > "$stamp"
  ) 9>"$lock"
}

rate_limit || exit 0

farts=()
while read -r f; do
  farts+=("$f")
done < <(find "$SOUND_DIR" -maxdepth 1 -type f -name 'fart*.mp3' -printf '%f\n' | sort)
[ ${#farts[@]} -eq 0 ] && exit 0
pick=${farts[RANDOM % ${#farts[@]}]}
ffplay -nodisp -loglevel quiet -autoexit -af "volume=$VOLUME" "$SOUND_DIR/$pick" </dev/null >/dev/null 2>&1 &
