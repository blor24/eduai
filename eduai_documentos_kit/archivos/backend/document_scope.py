"""Validación de tokens de selección emitidos por Django.
No confiar en los nombres de usuario ni en archivos enviados directamente por Socket.IO.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from werkzeug.utils import secure_filename

PURPOSE = b'eduai-document-scope-v1:'
MAX_AGE = 12 * 3600
MAX_FILES = 250


class InvalidDocumentScope(ValueError):
    pass


def _decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def verify(token, *, now=None):
    secret = os.environ.get('AI_INTERNAL_TOKEN', '')
    if len(secret) < 24:
        raise InvalidDocumentScope('No se ha configurado la clave interna.')
    if not isinstance(token, str) or len(token) > 45000 or token.count('.') != 1:
        raise InvalidDocumentScope('Sesión documental inválida. Recarga el chat.')
    encoded, signature = token.split('.', 1)
    digest = hmac.new(secret.encode(), PURPOSE + encoded.encode(), hashlib.sha256).digest()
    wanted = base64.urlsafe_b64encode(digest).decode().rstrip('=')
    if not hmac.compare_digest(wanted, signature):
        raise InvalidDocumentScope('Firma de selección inválida.')
    try:
        data = json.loads(_decode(encoded))
        username = data['u']
        filenames = data['f']
        issued = int(data['t'])
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
        raise InvalidDocumentScope('Datos de selección inválidos.') from exc
    instant = int(now if now is not None else time.time())
    if issued > instant + 60 or instant - issued > MAX_AGE:
        raise InvalidDocumentScope('La selección caducó. Actualiza el chat.')
    if (not isinstance(username, str) or not username or len(username) > 150
            or not isinstance(filenames, list) or len(filenames) > MAX_FILES):
        raise InvalidDocumentScope('Selección documental incorrecta.')
    safe_user = secure_filename(username)
    if not safe_user:
        raise InvalidDocumentScope('Usuario incorrecto.')
    cleaned = []
    for item in filenames:
        if not isinstance(item, str) or item != secure_filename(item) or not item:
            raise InvalidDocumentScope('Nombre de documento incorrecto.')
        if len(item) > 255:
            raise InvalidDocumentScope('Nombre de documento demasiado largo.')
        if item not in cleaned:
            cleaned.append(item)
    # Solo documentos que continúan existiendo en el directorio privado del usuario.
    private_dir = Path('uploads') / safe_user
    existing = [filename for filename in cleaned if (private_dir / filename).is_file()]
    return safe_user, existing
