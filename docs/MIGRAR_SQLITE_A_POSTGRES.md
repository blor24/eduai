# EduAI: transición segura SQLite → PostgreSQL (Docker Compose)

Parche preparado sobre `eduai_filtrado_chat_completo.zip` y compatible con los parches posteriores de la interfaz y embeddings. Modifica **únicamente** los archivos de este ZIP; NO contiene migraciones nuevas ni datos de BD. No reemplaces un `compose.yaml` editado manualmente sin revisar `git diff`.

## 0. Reglas de seguridad
- Ejecutar en raíz del proyecto (`compose.yaml`). Guarda copia de `.env` y de `compose.yaml` antes de aplicar el parche.
- **NO** ejecutar `docker compose down -v`: elimina volúmenes, incluida la antigua SQLite y la nueva PostgreSQL.
- No publicar ni compartir `.env` ni `respaldos/`; el JSON exportado contiene usuarios y datos privados.
- Usa **el mismo DJANGO_SECRET_KEY y AI_INTERNAL_TOKEN** que tenías.
- No ejecutar `createsuperuser` si vas a migrar usuarios: el usuario administrador se conserva.
- No intentes `loaddata` dos veces en una misma base poblada. Para repetir, restaura sobre una BD nueva/vacía.

## 1. RESPALDA ANTES de aplicar el parche (Django todavía usa SQLite)
```bash
cd ~/Documents/tesis-v2/eduai
mkdir -p respaldos
chmod 700 respaldos
grep -qxF 'respaldos/' .gitignore || printf '\nrespaldos/\n' >> .gitignore
# Evitar trabajos de IA que escriban en SQLite durante la exportación.
docker compose stop ai_worker backend
# Backup de contenido lógico Django sin tablas generadas automáticamente (contenttypes/permisos).
docker compose exec -T frontend python manage.py dumpdata \
  --all --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission --exclude sessions \
  --indent 2 > respaldos/datos_sqlite.json
python3 -m json.tool respaldos/datos_sqlite.json >/dev/null
# Copia adicional del SQLite: útil si la exportación o restauración se complican.
docker compose cp frontend:/app/data/db.sqlite3 respaldos/db.sqlite3
ls -lh respaldos/datos_sqlite.json respaldos/db.sqlite3
docker compose stop frontend  # Congelar SQLite luego del respaldo
```
NOTA: Para máxima consistencia, realiza esto sin usuarios navegando por EduAI. El contenedor frontend queda activo para exportar, pero nadie debe cambiar datos durante la operación.

## 2. Aplica el parche a la raíz de EduAI
```bash
cp compose.yaml respaldos/compose.yaml.antes
cp frontend/djtesis/root/settings.py respaldos/settings.py.antes
unzip -o /ruta/al/eduai_postgres_parche.zip -d .
```
Edita `.env` (**no lo reemplaces por `.env.example`**):
```dotenv
POSTGRES_DB=eduai
POSTGRES_USER=eduai_user
POSTGRES_PASSWORD=REEMPLAZA_CON_UN_SECRETO_NUEVO_LARGO
```
Generar secreto: `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`

## 3. Inicia PostgreSQL y reconstruye el frontend
```bash
docker compose config --quiet
docker compose up -d postgres
docker compose ps postgres
docker compose up -d --build frontend
# La imagen frontend ejecuta python manage.py migrate --noinput al iniciar.
docker compose logs --tail=100 frontend
```
Si prefieres confirmar migraciones antes de restaurar:
```bash
docker compose exec frontend python manage.py migrate --noinput
```

## 4. Importa los datos existentes
```bash
docker compose cp respaldos/datos_sqlite.json frontend:/tmp/datos_sqlite.json
docker compose exec -T frontend python manage.py loaddata /tmp/datos_sqlite.json
# Verifica Django en PostgreSQL y cuenta usuarios/documentos.
docker compose exec frontend python manage.py shell -c \
  "from django.conf import settings; from django.contrib.auth import get_user_model; from tesis.models import Archivo, Mensaje, Estadistica; print('Motor:', settings.DATABASES['default']['ENGINE']); print('Usuarios:', get_user_model().objects.count()); print('Archivos:', Archivo.objects.count()); print('Mensajes:', Mensaje.objects.count()); print('Estadísticas:', Estadistica.objects.count())"
```
Se recomienda comprobar estas cantidades antes/después. `loaddata` restaura también contraseñas hasheadas y roles de Django; no es necesario reconstruirlos.

## 5. Reactiva los servicios y valida
```bash
docker compose up -d backend ai_worker
docker compose ps
docker compose exec frontend python manage.py check
```
Revisa en EduAI inicio de sesión, `/admin/`, mensajes, biblioteca, banco de preguntas y configuración de IA. Los documentos y vectores se guardan en volúmenes separados: esta migración no los mueve ni los elimina.

## Advertencias
- No se expone PostgreSQL al host (sin `ports`); desde frontend su HOST es `postgres` (DNS del servicio Compose).
- `POSTGRES_PASSWORD` se utiliza SOLO la primera vez que se inicializa el volumen PostgreSQL. Si luego cambias esa variable, la contraseña almacenada en la DB no cambia automáticamente.
- Actualiza `.gitignore` si tu proyecto permite seguimiento de `respaldos/` (recomendado incluirlo).
- Django 5.1.5 es una versión antigua; planifica actualizarla por seguridad después de finalizar la migración.
- Para copias de seguridad futuras: `docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > respaldos/eduai_postgres.sql`
