#!/usr/bin/env bash
set -euo pipefail

mapfile -t MODELS < <(ollama ps | awk 'NR > 1 && NF {print $1}')

if ((${#MODELS[@]} == 0)); then
  echo "No models are loaded."
  exit 0
fi

for model in "${MODELS[@]}"; do
  echo "Unloading $model"
  ollama stop "$model"
done

sleep 2
ollama ps
