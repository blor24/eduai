"""Operaciones sobre la instancia Ollama compartida entre Django y Flask."""
import os
import re
import requests

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434').rstrip('/')
# Nombres de biblioteca Ollama, incluyendo namespaces y etiquetas (qwen3:4b, hf.co/...).
MODEL_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$')


def valid_model_name(name):
    return isinstance(name, str) and 1 <= len(name) <= 180 and bool(MODEL_NAME_RE.fullmatch(name))


def list_models():
    """Consulta el estado real de Ollama; no mantiene una lista paralela en Django."""
    resp = requests.get(f'{OLLAMA_BASE_URL}/api/tags', timeout=(5, 12))
    resp.raise_for_status()
    models = resp.json().get('models', [])
    return sorted(({
        'name': item['name'],
        'size': int(item.get('size') or 0),
        'parameters': item.get('details', {}).get('parameter_size') or '—',
        'quantization': item.get('details', {}).get('quantization_level') or '—',
    } for item in models if valid_model_name(item.get('name'))), key=lambda x: x['name'].lower())
