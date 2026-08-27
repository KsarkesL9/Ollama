#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT_DIR/results"
REPORT="$ROOT_DIR/results/diagnostics-$(date -u +%Y%m%d-%H%M%S).txt"

{
  echo "timestamp_utc=$(date -u --iso-8601=seconds)"
  echo "hostname=$(hostname)"
  echo "kernel=$(uname -a)"
  echo
  echo "== CPU =="
  lscpu 2>&1 || true
  echo
  echo "== RAM =="
  free -h 2>&1 || true
  echo
  echo "== PCI display devices =="
  lspci 2>&1 | grep -Ei 'vga|3d|display' || true
  echo
  echo "== NVIDIA =="
  nvidia-smi 2>&1 || true
  echo
  echo "== Ollama CLI =="
  ollama --version 2>&1 || true
  ollama list 2>&1 || true
  ollama ps 2>&1 || true
  echo
  echo "== Ollama service =="
  systemctl --no-pager --full status ollama 2>&1 || true
  echo
  echo "== Ollama API =="
  curl -fsS http://127.0.0.1:11434/api/version 2>&1 || true
  echo
} | tee "$REPORT"

echo "Diagnostic report: $REPORT"

