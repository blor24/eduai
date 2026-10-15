# EduAI — Etapa 1: Gestión documental avanzada

Este parche está diseñado para la versión de EduAI con los kits **Docker, autenticación, administrador Ollama, administración de IA y OpenDocument** previamente instalados. No sustituye el generador de preguntas, los modelos ni la configuración de embeddings.

## Cambios

- **Chat con selección de documentos:** muestra las entradas de `Archivo` del usuario autenticado, permite elegir uno o varios documentos y guarda la selección en la sesión Django. Por defecto selecciona todos los documentos disponibles (hasta 250). Si ninguno está seleccionado, se bloquea el envío de preguntas.
- **Filtro real en ChromaDB:** se usa el `metadata.source` existente para limitar la recuperación a los documentos seleccionados. No cambia dimensionalidad, fragmentos ni esquema de colecciones.
- **Comprobación de identidad:** Django firma un token HMAC temporal para cada selección. Flask valida la firma y el usuario y verifica que los archivos sigan existiendo. El backend no utiliza el campo `username` proporcionado por el navegador para buscar documentos. El token vence a las 12 horas y se actualiza desde la interfaz cada 5 minutos.
- **Estados de indexación:** la página **Archivos** muestra `Indexado (n)`, `Sin indexar` o `No disponible` con respecto al índice ChromaDB activo. La lista se actualiza al abrir la página.
- **Abrir/descargar originales:** el enlace `Abrir` pasa por una vista Django autenticada; para PDF/TXT y Markdown se intenta mostrar en el navegador y para DOCX/ODT/FODT/PPTX se descarga el archivo, dependiendo del navegador.
- **Eliminación coherente:** se verifica propiedad del registro `Archivo` en Django, se elimina del almacenamiento y de todos los índices ChromaDB mediante la lógica versionada ya existente, y sólo después se elimina el registro Django.
- **Protección de endpoints internos:** las rutas Flask `/upload`, `/delete`, `/file` y `/exam` requieren `X-EduAI-Internal-Token`. La vista de guardado de mensajes Django también requiere dicho token. Las vistas Django proporcionan el token; las solicitudes de navegador no lo exponen.
- **Presentación del chat:** se escapan los mensajes dinámicos antes de insertar HTML; las respuestas recibidas se muestran como texto, no se interpretan como HTML.

## Instalación

1. Desde el equipo que ejecuta tu proyecto:

   ```bash
   cd ~/Documents/tesis-v2/eduai
   git status
   git add . && git commit -m 'Respaldo antes de gestión documental avanzada'
   ```

   **Además**, respalda por separado el volumen Django y los volúmenes de archivos originales y ChromaDB. Git no respalda los datos de los contenedores.

2. Descomprime este paquete en la raíz del repositorio, de modo que exista `eduai_documentos_kit/instalar.py`:

   ```bash
   unzip ~/Downloads/eduai_documentos_kit.zip -d .
   python3 eduai_documentos_kit/instalar.py
   git diff
   ```

   El instalador valida los fragmentos esperados y crea copias de los archivos modificados en `.eduai_documents_backup/`, ignorada por Git. Si indica que falta una coincidencia, **no fuerces el parche ni reemplaces archivos completos**: revisa primero la diferencia con tu versión local. No edita el archivo `.env`.

3. Revisa que `AI_INTERNAL_TOKEN` ya esté definido en `.env` y sea la misma cadena de al menos 24 caracteres en los servicios Django, backend y worker (el kit de administración de IA lo configuró previamente). No publiques el valor.

4. Reconstruye Django y Flask; si quieres mantener las imágenes del worker alineadas, reconstrúyelo también:

   ```bash
   docker compose up -d --build frontend backend ai_worker
   docker compose exec frontend python manage.py check
   docker compose ps
   docker compose logs --tail=70 frontend backend
   ```

   **No hay migraciones nuevas.** No ejecutes `docker compose down -v` ni borres los volúmenes existentes.

## Verificar funcionamiento

1. Entra con **Usuario A** y carga dos documentos diferentes (`tema_a.pdf` y `tema_b.odt`), con información que sólo aparezca en uno de ellos.
2. En **Archivos**, confirma que ambos están `Indexado` y prueba `Abrir`. En ODT puede iniciarse una descarga en lugar de una previsualización del navegador.
3. Abre **Chat**, desmarca `tema_b.odt` y pregunta algo exclusivo de ese documento. El RAG **no debe recuperar fragmentos** de `tema_b.odt`; el LLM deberá indicar que no tiene información suficiente.
4. Vuelve a seleccionar ambos documentos y comprueba que el chat pueda consultar el contenido de los dos.
5. Prueba con **Usuario B**: sus documentos no deben aparecer en el selector de Usuario A.
6. Elimina `tema_b.odt` desde **Archivos**. Verifica que desaparece de Django y que no se recupera desde el índice activo. El método de borrado existente también limpia colecciones de versiones anteriores.
7. Comprueba que siguen funcionando la generación de exámenes, exportación ZIP y `/admin/ia/`.

### Tests unitarios ligeros

```bash
python3 -m unittest discover -s eduai_documentos_kit/tests -v
```

Se comprueban la firma, caducidad, aislamiento por directorio, rechazo de `../`, documentos eliminados, y el filtro de ChromaDB para uno o varios archivos. Los tests no requieren instalar los modelos de IA.

## Consideraciones

- En esta etapa la selección afecta al **chat RAG**. La generación y exportación de exámenes continúa trabajando con el documento elegido en su formulario. En la etapa 3 podremos ampliar la selección a bancos de preguntas y combinaciones de materiales.
- El listado de selección y estados se limita a los primeros 250 archivos por usuario para evitar peticiones excesivas. Si el usuario supera ese límite, hay que incorporar paginación.
- `Indexado (n)` es el número de fragmentos detectados en **la versión del índice activa**, no una evaluación de su calidad ni un estado de una cola de procesamiento.
- Los documentos anteriores con caracteres especiales en el nombre se normalizan al mismo estilo de Flask. Si existen registros Django creados antes del cambio de nombres y no coinciden con el archivo físico, revísalos.
- Las rutas internas anteriores que se llamaban con `curl` sin cabecera ahora devolverán HTTP 403. Las vistas Django existentes envían la cabecera automáticamente después del parche.
- Para producción sigue pendiente una revisión integral de autenticación, CORS, HTTPS, colas y capacidades concurrentes. **Este parche no constituye una auditoría de seguridad completa.**
- No se ha ejecutado en tu Docker ni sobre la base real de EduAI. Se han comprobado sintaxis Python/JavaScript, aplicación repetida del instalador y tests unitarios sobre una reconstrucción local de los kits anteriores.
