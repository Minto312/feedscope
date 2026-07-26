#!/usr/bin/env bash
# Install (or refresh) the feedscope systemd user units from this repository.
#
# The units are intentionally NOT kept in dotfiles: they embed absolute paths
# for this checkout and for `uv`. This repo is the source of truth — re-run this
# script to recreate them on a fresh machine.
#
#   ./deploy/install.sh              # collect + classify timers, and the viewer
#   ./deploy/install.sh --no-serve   # timers only (no always-on web viewer)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UV_BIN="$(command -v uv || true)"
WITH_SERVE=1
[[ "${1:-}" == "--no-serve" ]] && WITH_SERVE=0

[[ -n "$UV_BIN" ]] || { echo "uv not found on PATH" >&2; exit 1; }
[[ -f "$REPO_DIR/config.yaml" ]] || echo "warning: $REPO_DIR/config.yaml is missing (cp config.example.yaml config.yaml)" >&2

mkdir -p "$UNIT_DIR"

# Rewrite the paths baked into the units so a checkout elsewhere still works.
for unit in "$REPO_DIR"/deploy/feedscope-*.service "$REPO_DIR"/deploy/feedscope-*.timer; do
  name="$(basename "$unit")"
  sed -e "s#/home/karinto/workspace/feedscope#$REPO_DIR#g" \
      -e "s#/home/karinto/.local/bin/uv#$UV_BIN#g" \
      -e "s#Environment=PATH=/home/karinto/.local/bin:#Environment=PATH=$(dirname "$UV_BIN"):#" \
      "$unit" > "$UNIT_DIR/$name"
  echo "installed $name"
done

systemctl --user daemon-reload
systemctl --user enable --now feedscope-collect.timer feedscope-classify.timer
[[ $WITH_SERVE -eq 1 ]] && systemctl --user enable --now feedscope-serve.service

# Without lingering, user units stop at logout.
if ! loginctl show-user "$USER" 2>/dev/null | grep -q 'Linger=yes'; then
  echo "note: run 'loginctl enable-linger $USER' so the timers survive logout" >&2
fi

echo
systemctl --user list-timers 'feedscope-*' --all --no-pager || true
