# EduAI — Administración centralizada de modelos IA (Django + Flask + Docker)

## 1. Qué incluye

- Django Admin: `http://localhost:8000/admin/ia/`.
- LLM para **preguntas y exámenes** configurable, sin reiniciar Flask.
- Parámetros `num_ctx` y `num_predict` configurables; generación en lotes pequeños con validación del JSON y de cada tipo de pregunta.
- Embeddings Hugging Face u Ollama; selección desde Admin con lista controlada.
- Trabajos en segundo plano para descargar/eliminar caché HF y **reindexar** todos los documentos.
- Índices ChromaDB versionados: se mantiene la colección anterior y se activa una nueva sólo tras una migración exitosa.
- Selección del índice activo en Chat RAG, generador de exámenes y cargas de documentos.
- Casos de evaluación en Admin (archivo esperado por consulta), trabajo `benchmark`, métricas **Hit@5**, **MRR@5** y latencia.
- CLI adicional `python evaluate_ai.py casos.json` con resultados por consulta.
- Token interno para la comunicación Django ↔ backend/worker.

## 2. Requisitos

**Este parche se basa en los ZIP originales y en los tres kits ya instalados:** Docker, recuperación/admin, y modelos Ollama. Si modificaste significativamente `vectorstorage.py`, `llmchat.py`, `llmgeneration.py` o `eduai-backend.py` desde entonces, revisa primero esos cambios: el instalador respalda y reemplaza los tres módulos del backend. Los cambios que hayas realizado en ellos deben integrarse manualmente si son necesarios.

- Los servicios `frontend`, `backend` y `ollama` deben funcionar.
- El administrador de modelos Ollama anterior debe estar instalado.
- Debe conservarse el volumen **`backend_uploads`** con los **archivos originales**: la reindexación depende de ellos.
- Conserva `backend_vectors`, `django_data`, `hf_cache` y `ollama_data`.
- **No ejecutes `docker compose down -v`.**

## 3. Instalación

Desde la raíz de tu repositorio:

```bash
cd ~/Documents/tesis-v2/eduai
git status
git add . && git commit -m 'Respaldo antes de modelos IA configurables'

# Ajusta la ruta a la carpeta donde descargaste el ZIP:
unzip ~/Downloads/eduai_ai_models_kit.zip -d .
python3 eduai_ai_models_kit/instalar.py

git diff
docker compose config
```

El instalador guarda copias de los archivos reemplazados en `.eduai_ai_backup/` (ignorado por Git). **No modifica tu archivo `.env`** ni reemplaza tu configuración actual de memoria de Ollama.

Crea un token interno aleatorio:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Añádelo al `.env` en la raíz del repositorio, usando el valor generado:

```dotenv
AI_INTERNAL_TOKEN=EL_TOKEN_ALEATORIO_GENERADO
```

**No publiques `.env`**. El instalador agrega su exclusión en `.gitignore`.

Reconstruye e inicia:

```bash
docker compose up -d --build frontend backend ai_worker
# Una vez inicializada la base de datos:
docker compose exec frontend python manage.py migrate
docker compose exec frontend python manage.py check
docker compose ps
docker compose logs --tail=80 ai_worker frontend backend
```

> El frontend del kit de Docker ejecuta `manage.py migrate` automáticamente antes de `runserver`. Se incluye el comando manual para comprobar el estado. El worker reintentará conectarse mientras Django arranca.

## 4. Configurar el modelo de preguntas

1. Abre `http://localhost:8000/admin/ia/` como superusuario.
2. En **Generador de preguntas y exámenes**, elige un LLM ya instalado en Ollama, por ejemplo `qwen3.5:4b`.
3. Ajusta contexto y salida máxima; para pruebas locales comienza con `4096` y `1024` tokens.
4. Guarda. Las próximas solicitudes a `/exam` y `/file` usan ese modelo.
5. Genera los cuatro tipos de preguntas desde EduAI. Se verifica la cantidad, estructura y respuesta para las preguntas de opción múltiple.

**Atención:** ahora la generación está limitada a **1–40** preguntas por tipo y un lote máximo de 4 preguntas por llamada. Las respuestas que no cumplen el esquema se reintentan una vez; si siguen siendo inválidas, la petición devuelve un error en lugar de guardar preguntas defectuosas. Esto mejora la confiabilidad, pero puede consumir más tiempo que el generador anterior. Las preguntas se reparten entre secciones del documento y no se concatena todo el texto en un solo prompt.

## 5. Instalar y activar embeddings

Los candidatos admitidos inicialmente son:

- Hugging Face: `sentence-transformers/all-MiniLM-L12-v2`, `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, `intfloat/multilingual-e5-small`, `intfloat/multilingual-e5-base`.
- Ollama: `embeddinggemma`, `qwen3-embedding:0.6b`.

**Opción Hugging Face:** elige `Descargar Hugging Face`, proveedor `Hugging Face` y el modelo. Espera a ver el trabajo como **Completado**; después elige `Reindexar y activar modelo`.

**Opción Ollama:** primero descarga el modelo desde `Admin > Ollama`, luego elige `Reindexar y activar modelo`, proveedor `Ollama` y el modelo correspondiente.

La primera indexación sigue usando la colección original `user_<username>_collection` (`index_version=legacy`). Durante la migración, el worker construye colecciones nuevas como `ed_<hash-usuario>_<version>`. **Sólo después de validar todas las colecciones cambia la configuración activa global**. El proceso puede bloquear temporalmente cargas/eliminaciones mientras reindexa, para mantener consistencia. Los chats conservan el índice anterior hasta observar el cambio activo.

Si la migración falla, el modelo y los índices activos se mantienen. El trabajo registra el error. Los índices anteriores no se eliminan automáticamente. Para volver al modelo previo, selecciónalo y crea otra reindexación; así se incluyen también los documentos añadidos desde el último cambio.

**Recomendación de memoria:** como Docker Desktop tenía un límite de ~2 GB antes de ajustarlo, mientras reindexas evita mantener cargados LLM grandes y vigila `docker stats`. El worker comparte el volumen de HF y Chroma con Flask.

## 6. Evaluar embeddings

1. Abre `http://localhost:8000/admin/tesis/aitestcase/`.
2. Añade casos con el **nombre de usuario real**, pregunta y **nombre de archivo fuente esperado**.
3. En `/admin/ia/`, pulsa **Evaluar índice activo**.
4. Actualiza la página hasta que el trabajo termine. En la columna Progreso aparecerán **Hit@5, MRR@5 y latencia**.
5. Repite los mismos casos antes y después de una reindexación para comparar resultados.

También puedes usar la CLI `backend/evaluate_ai.py` y `backend/benchmark_cases.example.json` (requiere que el ejemplo se sustituya por datos reales):

```bash
docker compose exec backend python evaluate_ai.py benchmark_cases.example.json
```

Las métricas de recuperación *no son una evaluación automática de corrección pedagógica*. Esa calidad debe revisarse con docentes o una rúbrica para cada tipo de pregunta. El generador sí comprueba automáticamente la estructura, los tipos y las cantidades.

## 7. Solucionar problemas

```bash
docker compose logs --tail=150 ai_worker
docker compose logs --tail=150 backend
docker compose exec frontend python manage.py check
docker compose exec frontend python manage.py showmigrations tesis
docker stats --no-stream
```

- `403` en API interna: comprueba que **el mismo** `AI_INTERNAL_TOKEN` esté en frontend, backend y ai_worker mediante `docker compose config` (no compartas el valor).
- Error de Hugging Face: verifica red, espacio y RAM; algunos repositorios necesitan licencias/autorizaciones no contempladas por esta lista.
- Trabajos atascados en `Ejecutándose`: revisa logs de ai_worker. La versión del worker incluida no implementa recuperación automática después de cierres bruscos; no reinicies la operación sobre una colección parcial sin inspeccionarla.
- Error de compatibilidad con código modificado: restaura desde `.eduai_ai_backup/` o revierte el commit y adapta manualmente el parche.
- Eliminar caché de HF: no elimina índices, pero puede obligarte a descargar el modelo si vuelves a seleccionarlo.

## 8. Verificación incluida y limitaciones

Pruebas incluidas:

```bash
python3 -m unittest discover -s eduai_ai_models_kit/tests -v
```

Se verificaron: sintaxis Python de los módulos modificados, lectura de `compose.yaml`, reejecución del instalador, nombres de colecciones y validación de tipos de preguntas. **No se ejecutó una prueba real de integración Django/Flask/Chroma/Ollama en tu computadora ni se midieron mejoras de rendimiento**. Antes de utilizarlo en producción, añade pruebas integradas, controles de autenticación de Flask/Socket.IO y un sistema de colas de trabajos con recuperación de fallos. 
