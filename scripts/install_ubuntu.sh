#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip curl git rsync jq pciutils tmux

if ! command -v ollama >/dev/null 2>&1; then
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl -fsSL https://ollama.com/install.sh -o "$installer"
  if [[ -n "${OLLAMA_VERSION:-}" ]]; then
    OLLAMA_VERSION="$OLLAMA_VERSION" sh "$installer"
  else
    sh "$installer"
  fi
fi

python3 -m venv "$ROOT_DIR/.venv"
"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable --now ollama
fi

echo "Installation complete. Run: scripts/diagnose.sh"
