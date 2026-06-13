#!/usr/bin/env bash
set -Eeuo pipefail

PID_DIR="${PID_DIR:-/tmp/file-translation-manual-airgap-portforwards}"

pass() {
  printf '[PASS] %s\n' "$1"
}

warn() {
  printf '[WARN] %s\n' "$1" >&2
}

if [ ! -d "$PID_DIR" ]; then
  pass "No manual airgap port-forward PID directory found: ${PID_DIR}"
  exit 0
fi

for pid_file in "$PID_DIR"/*.pid; do
  [ -e "$pid_file" ] || continue
  pid="$(cat "$pid_file")"
  name="$(basename "$pid_file" .pid)"
  if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
    pass "Stopped ${name} port-forward pid ${pid}"
  else
    warn "Port-forward ${name} pid ${pid:-unknown} was not running"
  fi
done

rm -rf "$PID_DIR"
pass "Removed ${PID_DIR}"
