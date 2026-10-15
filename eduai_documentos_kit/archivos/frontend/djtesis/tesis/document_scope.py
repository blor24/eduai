"""Firma una lista de archivos obtenida EXCLUSIVAMENTE de la BD Django."""
import base64
import hashlib
import hmac
import json
import os
import time

PURPOSE = b'eduai-document-scope-v1:'


def make_token(username, filenames, *, now=None):
    secret = os.environ.get('AI_INTERNAL_TOKEN', '')
    if len(secret) < 24:
        raise RuntimeError('Configura AI_INTERNAL_TOKEN (mínimo 24 caracteres)')
    data = {'u': username, 'f': list(filenames), 't': int(time.time() if now is None else now)}
    payload = base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode()).decode().rstrip('=')
    mac = hmac.new(secret.encode(), PURPOSE + payload.encode(), hashlib.sha256).digest()
    return payload + '.' + base64.urlsafe_b64encode(mac).decode().rstrip('=')
