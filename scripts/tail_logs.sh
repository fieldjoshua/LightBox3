#!/usr/bin/env bash
set -euo pipefail

# Tail the application log on the Pi or locally.
# Usage:
#  - On the Pi:     ./scripts/tail_logs.sh
#  - From your Mac: ssh pi 'cd ~/LightBox3 && ./scripts/tail_logs.sh'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/ledctl/logs"
LOG_FILE="$LOG_DIR/ledctl.log"

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
echo "Tailing $LOG_FILE"
exec tail -F "$LOG_FILE"


