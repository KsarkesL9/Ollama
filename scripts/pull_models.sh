#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${1:-$ROOT_DIR/config/benchmark.json}"
PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"

mapfile -t MODELS < <("$PYTHON" -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["models"]))' "$CONFIG")
for model in "${MODELS[@]}"; do
  echo "Pulling $model"
  ollama pull "$model"
done

