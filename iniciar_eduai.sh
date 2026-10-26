#!/usr/bin/env bash
# Inicia EduAI en CPU o GPU; no modifica los archivos existentes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! docker compose version >/dev/null 2>&1; then
    echo 'Error: Docker Compose v2 no está instalado o Docker no es accesible.' >&2
    exit 1
fi

mode="${EDUAI_ACCELERATOR:-}"
if [[ -z "$mode" && -f .env ]]; then
    # Leer solo la variable admitida, sin ejecutar/sourcing el archivo .env.
    mode="$(sed -n 's/^EDUAI_ACCELERATOR=//p' .env | tail -n 1 | tr -d '\r\"' || true)"
fi
mode="${mode:-auto}"
case "$mode" in
  auto|cpu|gpu) ;;
  *) echo 'EDUAI_ACCELERATOR debe ser auto, cpu o gpu' >&2; exit 2 ;;
esac

has_host_gpu=false
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    has_host_gpu=true
fi
has_docker_nvidia=false
if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q '"nvidia"'; then
    has_docker_nvidia=true
fi

if [[ "$mode" == auto ]]; then
    if [[ "$has_host_gpu" == true && "$has_docker_nvidia" == true ]]; then
        mode=gpu
    else
        if [[ "$has_host_gpu" == true ]]; then
            echo 'GPU detectada, pero Docker no muestra runtime NVIDIA. Se usará CPU.' >&2
            echo 'Instala/configura NVIDIA Container Toolkit o fuerza GPU con EDUAI_ACCELERATOR=gpu.' >&2
        fi
        mode=cpu
    fi
fi

if [[ "$mode" == gpu ]]; then
    echo 'EduAI: GPU NVIDIA habilitada (Ollama, backend y worker).'
    exec docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
else
    echo 'EduAI: modo CPU (compatible con equipos sin GPU NVIDIA).'
    exec docker compose -f compose.yaml up -d --build
fi
