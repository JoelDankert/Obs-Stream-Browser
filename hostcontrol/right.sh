#!/bin/bash

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
"$BASE_DIR/play_sound.sh" 'random*.mp3'
