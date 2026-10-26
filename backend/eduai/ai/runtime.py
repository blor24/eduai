"""Configuración de IA obtenida de Django; no existen modelos activos hardcodeados en Flask."""
import os
import time
import logging
from eduai.ai.device import detect_device

log = logging.getLogger(__name__)
# EDUAI-AUTO-GPU-V1
from functools import lru_cache
import requests
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaEmbeddings

CONFIG_URL = os.environ.get('DJANGO_BASE_URL', 'http://frontend:8000').rstrip('/') + '/internal/ai/config/'
TOKEN = os.environ.get('AI_INTERNAL_TOKEN', '')
_cache = None
_cache_until = 0


def config(force=False):
    global _cache, _cache_until
    now = time.monotonic()
    if not force and _cache is not None and now < _cache_until:
        return _cache.copy()
    if not TOKEN:
        raise RuntimeError('AI_INTERNAL_TOKEN no configurado')
    r = requests.get(CONFIG_URL, headers={'X-EduAI-Internal-Token': TOKEN}, timeout=8)
    r.raise_for_status()
    cfg = r.json()
    required = {'generation_model', 'embedding_provider', 'embedding_model', 'index_version', 'num_ctx', 'num_predict'}
    if not required.issubset(cfg):
        raise RuntimeError('Configuración de IA incompleta')
    _cache, _cache_until = cfg, now + 5
    return cfg.copy()


class E5Embeddings(Embeddings):
    """E5 requiere prefijos distintos para consultas y documentos."""
    def __init__(self, embedding):
        self.embedding = embedding

    def embed_documents(self, texts):
        return self.embedding.embed_documents(['passage: ' + t for t in texts])

    def embed_query(self, text):
        return self.embedding.embed_query('query: ' + text)


@lru_cache(maxsize=2)
def embedding_for(provider, model):
    if provider == 'hf':
        device = detect_device()
        log.info('EduAI Hugging Face: modelo=%s, dispositivo=%s', model, device)
        hf = HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={'device': device},
            encode_kwargs={'normalize_embeddings': model.startswith('intfloat/multilingual-e5-')}
        )
        return E5Embeddings(hf) if model.startswith('intfloat/multilingual-e5-') else hf
    if provider == 'ollama':
        return OllamaEmbeddings(model=model, base_url=os.getenv('OLLAMA_HOST', 'http://ollama:11434'))
    raise ValueError('Proveedor de embeddings desconocido')
