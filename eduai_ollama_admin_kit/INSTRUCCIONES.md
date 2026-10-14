# EduAI · Administración de modelos Ollama desde Django Admin

Parche incremental para la estructura `eduai/` generada tras aplicar los kits previos de **Docker** y **autenticación/administración**. Cambia únicamente el código y las plantillas; no migra ni borra bases de datos o modelos. **No ejecutar `docker compose down -v`.**

## 1. Requisitos

- El repositorio tiene `compose.yaml`, `frontend/djtesis/...` y `backend/...`.
- Los servicios `frontend`, `backend` y `ollama` funcionan en Docker Compose.
- Puedes iniciar sesión en `/admin/` como **superusuario**.
- El código local conserva la estructura compatible con los ZIP compartidos; si has modificado segmentos del código que deben parchearse, el instalador se detendrá sin aplicar cambios y deberás integrarlos manualmente.

## 2. Instalación

Desde la raíz del repositorio local:

```bash
cd ~/Documents/tesis-v2/eduai
# Realiza un respaldo en Git antes de parchear:
git status
git add .
git commit -m "Backup: antes de administrar modelos Ollama"

# Si el ZIP quedó en Descargas:
unzip ~/Downloads/eduai_ollama_admin_kit.zip -d .
python3 eduai_ollama_admin_kit/instalar.py

git diff
docker compose up -d --build frontend backend
docker compose exec frontend python manage.py check
docker compose ps
```

*Si `git commit` indica que no hay nada que registrar, no es un error. Si tienes cambios que no quieres confirmar todavía, haz una copia aparte.*

No son necesarias nuevas migraciones. No se modifica el contenedor/volumen Ollama ni tus datos persistentes.

## 3. Uso

1. Como superusuario, abre `http://localhost:8000/admin/`.
2. Haz clic en **Administrar modelos de Ollama** (bloque "Inteligencia artificial"). También está disponible directamente en `http://localhost:8000/admin/ollama/`.
3. En **Descargar modelo**, introduce `qwen3:4b` o un nombre válido del catálogo y presiona **Descargar modelo**. La vista mostrará progreso en tiempo real. Mantén abierta la pestaña hasta que termine.
4. Una vez instalado, aparecerá en la tabla con nombre, tamaño y características.
5. Ingresa como usuario normal al chat, selecciona el modelo e intercambia mensajes con Flask. El selector se actualiza al abrir el chat y luego cada 15 segundos para todas las sesiones abiertas (no hace falta recargar ni reconstruir los contenedores tras cada pull).
6. Para eliminar, usa el botón **Eliminar** junto al modelo y confirma. Si un usuario lo estaba utilizando, su siguiente consulta puede fallar y deberá seleccionar otro.

### Modelo protegido

**`gemma3:4b` no puede eliminarse desde el panel** porque `backend/llmgeneration.py` lo requiere actualmente para generar preguntas. Si deseas liberarlo, adapta primero la configuración del generador y la constante `PROTECTED_QUESTION_MODEL` de `frontend/djtesis/tesis/ollama_admin.py`.

### Restricciones y advertencias

- Los modelos descargados consumen espacio en el volumen `ollama_data`, además de memoria RAM/VRAM cuando se usan. Revisa el tamaño antes de descargar.
- El panel lista modelos instalados en Ollama, incluidos los que puedan servir sólo para embeddings. Esos modelos no son necesariamente compatibles con el chat de LangChain; utiliza modelos generativos en el selector del chat.
- La sincronización es **por consulta periódica** (máximo ~15 s), no una notificación push instantánea.
- El progreso de descarga se obtiene mediante transmisión HTTP desde Ollama, sin colas de tareas; si cierras la pestaña, la descarga puede interrumpirse. Ollama puede reanudar descargas parciales.
- Sólo superusuarios pueden añadir o borrar modelos. Usuarios autenticados comunes únicamente pueden consultar la lista y conversar mediante el backend.
- El endpoint de Ollama se usa en red privada Docker: `http://ollama:11434`, nunca desde JavaScript directamente.
- Las operaciones administrativas usan `POST` más token CSRF; el navegador nunca recibe credenciales del servidor Ollama.
- Esta solución conserva Socket.IO tal cual está; el esquema actual de autenticación de Socket.IO y la inserción de HTML dinámico deberían reforzarse antes del despliegue público.

## 4. Verificaciones

```bash
# Lista instalada realmente en Ollama:
docker compose exec ollama ollama list

# Comprobar conectividad desde Django a Ollama:
docker compose exec frontend python manage.py shell -c "from tesis.ollama_api import list_models; print([m['name'] for m in list_models()])"

# Seguir registros:
docker compose logs -f frontend backend ollama
```

No es necesario reiniciar Flask/Django después de descargar o borrar **cada** modelo. Sí hay que reconstruir una vez los servicios al instalar este parche.

## 5. Archivos creados

- `frontend/djtesis/tesis/ollama_api.py`: cliente interno Ollama y validación de nombres.
- `frontend/djtesis/tesis/ollama_admin.py`: vistas protegidas, descarga en streaming y eliminación.
- `frontend/djtesis/tesis/templates/tesis/ollama_admin.html`: panel, estado y progreso.
- `frontend/djtesis/tesis/templates/tesis/admin_index_eduai.html`: acceso desde la página inicial del admin.

## 6. Archivos actualizados

- `frontend/djtesis/root/urls.py`: rutas administrativas y API para chat.
- `frontend/djtesis/tesis/admin.py`: enlace en índice Django Admin.
- `frontend/djtesis/tesis/views.py`: listado en vivo y endpoint autenticado.
- `frontend/djtesis/tesis/templates/tesis/chat.html`: selector dinámico y actualización cada 15 s.
- `backend/llmchat.py`: recibe el nombre de Ollama en lugar de un índice numérico.
- `backend/eduai-backend.py`: verifica el modelo instalado y maneja errores de selección.
- `compose.yaml`: `OLLAMA_BASE_URL=http://ollama:11434` para Django.

El parche se ha probado estáticamente (sintaxis Python y JS, configuración YAML, idempotencia del instalador y consulta simulada a `/api/tags`) sobre una copia de los ZIP anteriores. **No se ha desplegado en tu Docker real.**
