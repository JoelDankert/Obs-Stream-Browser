#!/bin/bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/sounds" && pwd)"
SOUND_DIR="$BASE_DIR"

VOLUME="0.6"

rate_limit() {
  local lock="$BASE_DIR/.play.lock"
  local stamp="$BASE_DIR/.play.ts"
  local limit="0.3"
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

if [ "$#" -eq 0 ]; then
  exit 0
fi

sounds=()
declare -A seen
for pattern in "$@"; do
  while read -r f; do
    if [ -z "${seen[$f]+x}" ]; then
      sounds+=("$f")
      seen["$f"]=1
    fi
  done < <(find "$SOUND_DIR" -maxdepth 1 -type f -name "$pattern" -printf '%f\n' | sort)
done

[ ${#sounds[@]} -eq 0 ] && exit 0
pick=${sounds[RANDOM % ${#sounds[@]}]}

PULSE_SINK="${PULSE_SINK:-obs_mix}"
pw-play --target "$PULSE_SINK" --volume "$VOLUME" "$SOUND_DIR/$pick" </dev/null >/dev/null 2>&1 &
