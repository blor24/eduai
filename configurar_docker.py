#!/usr/bin/env python3
"""Adapta URLs y configuración local de EduAI a servicios Docker.
Ejecutar desde la raíz eduai tras descomprimir el kit.
Usa git diff para revisar los cambios antes de hacer commit.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def update(file_name, transformations):
    p = ROOT / file_name
    if not p.is_file():
        raise SystemExit(f"Archivo no encontrado: {p}")
    original = p.read_text(encoding="utf-8")
    content = original
    for pattern, replacement in transformations:
        content, num = re.subn(pattern, replacement, content, flags=re.M)
        if num != 1:
            raise SystemExit(
                f"Patrón inesperado en {file_name}: {pattern!r} ({num} coincidencias). "
                "Revisa el código: quizá ya se editó o cambió respecto de los ZIP."
            )
    if content != original:
        p.write_text(content, encoding="utf-8")
        print(f"Actualizado: {file_name}")


backend = ROOT / "backend/eduai-backend.py"
s = backend.read_text(encoding="utf-8")
if 'DJANGO_BASE_URL = os.environ.get(' not in s:
    update("backend/eduai-backend.py", [
        (r'(?m)^app = Flask\(__name__\)$',
         'app = Flask(__name__)\nDJANGO_BASE_URL = os.environ.get("DJANGO_BASE_URL", "http://127.0.0.1:8000").rstrip("/")'),
        (r'(?m)^([ \t]*)response = requests.post\("http://127\.0\.0\.1:8000/dashboard/chat/save_mensaje/", json=data\)',
         r'\g<1>response = requests.post(f"{DJANGO_BASE_URL}/dashboard/chat/save_mensaje/", json=data)'),
        (r'(?m)^[ \t]*socketio\.run\(app, host="localhost", port=8080, debug=True\)$',
         '    socketio.run(app, host=os.getenv("FLASK_HOST", "127.0.0.1"),\n'
         '                 port=int(os.getenv("FLASK_PORT", "8080")),\n'
         '                 debug=os.getenv("FLASK_DEBUG", "0") == "1")'),
    ])
else:
    print("backend/eduai-backend.py ya parece configurado.")

settings = ROOT / "frontend/djtesis/root/settings.py"
s = settings.read_text(encoding="utf-8")
if 'DJANGO_SECRET_KEY' not in s:
    update("frontend/djtesis/root/settings.py", [
        (r'(?m)^from pathlib import Path$', 'from pathlib import Path\nimport os'),
        (r'(?m)^SECRET_KEY\s*=.*$', 'SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]'),
        (r'(?m)^DEBUG\s*=\s*True$', 'DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"'),
        (r'(?m)^ALLOWED_HOSTS\s*=\s*\[\]$',
         'ALLOWED_HOSTS = [x.strip() for x in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if x.strip()]'),
        (r"(?m)^([ \t]*)'NAME': BASE_DIR / 'db.sqlite3',$",
         r"\g<1>'NAME': os.getenv('DJANGO_DB_PATH', str(BASE_DIR / 'db.sqlite3')),"),
    ])
else:
    print("frontend/djtesis/root/settings.py ya parece configurado.")

views = ROOT / "frontend/djtesis/tesis/views.py"
s = views.read_text(encoding="utf-8")
if 'FLASK_BASE_URL = os.environ.get(' not in s:
    update("frontend/djtesis/tesis/views.py", [
        (r'(?m)^import os$',
         'import os\nFLASK_BASE_URL = os.environ.get("FLASK_BASE_URL", "http://localhost:8080").rstrip("/")'),
        (r"flask_url = 'http://localhost:8080/upload'", 'flask_url = f"{FLASK_BASE_URL}/upload"'),
        (r"flask_url = 'http://localhost:8080/delete'", 'flask_url = f"{FLASK_BASE_URL}/delete"'),
        (r"flask_url = 'http://localhost:8080/exam'", 'flask_url = f"{FLASK_BASE_URL}/exam"'),
        (r"flask_url = 'http://localhost:8080/file'", 'flask_url = f"{FLASK_BASE_URL}/file"'),
    ])
else:
    print("frontend/djtesis/tesis/views.py ya parece configurado.")

chat = ROOT / "frontend/djtesis/tesis/templates/tesis/chat.html"
s = chat.read_text(encoding="utf-8")
if 'window.location.hostname' not in s:
    update("frontend/djtesis/tesis/templates/tesis/chat.html", [
        (r"const socket = io\('http://localhost:8080'\);",
         'const socket = io(`${window.location.protocol}//${window.location.hostname}:8080`);'),
    ])
else:
    print("frontend/djtesis/tesis/templates/tesis/chat.html ya parece configurado.")
print("Listo. Revisa con: git diff")
