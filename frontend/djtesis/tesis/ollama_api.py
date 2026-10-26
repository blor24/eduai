"""Operaciones sobre la instancia Ollama compartida entre Django y Flask."""
import os
import re
import hashlib
import requests
from django.core.cache import cache

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
        'digest': item.get('digest', ''),
        'size': int(item.get('size') or 0),
        'parameters': item.get('details', {}).get('parameter_size') or '—',
        'quantization': item.get('details', {}).get('quantization_level') or '—',
    } for item in models if valid_model_name(item.get('name'))), key=lambda x: x['name'].lower())


# Los modelos de embeddings no deben aparecer como LLM en el chat.
# Ollama publica capacidades reales (completion, embedding, vision, etc.)
# en POST /api/show; el nombre de un modelo no es un clasificador fiable.
def model_capabilities(name):
    if not valid_model_name(name):
        raise ValueError('Nombre de modelo inválido')
    response = requests.post(
        f'{OLLAMA_BASE_URL}/api/show',
        json={'model': name},
        timeout=(5, 12),
    )
    response.raise_for_status()
    capabilities = response.json().get('capabilities', [])
    # Si una versión antigua de Ollama no declara capacidades,
    # se excluye el modelo por seguridad en vez de suponer que conversa.
    return capabilities if isinstance(capabilities, list) else []


def _list_models_with_capability(required_capability):
    """Detecta capacidades reales de Ollama, compartiendo caché con el chat."""
    result = []
    models = list_models()
    checked = 0
    failures = 0
    for model in models:
        name = model['name']
        digest = model.get('digest') or ''
        cache_hash = hashlib.sha256(
            f'{OLLAMA_BASE_URL}\0{name}\0{digest}'.encode('utf-8')
        ).hexdigest()
        key = 'eduai:ollama:capabilities:' + cache_hash
        capabilities = cache.get(key)
        if capabilities is None:
            try:
                capabilities = model_capabilities(name)
            except (requests.RequestException, ValueError, TypeError, KeyError):
                failures += 1
                continue
            cache.set(key, capabilities, timeout=120)
        checked += 1
        if required_capability in capabilities:
            result.append(model)
    if models and not checked and failures:
        raise requests.RequestException('No se pudieron consultar las capacidades de Ollama')
    return result


def list_chat_models():
    """Solo modelos instalados con capacidad completion para chat."""
    return _list_models_with_capability('completion')


def list_embedding_models():
    """Solo modelos instalados que permiten calcular embeddings."""
    return _list_models_with_capability('embedding')
