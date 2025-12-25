#!/bin/sh
set -eu

PORT="${PORT:-10000}"
RUN_MODE="${RUN_MODE:-all}"

term() {
  if [ -n "${WEB_PID:-}" ]; then
    kill -TERM "$WEB_PID" 2>/dev/null || true
  fi
  if [ -n "${BOT_PID:-}" ]; then
    kill -TERM "$BOT_PID" 2>/dev/null || true
  fi
}

case "$RUN_MODE" in
  web)
    exec env PORT="$PORT" python3 app.py
    ;;
  bot)
    exec python3 main.py
    ;;
  all)
    env PORT="$PORT" python3 app.py &
    WEB_PID=$!
    python3 main.py &
    BOT_PID=$!

    trap term INT TERM

    while :; do
      if ! kill -0 "$WEB_PID" 2>/dev/null; then
        wait "$WEB_PID"
        status=$?
        term
        wait "$BOT_PID" 2>/dev/null || true
        exit "$status"
      fi

      if ! kill -0 "$BOT_PID" 2>/dev/null; then
        wait "$BOT_PID"
        status=$?
        term
        wait "$WEB_PID" 2>/dev/null || true
        exit "$status"
      fi

      sleep 1
    done
    ;;
  *)
    echo "Unknown RUN_MODE: $RUN_MODE" >&2
    echo "Expected: all|web|bot" >&2
    exit 1
    ;;
esac

