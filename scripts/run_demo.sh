#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/.tmp"
PID_FILE="$PID_DIR/demo-server.pid"
LOG_FILE="$PID_DIR/demo-server.log"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"

mkdir -p "$PID_DIR"

is_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

start_server() {
  if is_running; then
    echo "Demo server already running on http://$HOST:$PORT"
    return 0
  fi

  (
    cd "$ROOT_DIR"
    nohup python3 server.py >"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  )

  sleep 1
  if ! is_running; then
    rm -f "$PID_FILE"
    echo "Failed to start demo server on http://$HOST:$PORT"
    echo "Check log: $LOG_FILE"
    return 1
  fi

  echo "Demo server started on http://$HOST:$PORT"
  echo "PID: $(cat "$PID_FILE")"
  echo "Log: $LOG_FILE"
}

stop_server() {
  if ! is_running; then
    rm -f "$PID_FILE"
    echo "Demo server is not running"
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid"
  rm -f "$PID_FILE"
  echo "Demo server stopped"
}

status_server() {
  if is_running; then
    echo "Demo server is running on http://$HOST:$PORT"
    echo "PID: $(cat "$PID_FILE")"
  else
    echo "Demo server is not running"
  fi
}

case "${1:-}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  status)
    status_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  *)
    echo "Usage: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac
