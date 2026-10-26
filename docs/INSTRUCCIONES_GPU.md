# Actualización CPU/GPU de EduAI v3

Se mantiene `compose.yaml` y `backend/Dockerfile` para ejecutar en CPU.
Se agregaron `compose.gpu.yaml` y `backend/Dockerfile.gpu` para GPU NVIDIA.

## Inicio automático (recomendado)

```bash
chmod +x iniciar_eduai.sh
./iniciar_eduai.sh
```

`iniciar_eduai.sh` usa GPU si detecta NVIDIA en el host y runtime NVIDIA en
Docker. Si no, usa CPU sin romper la instalación original. Requiere Docker
Compose v2. Para forzar el modo: `EDUAI_ACCELERATOR=gpu ./iniciar_eduai.sh`
(o `EDUAI_ACCELERATOR=cpu ...`).

## Requisitos GPU

- Driver NVIDIA operativo (`nvidia-smi`).
- Docker Engine y NVIDIA Container Toolkit configurado.
- Espacio de disco para la imagen PyTorch CUDA (más grande que la CPU).
- GPU con memoria adecuada a los modelos. El despliegue CUDA utiliza cu121.

Si ejecutas un despliegue ajeno a Compose (como ECS/AWS), también debes asignar
GPU al contenedor backend, al worker y a Ollama en la configuración de ese entorno.
Solo detectar CUDA dentro de Python no asigna una GPU al contenedor.

## Diagnóstico

```bash
docker compose exec backend python -c "from eduai.ai.device import hardware_info; print(hardware_info())"
docker compose exec ai_worker python -c "from eduai.ai.device import hardware_info; print(hardware_info())"
docker compose exec ollama ollama ps
```

Revisa también `/admin/ia/` como superusuario. Si se usó el overlay GPU, usa
`docker compose -f compose.yaml -f compose.gpu.yaml exec ...` para consultar los
servicios y sus contenedores.

`EDUAI_EMBEDDING_DEVICE` admite `auto` (por defecto), `cpu`, `cuda` o `mps`.
Forzar `cuda` sin tener acceso real a la GPU produce un error explicativo.
La memoria insuficiente durante inferencia no se recupera automáticamente.

## Seguridad, compatibilidad y reversión

El script no modifica `.env`, PostgreSQL, archivos, índices Chroma ni modelos.
Los originales editados se guardan en `.eduai_gpu_backup/FECHA/` junto con
`manifest.json`. Para revertir los cambios de archivos, ejecuta:

```bash
python3 actualizar_eduai_gpu.py . --rollback .eduai_gpu_backup/FECHA
```

Detén/reconstruye los contenedores según corresponda después de la reversión.
El script de reversión no modifica volúmenes ni elimina datos.
