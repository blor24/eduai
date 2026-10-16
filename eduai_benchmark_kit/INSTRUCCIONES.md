# EduAI — Kit 1 de evaluación y optimización

**Objetivo:** crear un *baseline reproducible* sin modificar los datos, las colecciones ChromaDB, los modelos descargados ni la base de datos Django.

## Estado y alcance

Los scripts se prepararon con base en la versión integrada de EduAI con `ai_runtime.py`, `llmgeneration.py`, `vectorstorage.py`, `ai_worker.py`, autenticación y Docker Compose. Las pruebas del kit se validaron de forma estática y mediante cuatro pruebas unitarias. **No se han ejecutado contra tu Docker ni contienen resultados reales de tu equipo.**

### Métricas

| Prueba | Qué hace | Métricas | Limitación |
|---|---|---|---|
| `ollama` | Envía prompts idénticos a los LLM con API nativa de Ollama | P50/P95 de tiempo, duración de carga, tokens/s, fallos | No mide todo el sistema RAG ni la calidad pedagógica |
| `retrieval` | Usa el recuperador real de ChromaDB | Hit@k, MRR@k, P50/P95 | Requiere preguntas y archivos esperados **correctamente etiquetados**; Hit@k por archivo no demuestra que se recuperó el fragmento adecuado |
| `generation` | Usa `QuestionGenerator.generate_all_types()` de EduAI | Duración, cantidad, éxito/error de validación estructural | No determina veracidad, sesgos ni correspondencia real con la dificultad |
| `web` | Realiza GET a `/admin/login/` con carga controlada | P50/P95, errores, código HTTP | No sustituye la prueba de múltiples sesiones de chat o usuarios autenticados |
| `medir_recursos.sh` | Captura RAM host y memoria por contenedor | uso memoria, CPU, estados | Muestra una fotografía instantánea, no máximos ni series de tiempo |

La API de Ollama devuelve duraciones en nanosegundos; el kit las convierte a segundos. Los percentiles son de **tiempo de pared observado** y no se mezclan las peticiones de precalentamiento con las mediciones.

## 1. Instalación del kit

Descomprime `eduai_benchmark_kit.zip` en la **raíz de tu repositorio** EduAI:

```bash
cd ~/Documents/tesis-v2/eduai
unzip ~/Downloads/eduai_benchmark_kit.zip -d .
mkdir -p bench-results
printf '\nbench-results/\n' >> .gitignore
```

No es un instalador: **no cambia el backend ni el frontend**. No reconstruye ni reinicia contenedores.

Comprueba servicios y memoria:

```bash
docker compose ps
bash eduai_benchmark_kit/benchmarks/medir_recursos.sh bench-results/recursos_baseline.txt
```

Recomendación: cierra otras cargas de Ollama durante las pruebas y mantén constantes los recursos asignados a Docker Desktop, el contexto, la cantidad de documentos y los modelos instalados.

**IMPORTANTE:** ejecuta estas pruebas en **tu máquina local de desarrollo**, no contra usuarios reales. Las pruebas `generation` producen carga de inferencia y podrían ralentizar temporalmente el chat.

## 2. Comparar dos LLM en Ollama

Usa los modelos que ya tengas instalados; por ejemplo `gemma3:4b` y `qwen3.5:4b`.

```bash
docker compose run --rm --no-deps \
  -v "$PWD/eduai_benchmark_kit/benchmarks:/benchmarks:ro" \
  -v "$PWD/bench-results:/results" \
  backend python /benchmarks/benchmark_eduai.py ollama \
  --models gemma3:4b,qwen3.5:4b \
  --prompts /benchmarks/prompts.example.json \
  --repetitions 2 --num-ctx 2048 --num-predict 128 \
  --output /results/ollama_baseline.json
```

**Recibirás:** `ollama_baseline.json`, `.csv`, `.md`.

Si deseas comparar la carga en frío, examina las filas `warmup` y `load_s` por separado. El resumen usa solo filas `measure`.

La cantidad de contexto y salida se mantiene igual en ambos modelos. Al revisar calidad, no basta con los tiempos: guarda tu propia evaluación humana de exactitud y claridad, sin publicar documentos privados.

## 3. Evaluar embeddings y recuperación RAG

Edita `eduai_benchmark_kit/benchmarks/recuperacion.example.json` con un **usuario existente**, preguntas basadas en documentos realmente indexados y el nombre del archivo en el que está la respuesta.

Idealmente añade de **10 a 20 consultas**, de diversos documentos, y algunas preguntas que no tengan respuesta en los archivos; estas últimas requieren una evaluación aparte de abstención. Para comparar modelos, usa siempre los mismos casos y datos.

Ejecuta:

```bash
docker compose run --rm --no-deps \
  -v "$PWD/eduai_benchmark_kit/benchmarks:/benchmarks:ro" \
  -v "$PWD/bench-results:/results" \
  backend python /benchmarks/benchmark_eduai.py retrieval \
  --cases /benchmarks/recuperacion.example.json \
  --k 5 --repetitions 3 \
  --output /results/recuperacion_baseline.json
```

Si quieres filtrar por un conjunto concreto de documentos como sucede en el chat, añade al caso `"filenames": ["archivo1.pdf", "archivo2.odt"]`. Evita limitar la prueba a un único documento si intentas medir cuál archivo se recupera: el resultado estaría sesgado.

Para comparar con otro embedding, primero reindexa de forma segura desde `/admin/ia/`, valida la nueva versión y ejecuta **el mismo comando**, pero con otro nombre de salida (por ejemplo `recuperacion_e5.json`). No se produce reindexación desde este kit.

## 4. Medir el generador real de preguntas

Edita `eduai_benchmark_kit/benchmarks/generacion.example.json` con un usuario y un documento indexado, preferiblemente de pruebas. Luego ejecuta:

```bash
docker compose run --rm --no-deps \
  -v "$PWD/eduai_benchmark_kit/benchmarks:/benchmarks:ro" \
  -v "$PWD/bench-results:/results" \
  backend python /benchmarks/benchmark_eduai.py generation \
  --cases /benchmarks/generacion.example.json \
  --models gemma3:4b,qwen3.5:4b \
  --repetitions 1 \
  --output /results/preguntas_baseline.json
```

Esto mide las cuatro modalidades reales, valida estructuras y registra duración y errores; **no guarda el contenido de las preguntas** en los informes. La exactitud pedagógica y la dificultad deben evaluarse manualmente, según la siguiente pauta:

| Criterio | 0 | 1 | 2 |
|---|---|---|---|
| Fidelidad documental | Dato inventado | Parcial | Correcto y respaldado |
| Claridad | Ambigua | Mejorable | Clara y precisa |
| Dificultad | No corresponde | Parcial | Corresponde al nivel solicitado |
| Opciones / distractores | Mal construidos | Aceptables | Plausibles y sin ambigüedad |
| Variedad | Muy repetitivas | Algo repetidas | Cobertura diversa |

Registra puntuaciones por pregunta. La suma máxima es 10; esta rúbrica **es orientativa, no una evaluación pedagógica validada**. Para emparejamiento y respuesta corta adapta el criterio de distractores al tipo de pregunta.

## 5. Prueba HTTP ligera de Django

```bash
docker compose run --rm --no-deps \
  -v "$PWD/eduai_benchmark_kit/benchmarks:/benchmarks:ro" \
  -v "$PWD/bench-results:/results" \
  backend python /benchmarks/benchmark_eduai.py web \
  --url http://frontend:8000/admin/login/ \
  --requests 20 --concurrency 1,2,5 \
  --output /results/django_baseline.json
```

Máximo 10 peticiones concurrentes en el script. El endpoint debe ser **de solo lectura**. Esta prueba no toca inicio de sesión ni contraseñas y no simula Socket.IO; no permite afirmar cuántos usuarios reales soporta EduAI.

## 6. Interpretar resultados

- **LLM:** compara P50/P95, tasa de fallos, carga del modelo y tokens por segundo. Mantén prompts y configuración idénticos.
- **RAG:** compara Hit@5 / MRR@5 con un juego de consultas etiquetadas de varios archivos. Revisa manualmente el texto relevante recuperado; la métrica por archivo es una aproximación.
- **Preguntas:** combina el porcentaje de validación estructural con la rúbrica de calidad y dificultad.
- **Django:** mide P95 y errores sobre el mismo endpoint y con igual concurrencia. Posteriormente habrá pruebas autenticadas y Socket.IO bajo un entorno de pruebas.
- **Recursos:** captura RAM y CPU antes y durante cada experimento; el script suministrado captura solo el estado instantáneo.

Tras comparar baseline y nueva versión, descarta toda optimización que gane velocidad pero reduzca sistemáticamente calidad, seguridad o estabilidad.

## 7. Mejoras candidatas para la segunda etapa (no aplicadas aún)

1. **Flask / RAG:** evitar `GET /api/tags` a Ollama por mensaje o incorporar una caché breve con invalidación; separar métricas de recuperación e inferencia; reemplazar la escritura síncrona de `tiempos.log` por logging seguro; evitar registrar contenido del mensaje y respuesta en consola.
2. **Generación:** evaluar reutilizar instancias `QuestionGenerator` cuando sea seguro; reducir reconstrucciones del cliente vectorial; instrumentar etapas `get_docs`, prompt e inferencia; comparar fragmentación y búsqueda con calidad controlada.
3. **Django:** medir SQL y índices según consultas reales; evaluar `SESSION_SAVE_EVERY_REQUEST=True` porque puede generar escrituras adicionales; mover el servidor de desarrollo a Gunicorn/ASGI en producción y realizar un despliegue de prueba; evaluar PostgreSQL si la concurrencia y el patrón de escritura lo justifican.
4. **Docker:** documentar límites de RAM, contenedores y colas; healthchecks, métricas y capacidad de CPU; pruebas de 1, 2, 5 usuarios antes de ampliar.
5. **Seguridad antes de publicar:** restringir `cors_allowed_origins="*"` en Socket.IO, revisar autenticación de endpoints, proteger secretos, ejecutar `manage.py check --deploy` con valores de producción. No exponer las API internas de Flask directamente al exterior sin autenticación y reglas de red.

## 8. Datos que puedes compartir para análisis

Es suficiente enviar archivos `*.md` / `*.csv` del directorio `bench-results`, **sin incluir documentos privados, contraseñas, `.env` ni tokens**. El kit no escribe contenido de documentos ni respuestas textuales en los reportes; sí incluye nombres de los modelos y los identificadores `id` definidos en los casos.

## 9. Comprobación local del kit

```bash
python3 -m unittest discover -s eduai_benchmark_kit/tests -v
```

No es necesario instalar Python extra para el host salvo para ejecutar este test; las pruebas operativas se realizan dentro de tu backend Docker con las dependencias ya instaladas.
