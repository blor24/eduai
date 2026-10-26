# EduAI: filtrar modelos de embeddings fuera del chat

## Qué se modificó
- `frontend/djtesis/tesis/ollama_api.py`: nuevo `list_chat_models()` usando `POST /api/show` y la capacidad `completion`; caché de 120 s basada en nombre y digest del modelo, pero siempre se actualiza el inventario de modelos instalados.
- `frontend/djtesis/tesis/views.py`: usa el filtro al mostrar el chat y en `/dashboard/chat/models/`.
- `frontend/djtesis/tesis/ai_control.py`: solo permite modelos con generación en el selector del panel IA; comprueba capacidades también al guardarlos.
- `backend/eduai-backend.py`: verifica en el servidor que el modelo seleccionado esté instalado y tenga la capacidad `completion` antes de responder un mensaje.
- `frontend/djtesis/tesis/test_ollama_chat_models.py`: pruebas con respuestas simuladas de Ollama.

**No** se modificó `ollama_admin.py`: ahí deben mostrarse tanto embeddings como modelos generativos, porque se administran todos desde ese panel.

## Aplicar el parche
Desde la carpeta raíz del proyecto que contiene `backend/`, `frontend/` y `compose.yaml`:

    unzip -o /ruta/eduai_filtro_modelos_chat_parche.zip
    docker compose up -d --build frontend backend

La construcción del backend suele tardar más por dependencias ML. No es necesario recrear los volúmenes de Ollama, ChromaDB o Django.

## Pruebas automáticas

    docker compose exec frontend python manage.py test tesis.test_ollama_chat_models

## Comprobación manual
1. En `/admin/ollama/` comprueba que aparezcan `gemma3:4b` y `embeddinggemma-2:270m` (si están instalados).
2. En `/dashboard/chat`, el selector solo debe mostrar modelos con capacidad `completion`.
3. En `/admin/ia/`, el selector de generador no debe incluir embeddings.
4. Un intento de usar un modelo solo-embedding mediante el evento Socket.IO debe ser rechazado por Flask.

Si una versión muy antigua de Ollama no devuelve el campo `capabilities` de `/api/show`, los modelos sin esa información quedan ocultos del chat por seguridad. Actualiza Ollama o verifica la respuesta de `/api/show` si de pronto la lista del chat queda vacía.
