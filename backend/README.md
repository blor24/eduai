# EduAI Backend

## Puntos de entrada (NO mover)
- `eduai-backend.py`: Flask/Socket.IO (`compose.yaml` ejecuta este archivo).
- `ai_worker.py`: worker de IA (Compose ejecuta `python ai_worker.py`).
- `Dockerfile`, `requirements.docker.txt`: imagen y dependencias Docker.

## Código
- En modo normal (`--apply`): módulos Python originales quedan en `backend/`.
- En modo avanzado (`--modularize-backend`): código en `eduai/{ai,api,documents,storage}/`;
  los módulos con nombres antiguos permanecen como compatibilidad para imports existentes.
- `tools/evaluate_ai.py`: evaluación; `evaluate_ai.py` sigue funcionando como lanzador.
- `tools/legacy_tests/`: pruebas antiguas, fuera de la imagen Docker.
- `font/DejaVuSans.ttf`: fuente necesaria para generar documentos PDF.

## Validación
Desde el proyecto: `python3 -m compileall -q backend frontend/djtesis`.
Luego `docker compose config --quiet` y `docker compose up -d --build`.

La reorganización no cambia URLs, tablas Django ni modelos de IA.
