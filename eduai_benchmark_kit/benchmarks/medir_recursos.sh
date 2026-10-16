#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-./bench-results/recursos.txt}"
mkdir -p "$(dirname "$OUT")"
{
  echo '=== Fecha UTC ==='
  date -u --iso-8601=seconds
  echo '=== RAM host ==='
  free -h
  echo '=== Docker memoria total y contexto ==='
  docker context show
  docker info --format '{{.MemTotal}} bytes RAM disponibles para Docker'
  echo '=== Consumo instantáneo contenedores ==='
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
  echo '=== Estado de servicios ==='
  docker compose ps
  echo '=== Modelos instalados ==='
  docker compose exec -T ollama ollama list
} | tee "$OUT"
