# EduAI — etapa 2: respuestas con fuentes y fragmentos verificables

## Qué incorpora

- Recupera los documentos de ChromaDB conservando sus metadatos (`source`, y `page` si existe).
- Identifica cada fragmento como `[1]`, `[2]`, etc., e instruye al LLM a usar esos marcadores para sus afirmaciones sustentadas.
- Envía a `chat.html` el texto de la respuesta y una lista estructurada de fuentes (archivo, página si está disponible, extracto del fragmento, marcador citado).
- Muestra enlaces seguros hacia la vista previa de documentos a través de Django: la IA no puede crear URL arbitrarias.
- Persiste las referencias nuevas en `Mensaje.fuentes` (`JSONField`) para mostrarlas al recargar el historial. Mensajes anteriores no tendrán referencias retroactivamente.
- Para PDFs **cargados o reindexados después de esta etapa**, incorpora metadatos de página reales (1-based); usa OCR por página en PDF escaneados.
- No inventa páginas si los vectores antiguos carecen de ese metadato, ni garantiza que una afirmación del modelo quede verificada automáticamente por mencionar un fragmento.

## Antes de instalar

Desde la raíz de `eduai/`, donde están `backend/` y `frontend/`:

```bash
# Haz una copia de seguridad de los datos persistentes (volúmenes de Django,
# archivos originales y ChromaDB) mediante tu procedimiento habitual.
git status
git add .
git commit -m "Backup previo a citas del chat"

unzip ~/Downloads/eduai_fuentes_kit.zip -d .
python3 eduai_fuentes_kit/instalar.py
git diff
```

El instalador valida los puntos de integración antes de escribir, guarda copias en `.eduai_fuentes_backup/`, y es idempotente. **No hace cambios en los volúmenes Docker ni instala dependencias**. Si falla porque encuentra un bloque distinto, **no fuerces el reemplazo**; revisa el `git diff` y adapta el parche a tu versión.

## Migración Django obligatoria

La funcionalidad agrega el campo `fuentes` al modelo `Mensaje`, por lo que **sí requiere migración**. Dado que cada instalación puede tener distintas migraciones previas (por ejemplo `0016_sync_ai_models`), el kit no suministra una migración con un número fijo.

1. Construir las imágenes con el nuevo código:

```bash
docker compose build frontend backend ai_worker
```

2. Generar la migración en **tu carpeta local** (el contenedor no tiene un bind mount permanente para el código fuente):

```bash
docker compose run --rm --no-deps \
  -v "$PWD/frontend/djtesis/tesis/migrations:/app/tesis/migrations" \
  frontend python manage.py makemigrations tesis --name add_chat_sources
```

3. Revisa el archivo generado `frontend/djtesis/tesis/migrations/00XX_add_chat_sources.py`. Debería agregar el campo `fuentes` a `Mensaje`. **Si aparece una eliminación inesperada de columnas o modelos, detente** y revisa las migraciones pendientes.

4. Reconstruir Django para incorporar la nueva migración y reiniciar los servicios:

```bash
docker compose up -d --build frontend backend ai_worker
# ai_worker necesita el extractor nuevo para reindexaciones futuras.
docker compose exec frontend python manage.py migrate
docker compose exec frontend python manage.py check
docker compose exec frontend python manage.py makemigrations --check --dry-run
docker compose ps
```

No ejecutes `docker compose down -v`.

## Pruebas funcionales

1. Abre `http://localhost:8000/dashboard/chat` con un usuario que tenga documentos indexados.
2. Selecciona **solo uno** de dos documentos diferentes.
3. Pregunta algo que esté en el primer documento. La respuesta debería incluir marcadores `[1]`, `[2]` cuando el LLM los genere y, bajo ella, **Fuentes y fragmentos consultados**.
4. Abre el enlace del archivo; Django verifica que el documento pertenece al usuario. Si el PDF tiene metadatos de página, se muestra el número y se añade `#page=N` al enlace.
5. Recarga `chat.html`: las fuentes del mensaje deberían conservarse en el historial.
6. Cambia la selección de documentos y repite la pregunta: las referencias solo deben apuntar a los documentos seleccionados.
7. Prueba otro usuario: no debe recibir referencias ni poder abrir los archivos privados del primer usuario.
8. Envía una pregunta no respondida por los documentos: el asistente debería indicar que no tiene información suficiente; la lista indica **fragmentos recuperados**, no evidencias concluyentes.

### PDF antiguo sin número de página

Esto es normal: los vectores históricos solo tenían el metadato `source`. Para habilitar las páginas en todos los PDFs históricos, realiza **una nueva reindexación versionada** desde `/admin/ia/` con el proveedor/modelo activo. Haz respaldo de ChromaDB y de los documentos antes, verifica el resultado y conserva la versión anterior mientras pruebas. No es necesario reindexar para empezar a mostrar nombres y extractos.

## Diagnóstico

```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend

docker compose exec frontend python manage.py shell -c \
  "from tesis.models import Mensaje; print(Mensaje._meta.get_field('fuentes'))"
```

**Si Django dice `no such column: tesis_mensaje.fuentes`**, falta ejecutar `migrate` con la migración generada. **Si no aparecen fuentes en un mensaje nuevo**, verifica que ChromaDB recupere fragmentos para el documento seleccionado y que el backend envíe el campo `sources` por Socket.IO. Mensajes anteriores a esta actualización seguirán sin fuentes.

## Pruebas incluidas

```bash
python3 -m unittest discover -s eduai_fuentes_kit/tests -v
```

Estas pruebas verifican formato, filtrado por nombre de usuario y selección, numeración, páginas y marcadores inválidos. También se verificaron sintaxis Python/JavaScript y que el instalador funcione dos veces contra una copia integrada del proyecto. **No se han hecho pruebas dentro de tu instancia Docker ni evaluaciones de veracidad factual automática**.

## Vuelta atrás

El instalador deja copias originales en `.eduai_fuentes_backup/`; para código bajo Git, lo más seguro es revertir los archivos del parche mediante tu commit de respaldo. Antes de revertir el modelo o la migración, verifica el estado de la base de datos. No elimines directamente el campo ni borres colecciones de ChromaDB.
