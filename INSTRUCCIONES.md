# Dockerización de EduAI (entorno de desarrollo)

## Estructura esperada

```text
eduai/
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.docker.txt
│   └── eduai-backend.py
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── djtesis/
│       ├── manage.py
│       └── requirements.txt
├── compose.yaml
├── .env.example
└── configurar_docker.py
```

## Preparación

1. Descomprime el kit **en la raíz `eduai/`** conservando subcarpetas.
2. Ejecuta `python3 configurar_docker.py`. El script adapta únicamente 4 archivos: Flask, vistas Django, settings Django y plantilla de chat.
3. Comprueba con `git diff` que los cambios son los esperados.
4. Copia `cp .env.example .env` y reemplaza `DJANGO_SECRET_KEY` por una clave secreta real. Genera una con `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'`.
5. Si accedes desde otro equipo, añade su IP/dominio a `DJANGO_ALLOWED_HOSTS` (separado por comas).
6. Comprueba `docker compose config`.

## Construir y ejecutar

```bash
docker compose up -d ollama
# Descargar ambos modelos utilizados en el chat (la generación usa gemma3:4b):
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama pull llama3.2
# Construir frontend y backend, e iniciarlos:
docker compose up -d --build
# Comprobar logs:
docker compose logs -f frontend backend
```

Frontend: http://localhost:8000
Backend Flask: http://localhost:8080 (sus rutas principales son POST)

Prueba simple: `curl -i http://localhost:8000/`.

## Notas importantes

- Primera ejecución: backend descarga desde Hugging Face el embedding `sentence-transformers/all-MiniLM-L12-v2`. Puede tardar y ocupar memoria/disco.
- Los modelos de Ollama no vienen dentro del Dockerfile; quedan almacenados en el volumen `ollama_data`.
- Los datos de Django, archivos cargados, ChromaDB y documentos generados persisten en **volúmenes de Docker**. Si tu SQLite local contiene usuarios, este arranque comienza con una base nueva; migrar los datos exige copiarla expresamente al volumen Django.
- Docker Compose usa nombres de servicio internos (`backend`, `frontend`, `ollama`) en vez de `localhost` entre contenedores.
- El navegador se conecta a Socket.IO usando el hostname con el puerto `8080`. Si luego instalas HTTPS/Nginx tendrás que usar proxy WebSocket por la misma origin y adaptar la URL.
- Esta configuración está orientada a **desarrollo**. Django `runserver`, `DEBUG=1`, el endpoint de Socket.IO abierto y los endpoints sin autenticación del backend no son recomendables para producción.
- Las dependencias del backend fueron fijadas según el entorno de los ZIP proporcionados; para producción es necesario revisar vulnerabilidades y probar actualizaciones.
- Este kit usa ruedas PyTorch **CPU** para `linux/amd64`. Para arquitectura ARM/GPU hay que adaptar la instalación.
- Revisa el espacio en disco y RAM disponibles: Ollama y embeddings ocupan varios GB.
- Si hay un error al ejecutar el script de configuración, no continúes con `docker compose up`; revisa las diferencias de tu repositorio.

## Detener

```bash
docker compose down
```

No ejecutes `docker compose down -v` si deseas conservar bases de datos, archivos y modelos.
