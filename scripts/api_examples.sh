#!/usr/bin/env bash
set -euo pipefail

# Simple helper for interacting with the LED controller API.
# Usage examples:
#   ./scripts/api_examples.sh upload ./path/to/image.png
#   ./scripts/api_examples.sh files
#   ./scripts/api_examples.sh start <filename-from-files>
#   ./scripts/api_examples.sh stop
#   ./scripts/api_examples.sh status
#   ./scripts/api_examples.sh preview /tmp/preview.png
#   ./scripts/api_examples.sh brightness 0.5

HOST="${HOST:-localhost:5000}"

say() { printf "[api] %s\n" "$*"; }

cmd_upload() {
  local file_path=${1:-}
  if [[ -z "$file_path" || ! -f "$file_path" ]]; then
    echo "Usage: $0 upload /path/to/file" >&2
    exit 2
  fi
  say "Uploading $file_path to http://$HOST/api/upload"
  curl -sS -F "file=@${file_path}" "http://$HOST/api/upload" | tee /dev/stderr
}

cmd_files() {
  say "Listing files at http://$HOST/api/files"
  curl -sS "http://$HOST/api/files" | tee /dev/stderr
}

cmd_start() {
  local name=${1:-}
  if [[ -z "$name" ]]; then
    echo "Usage: $0 start <filename-from-files>" >&2
    exit 2
  fi
  say "Starting playback of '$name'"
  curl -sS -H 'Content-Type: application/json' \
    -d "{\"file\":\"$name\"}" \
    "http://$HOST/api/playback/start" | tee /dev/stderr
}

cmd_stop() {
  say "Stopping playback"
  curl -sS -X POST "http://$HOST/api/playback/stop" | tee /dev/stderr
}

cmd_status() {
  say "Playback status"
  curl -sS "http://$HOST/api/playback/status" | tee /dev/stderr
}

cmd_preview() {
  local out=${1:-/tmp/preview.png}
  say "Fetching preview to $out"
  if curl -sSf "http://$HOST/api/preview.png" -o "$out"; then
    say "Saved preview: $out"
  else
    say "No preview available (device may not support or no frame yet)"
    exit 1
  fi
}

cmd_brightness() {
  local val=${1:-}
  if [[ -z "$val" ]]; then
    echo "Usage: $0 brightness <0..1>" >&2
    exit 2
  fi
  say "Setting brightness to $val"
  curl -sS -H 'Content-Type: application/json' \
    -d "{\"value01\":$val}" \
    "http://$HOST/api/brightness" | tee /dev/stderr
}

main() {
  local cmd=${1:-}
  shift || true
  case "$cmd" in
    upload) cmd_upload "$@" ;;
    files) cmd_files ;;
    start) cmd_start "$@" ;;
    stop) cmd_stop ;;
    status) cmd_status ;;
    preview) cmd_preview "$@" ;;
    brightness) cmd_brightness "$@" ;;
    * )
      cat >&2 <<'USAGE'
Usage:
  HOST=pi.local:5000 ./scripts/api_examples.sh upload /path/to/image.png
  HOST=pi.local:5000 ./scripts/api_examples.sh files
  HOST=pi.local:5000 ./scripts/api_examples.sh start <filename-from-files>
  HOST=pi.local:5000 ./scripts/api_examples.sh stop
  HOST=pi.local:5000 ./scripts/api_examples.sh status
  HOST=pi.local:5000 ./scripts/api_examples.sh preview /tmp/preview.png
  HOST=pi.local:5000 ./scripts/api_examples.sh brightness 0.5
USAGE
      exit 1
      ;;
  esac
}

main "$@"


