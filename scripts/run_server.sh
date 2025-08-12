#!/usr/bin/env bash
set -euo pipefail

# Safe launcher for the LED controller.
# - Binds to HOST (default 0.0.0.0) and PORT (default 5000)
# - If PORT is in use, it will only terminate a process that looks like
#   our LightBox3 ledctl/app.py. Set FORCE=1 to override and kill any listener.
# - Set USE_SUDO=1 to run with sudo (required for HUB75 GPIO on Pi).
# - Optionally set LEDCTL_CONFIG to a specific YAML path.
#
# Usage:
#   HOST=0.0.0.0 PORT=5000 USE_SUDO=1 LEDCTL_CONFIG=/path/device.yml \
#     ./scripts/run_server.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDCTL_DIR="$ROOT_DIR/ledctl"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
USE_SUDO="${USE_SUDO:-0}"
FORCE="${FORCE:-0}"

# Optionally append rgbmatrix bindings path for HUB75 if not installed site-wide
if [ -z "${RGBMATRIX_PATH:-}" ] && [ -d "$HOME/rpi-rgb-led-matrix/bindings/python" ]; then
  RGBMATRIX_PATH="$HOME/rpi-rgb-led-matrix/bindings/python"
fi
if [ -n "${RGBMATRIX_PATH:-}" ]; then
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$RGBMATRIX_PATH"
fi

if [ -z "${LEDCTL_CONFIG:-}" ]; then
  if [ -f "$LEDCTL_DIR/config/device.yml" ]; then
    LEDCTL_CONFIG="$LEDCTL_DIR/config/device.yml"
  else
    LEDCTL_CONFIG="$LEDCTL_DIR/config/device.default.yml"
  fi
fi

say() { printf "[run] %s\n" "$*"; }
die() { printf "[run][error] %s\n" "$*" >&2; exit 1; }

find_listen_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN -n -P 2>/dev/null || true
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p { print $NF }' | sed -E 's/.*pid=([0-9]+).*/\1/'
  else
    return 0
  fi
}

cmdline_for_pid() {
  local pid="$1"
  if [ -r "/proc/$pid/cmdline" ]; then
    tr '\0' ' ' <"/proc/$pid/cmdline"
  else
    ps -o command= -p "$pid" 2>/dev/null || true
  fi
}

kill_pid() {
  local pid="$1"; local reason="$2"
  say "Killing PID $pid ($reason)"
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 25); do
    if ! kill -0 "$pid" 2>/dev/null; then return 0; fi
    sleep 0.2
  done
  say "Escalating to KILL for PID $pid"
  kill -KILL "$pid" 2>/dev/null || true
}

# 1) Check for existing listener
EXISTING_PIDS=( $(find_listen_pids "$PORT") ) || true
if [ ${#EXISTING_PIDS[@]} -gt 0 ]; then
  say "Port $PORT is in use by: ${EXISTING_PIDS[*]}"
  for pid in "${EXISTING_PIDS[@]}"; do
    cmdline="$(cmdline_for_pid "$pid")"
    if [[ "$cmdline" == *"LightBox3/ledctl/app.py"* || "$cmdline" == *"ledctl/app.py"* ]]; then
      kill_pid "$pid" "previous ledctl instance"
    else
      if [ "$FORCE" = "1" ]; then
        kill_pid "$pid" "FORCE kill: non-ledctl listener"
      else
        die "Refusing to kill non-ledctl process on port $PORT. Set FORCE=1 to override.\n  PID $pid: $cmdline"
      fi
    fi
  done
fi

# 2) Launch server
cd "$LEDCTL_DIR"
export LEDCTL_CONFIG
export HOST
export PORT

say "Starting server: HOST=$HOST PORT=$PORT LEDCTL_CONFIG=$LEDCTL_CONFIG"
if [ -n "${RGBMATRIX_PATH:-}" ]; then
  say "PYTHONPATH+=${RGBMATRIX_PATH}"
fi
if [ "$USE_SUDO" = "1" ]; then
  exec sudo -E "$PYTHON_BIN" app.py
else
  exec "$PYTHON_BIN" app.py
fi


