# EduAI — Procesamiento de formatos abiertos ODT/FODT/Markdown

## Qué incorpora

Permite subir e indexar documentos `.odt` (OpenDocument Text de LibreOffice/OpenOffice), `.fodt` (OpenDocument Text en XML plano) y `.md` (Markdown). `.txt` ya funcionaba y se conserva. Los documentos admiten chat RAG, generación de preguntas y reindexación usando los embeddings activos (Hugging Face u Ollama).

Formatos anteriores preservados: PDF, DOCX, PPTX y TXT.

El nuevo extractor de ODF recupera **texto**: títulos, párrafos, viñetas y contenido textual de tablas. No hace OCR de imágenes incrustadas, no procesa macros ni ejecuta LibreOffice. No añade conversión de documentos ni depende del servidor gráfico.

## Archivos modificados

- `backend/opendocument_text.py` (nuevo): lector seguro con `defusedxml` y límites al XML comprimido.
- `backend/filecontentextractor.py`: registra ODT/FODT y Markdown en `get_text`.
- `backend/eduai-backend.py`: agrega las tres extensiones a `ALLOWED_EXTENSIONS`.
- `backend/vectorstorage.py`: incluye ODT/FODT/Markdown en el recorrido de `reindex_everyone` usado por `ai_worker`.
- `backend/requirements.docker.txt`: declara explícitamente `defusedxml==0.7.1`.
- `frontend/djtesis/tesis/templates/tesis/archivos.html`: añade `accept` y texto de ayuda en el selector de archivos.

**No modifica** `compose.yaml`, `.env`, credenciales, configuración Ollama, índices existentes, modelos de Django ni migraciones. Las nuevas extensiones caben en `Archivo.tipo` (`max_length=5`; `.fodt` tiene 5 caracteres).

## Instalar sobre el EduAI actual

Desde la raíz del repositorio:

```bash
cd ~/Documents/tesis-v2/eduai

git status
git add .
git commit -m "Backup antes de agregar OpenDocument"

# Ajusta la ruta al ZIP descargado:
unzip ~/Downloads/eduai_opendocument_kit.zip -d .
python3 eduai_opendocument_kit/instalar.py

git diff
```

El script mantiene los cambios existentes; si encuentra una estructura distinta de la esperada, **se detiene** para evitar sobrescrituras accidentales. Los archivos editados previamente se respaldan en `.eduai_odf_backup/`. Es conveniente añadir `.eduai_odf_backup/` a `.gitignore` para que no termine en GitHub, o eliminar el respaldo local después de confirmar todo.

Reconstruye los tres servicios de código Python/Django (Ollama no requiere reconstrucción):

```bash
docker compose up -d --build backend ai_worker frontend

docker compose ps
docker compose exec frontend python manage.py check
```

No necesitas `makemigrations`, `migrate` ni cambiar el modelo de embeddings. **No ejecutes `docker compose down -v`**, ya que borraría datos persistentes.

## Probar el flujo completo

1. Ingresa como usuario normal a `http://localhost:8000` y abre la sección **Archivos**.
2. Carga `eduai_opendocument_kit/ejemplos/tema_fotosintesis.odt`.
3. Verifica que aparezca en la lista como tipo `.odt`.
4. Desde `chat.html` pregunta `¿Qué ocurre durante el ciclo de Calvin?` y confirma que se base en el documento.
5. Desde la sección de generación, selecciona el nuevo archivo y genera 2 preguntas de selección múltiple y 2 de respuesta corta.
6. Repite la prueba con `tema_fotosintesis.fodt` y `tema_fotosintesis.md` si quieres confirmar los otros formatos. Nota: los tres contienen el mismo texto, por lo que los resultados de recuperación podrían ser redundantes.
7. Al cambiar el modelo de embeddings desde `/admin/ia/`, la reindexación también debe encontrar los archivos nuevos. Mantén un respaldo de ChromaDB y de los documentos antes de reindexar.

Prueba rápida del extractor desde el contenedor:

```bash
docker compose exec backend python -c "from filecontentextractor import FileContentExtractor; print(FileContentExtractor().get_text('uploads/TU_USUARIO/tema_fotosintesis.odt')[:600])"
```

Reemplaza `TU_USUARIO` por el nombre de la cuenta de prueba y ejecuta la carga desde la interfaz previamente.

Para revisar errores:

```bash
docker compose logs --tail=100 backend frontend ai_worker
```

## Limitaciones y seguridad

- **ODT/FODT con imágenes**: solo se indexa texto nativo; para imágenes escaneadas habría que añadir OCR específico o convertir a PDF de manera controlada.
- **Markdown**: se indexa como texto plano con su sintaxis Markdown visible (`#`, `*`, etc.).
- **Archivos cifrados**: no se admiten documentos protegidos por contraseña.
- **Validaciones**: se revisa la extensión en Flask, el mimetype interno en ODT/FODT y que XML sea razonablemente pequeño. Esto no sustituye límites de carga HTTP ni un escáner de malware al desplegar en producción.
- **Seguridad del backend**: los endpoints de subida actuales necesitan controles adicionales de autenticación antes del despliegue público; este kit no cambia ese comportamiento.
- **Reindexación**: lee los archivos originales del volumen `backend_uploads`. No modifica colecciones antiguas; sigue el esquema versionado vigente.

## Pruebas incluidas

En una instalación Python que disponga de `defusedxml`:

```bash
cd eduai_opendocument_kit
python3 -m unittest discover -s tests -v
```

Las pruebas cubren extracción de texto, tablas y espacios ODF, MIME inválido, archivo dañado, documento vacío, FODT y entidades XML maliciosas. El código también se probó de forma integrada con `FileContentExtractor` en una copia de los fuentes anteriores, pero **no se ha ejecutado en tu Docker ni contra documentos reales tuyos**.
