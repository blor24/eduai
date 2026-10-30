#!/usr/bin/env python3
"""Parche de producción para EduAI v3: app.eduai.work.gd + GPU + Nginx.

Uso:
    python3 preparar_eduai_produccion.py . --dry-run
    python3 preparar_eduai_produccion.py .

Crea respaldos en .eduai_prod_backup/.
No modifica contraseñas, datos ni volúmenes persistentes.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

MARKER = '# EDUAI-PROD-NGINX-V1'
DOMAIN = 'app.eduai.work.gd'
OLD_ORIGIN = 'https://eduai.work.gd'
NEW_ORIGIN = f'https://{DOMAIN}'


def replace_exact(value, before, after, name):
    if value.count(before) != 1:
        raise RuntimeError(
            f'{name}: no se encontró exactamente una '
            'coincidencia del código esperado'
        )
    return value.replace(before, after, 1)


def read(base, name):
    p = base / name
    if not p.is_file():
        raise RuntimeError(f'Archivo requerido ausente: {p}')
    return p.read_text(encoding='utf-8')


def patch(base):
    if not (base / 'compose.gpu.yaml').exists():
        raise RuntimeError(
            'Aplica primero actualizar_eduai_gpu.py '
            '(falta compose.gpu.yaml).'
        )

    files = {
        'compose.yaml',
        'frontend/djtesis/root/settings.py',
        'frontend/djtesis/root/urls.py',
        'frontend/djtesis/requirements.txt',
        'frontend/djtesis/tesis/document_views.py',
        'frontend/djtesis/tesis/templates/tesis/chat.html',
        'backend/eduai-backend.py',
        '.gitignore',
        '.env.example',
    }

    originals = {name: read(base, name) for name in files}
    changes = {}

    # =====================================================
    # 1. RESTRINGIR LOS PUERTOS DE DJANGO Y FLASK
    # =====================================================

    name = 'compose.yaml'
    val = originals[name]

    if '"8080:8080"' in val:
        val = replace_exact(
            val,
            '"8080:8080"',
            '"127.0.0.1:8080:8080"',
            name
        )
    elif '"127.0.0.1:8080:8080"' not in val:
        raise RuntimeError(
            f'{name}: publicación del puerto Flask desconocida'
        )

    if '"8000:8000"' in val:
        val = replace_exact(
            val,
            '"8000:8000"',
            '"127.0.0.1:8000:8000"',
            name
        )
    elif '"127.0.0.1:8000:8000"' not in val:
        raise RuntimeError(
            f'{name}: publicación del puerto Django desconocida'
        )

    changes[name] = val

    # =====================================================
    # 2. CONFIGURAR DJANGO PARA PRODUCCIÓN
    # =====================================================

    name = 'frontend/djtesis/root/settings.py'
    val = originals[name]

    if MARKER not in val:
        val = replace_exact(
            val,
            "STATIC_URL = 'static/'",
            "STATIC_URL = '/static/'",
            name
        )

        val = replace_exact(
            val,
            "    'django.middleware.security.SecurityMiddleware',\n",
            "    'django.middleware.security.SecurityMiddleware',\n"
            "    'whitenoise.middleware.WhiteNoiseMiddleware',\n",
            name
        )

        val += f'''

{MARKER}

# HTTPS termina en Nginx.
SECURE_PROXY_SSL_HEADER = (
    'HTTP_X_FORWARDED_PROTO',
    'https'
)

CSRF_TRUSTED_ORIGINS = [
    item.strip()
    for item in os.getenv(
        'DJANGO_CSRF_TRUSTED_ORIGINS', ''
    ).split(',')
    if item.strip()
]

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

STATIC_ROOT = BASE_DIR / 'staticfiles'

# La redirección HTTP -> HTTPS se realiza en Nginx.
'''

    changes[name] = val

    # =====================================================
    # 3. INSTALAR GUNICORN Y WHITENOISE
    # =====================================================

    name = 'frontend/djtesis/requirements.txt'
    val = originals[name]

    if 'gunicorn' not in val:
        val += (
            '\n# Servidor WSGI de producción\n'
            'gunicorn>=22,<24\n'
        )

    if 'whitenoise' not in val:
        val += 'whitenoise>=6.7,<7\n'

    changes[name] = val

    # =====================================================
    # 4. ADAPTAR SOCKET.IO A HTTPS
    # =====================================================

    name = 'frontend/djtesis/tesis/templates/tesis/chat.html'
    val = originals[name]

    original = (
        '  const socket = io('
        '`${window.location.protocol}//'
        '${window.location.hostname}:8080`);'
    )

    after = (
        '  const socket = io('
        'window.location.origin, '
        '{path: "/socket.io/"});'
    )

    if original in val:
        val = replace_exact(val, original, after, name)
    elif after not in val:
        raise RuntimeError(
            f'{name}: no localicé la dirección Socket.IO esperada'
        )

    changes[name] = val

    # =====================================================
    # 5. LIMITAR ORÍGENES PERMITIDOS EN FLASK
    # =====================================================

    name = 'backend/eduai-backend.py'
    val = originals[name]

    old = 'socketio = SocketIO(app, cors_allowed_origins="*")'

    new = (
        "socketio = SocketIO(\n"
        "    app,\n"
        "    cors_allowed_origins=[\n"
        "        url.strip() for url in os.getenv(\n"
        "            'EDUAI_SOCKETIO_ALLOWED_ORIGINS',\n"
        "            'http://localhost:8000,"
        "http://127.0.0.1:8000'\n"
        "        ).split(',') if url.strip()\n"
        "    ],\n"
        ")"
    )

    if old in val:
        val = replace_exact(val, old, new, name)
    elif new not in val:
        raise RuntimeError(
            f'{name}: configuración Socket.IO desconocida'
        )

    changes[name] = val

    # =====================================================
    # 6. PROTEGER DESCARGAS PDF, DOCX Y ZIP
    # =====================================================

    name = 'frontend/djtesis/tesis/document_views.py'
    val = originals[name]

    if MARKER not in val:
        val = replace_exact(
            val,
            'from django.http import '
            'JsonResponse, StreamingHttpResponse, Http404\n',
            'from django.http import '
            'JsonResponse, StreamingHttpResponse, '
            'Http404, FileResponse\n'
            'from django.conf import settings\n',
            name
        )

        val += f'''

{MARKER}

@login_required(login_url='index')
@require_GET
def export_download(request, username, basename, filename):
    """Descargas disponibles únicamente para su propietario."""

    if username != request.user.username or filename not in (
        'generated_questions.pdf',
        'generated_questions.docx',
        'generated_questions.zip'
    ):
        raise Http404

    if not any(
        Path(name).stem == basename
        for name in Archivo.objects.filter(
            user=request.user
        ).values_list('nombre', flat=True)
    ):
        raise Http404

    root = (
        Path(settings.MEDIA_ROOT) / 'exports' / username
    ).resolve()

    target = (root / basename / filename).resolve()

    if not target.is_relative_to(root) or not target.is_file():
        raise Http404

    content_type = (
        'application/pdf'
        if filename.endswith('.pdf')
        else (
            'application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document'
            if filename.endswith('.docx')
            else 'application/zip'
        )
    )

    response = FileResponse(
        target.open('rb'),
        content_type=content_type
    )

    disposition = (
        'inline' if filename.endswith('.pdf')
        else 'attachment'
    )

    response['Content-Disposition'] = (
        f'{{disposition}}; filename="{{filename}}"'
    )

    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'

    return response
'''

    changes[name] = val

    # =====================================================
    # 7. REGISTRAR RUTA SEGURA DE DESCARGAS
    # =====================================================

    name = 'frontend/djtesis/root/urls.py'
    val = originals[name]

    new_route = (
        "    path("
        "'media/exports/<str:username>/"
        "<str:basename>/<str:filename>', "
        "document_views.export_download, "
        "name='secure_export'),\n"
    )

    if new_route not in val:
        val = replace_exact(
            val,
            'urlpatterns = [\n',
            'urlpatterns = [\n' + new_route,
            name
        )

    changes[name] = val

    # =====================================================
    # 8. IGNORAR RESPALDOS EN GIT
    # =====================================================

    name = '.gitignore'
    val = originals[name]

    for entry in (
        '.eduai_prod_backup/',
        '.eduai_gpu_backup/'
    ):
        if entry not in val.splitlines():
            val += '\n' + entry + '\n'

    changes[name] = val

    # =====================================================
    # 9. VARIABLES DE ENTORNO DEL NUEVO DOMINIO
    # =====================================================

    name = '.env.example'
    val = originals[name]

    if MARKER not in val:
        val += f'''

{MARKER}

# Producción detrás de Nginx.
DJANGO_CSRF_TRUSTED_ORIGINS={NEW_ORIGIN}
EDUAI_SOCKETIO_ALLOWED_ORIGINS={NEW_ORIGIN}
'''

    changes[name] = val.replace(
        OLD_ORIGIN, NEW_ORIGIN
    )

    # =====================================================
    # 10. GENERAR DOCKER COMPOSE DE PRODUCCIÓN
    # =====================================================

    changes['compose.prod.yaml'] = f'''# Producción EduAI.
# Utilizar junto con compose.yaml y compose.gpu.yaml.

services:
  frontend:
    environment:
      DJANGO_DEBUG: "0"
      DJANGO_CSRF_TRUSTED_ORIGINS: ${{DJANGO_CSRF_TRUSTED_ORIGINS:-{NEW_ORIGIN}}}
    command:
      - sh
      - -c
      - >-
        python manage.py migrate --noinput &&
        python manage.py collectstatic --noinput &&
        exec gunicorn root.wsgi:application
        --bind 0.0.0.0:8000
        --workers 2 --threads 4 --timeout 360
        --access-logfile - --error-logfile -

  backend:
    environment:
      EDUAI_SOCKETIO_ALLOWED_ORIGINS: ${{EDUAI_SOCKETIO_ALLOWED_ORIGINS:-{NEW_ORIGIN}}}
'''

    # Conservar cambios manuales si ya existe el archivo.
    prod_file = base / 'compose.prod.yaml'

    if prod_file.is_file():
        changes['compose.prod.yaml'] = (
            prod_file.read_text(encoding='utf-8')
            .replace(OLD_ORIGIN, NEW_ORIGIN)
        )

    # =====================================================
    # 11. GENERAR CONFIGURACIÓN NGINX
    # =====================================================

    nginx_name = f'deploy/nginx/{DOMAIN}.conf'

    changes[nginx_name] = f'''# EduAI - Nginx
# Dominio: {DOMAIN}
# Certbot agregará la configuración HTTPS.

map $http_upgrade $eduai_connection_upgrade {{
    default upgrade;
    '' close;
}}

server {{
    listen 80;
    server_name {DOMAIN};

    client_max_body_size 50m;

    # Bloquear las rutas internas de Django.
    location ^~ /internal/ {{
        return 404;
    }}

    # Socket.IO hacia Flask.
    location /socket.io/ {{
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $eduai_connection_upgrade;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }}

    # Aplicación Django.
    location / {{
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 360s;
        proxy_send_timeout 360s;
    }}
}}
'''

    nginx_file = base / nginx_name

    if nginx_file.is_file():
        changes[nginx_name] = (
            nginx_file.read_text(encoding='utf-8')
            .replace(OLD_ORIGIN, NEW_ORIGIN)
            .replace(
                'server_name eduai.work.gd;',
                f'server_name {DOMAIN};'
            )
        )

    # Solo devolver archivos cuyo contenido cambie.
    return {
        name: content
        for name, content in changes.items()
        if not (base / name).is_file()
        or (base / name).read_text(
            encoding='utf-8'
        ) != content
    }


# =========================================================
# 12. APLICAR CAMBIOS Y GENERAR RESPALDOS
# =========================================================

def apply(base, changes):
    stamp = datetime.now(timezone.utc).strftime(
        '%Y%m%d_%H%M%S_%f'
    )

    folder = base / '.eduai_prod_backup' / stamp
    backups = []
    created = []

    for name in sorted(changes):
        p = base / name

        if p.is_file():
            copy = folder / 'originals' / name
            copy.parent.mkdir(
                parents=True,
                exist_ok=True
            )
            shutil.copy2(p, copy)
            backups.append(name)
        else:
            created.append(name)

    for name, value in changes.items():
        p = base / name
        p.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        p.write_text(
            value,
            encoding='utf-8'
        )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    (folder / 'manifest.json').write_text(
        json.dumps(
            {
                'backups': backups,
                'created': created
            },
            indent=2
        ),
        encoding='utf-8'
    )

    return folder


# =========================================================
# 13. FUNCIÓN PRINCIPAL
# =========================================================

def main():
    ap = argparse.ArgumentParser(
        description=__doc__
    )

    ap.add_argument(
        'project',
        nargs='?',
        default='.'
    )

    ap.add_argument(
        '--dry-run',
        action='store_true'
    )

    args = ap.parse_args()

    base = Path(
        args.project
    ).expanduser().resolve()

    if not (base / 'compose.yaml').is_file():
        ap.error(
            'Indica la carpeta raíz de EduAI, '
            'donde está compose.yaml'
        )

    try:
        changes = patch(base)

        if not changes:
            print(
                'Configuración de producción '
                'ya aplicada; sin cambios.'
            )
            return 0

        print('Archivos a crear/modificar:')

        for name in sorted(changes):
            print('  ' + name)

        if args.dry_run:
            print(
                'Vista previa: no se modificó ningún archivo.'
            )
            return 0

        backup = apply(base, changes)

        print('Respaldo:', backup)
        print(f'Dominio: {NEW_ORIGIN}')
        print(
            'Configura .env e instala Nginx y Certbot.'
        )

        old_nginx = (
            base / 'deploy/nginx/eduai.work.gd.conf'
        )

        if old_nginx.exists():
            print(
                'AVISO: existe la configuración antigua '
                'eduai.work.gd.conf. Desactívala en Nginx '
                'si estaba instalada.'
            )

        print(
            'Inicia con compose.yaml + '
            'compose.gpu.yaml + compose.prod.yaml'
        )

        return 0

    except (RuntimeError, OSError) as exc:
        print(
            'ERROR:', str(exc),
            file=sys.stderr
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

