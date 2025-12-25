#!/bin/sh
set -eu

RUN_MODE="${RUN_MODE:-all}"
PORT="${PORT:-10000}"

case "$RUN_MODE" in
  bot)
    # Bot-only container exits if main process dies; healthcheck is best-effort.
    exit 0
    ;;
  web|all)
    python3 -c "import os,requests; port=os.getenv('PORT','10000'); r=requests.get(f'http://localhost:{port}/health', timeout=5); r.raise_for_status()"
    ;;
  *)
    echo "Unknown RUN_MODE: $RUN_MODE" >&2
    echo "Expected: all|web|bot" >&2
    exit 1
    ;;
esac
