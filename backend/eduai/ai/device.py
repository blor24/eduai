"""Detección de hardware para embeddings Hugging Face.

EDUAI_EMBEDDING_DEVICE=auto|cpu|cuda|mps. GPU compatible implica wheel
PyTorch apropiado y dispositivo visible *dentro* del contenedor.
"""
import logging
import os

log = logging.getLogger(__name__)
VALID = ('auto', 'cpu', 'cuda', 'mps')


def _preference():
    preference = os.getenv('EDUAI_EMBEDDING_DEVICE', 'auto').strip().lower() or 'auto'
    if preference not in VALID:
        raise ValueError('EDUAI_EMBEDDING_DEVICE debe ser auto, cpu, cuda o mps')
    return preference


def detect_device():
    """Auto usa CUDA/ROCm, después MPS; CPU si ninguna aceleración es accesible.

Una selección forzada inválida falla explícitamente para evitar falsos
positivos. Esto NO captura errores por VRAM insuficiente durante inferencia.
"""
    import torch
    preference = _preference()
    if preference == 'cpu':
        return 'cpu'
    cuda = bool(torch.cuda.is_available())
    mps_backend = getattr(torch.backends, 'mps', None)
    mps = bool(mps_backend and mps_backend.is_available())
    if preference == 'cuda':
        if not cuda:
            raise RuntimeError('CUDA/ROCm no disponible en este proceso; verifica PyTorch, drivers y Docker')
        return 'cuda'
    if preference == 'mps':
        if not mps:
            raise RuntimeError('MPS no disponible en este proceso')
        return 'mps'
    return 'cuda' if cuda else ('mps' if mps else 'cpu')


def hardware_info():
    """Diagnóstico sin credenciales para el panel administrativo."""
    import torch
    cuda = bool(torch.cuda.is_available())
    mps_backend = getattr(torch.backends, 'mps', None)
    mps = bool(mps_backend and mps_backend.is_available())
    info = {
        'requested_device': os.getenv('EDUAI_EMBEDDING_DEVICE', 'auto').strip().lower() or 'auto',
        'selected_device': None,
        'cuda_available': cuda,
        'mps_available': mps,
        'pytorch_version': torch.__version__,
        'gpu_name': None,
        'gpu_total_memory_gib': None,
        'error': None,
    }
    if cuda:
        try:
            properties = torch.cuda.get_device_properties(0)
            info['gpu_name'] = properties.name
            info['gpu_total_memory_gib'] = round(properties.total_memory / (1024 ** 3), 2)
        except Exception as exc:
            log.warning('No se pudieron consultar las propiedades de GPU: %s', exc)
    try:
        info['selected_device'] = detect_device()
    except (RuntimeError, ValueError) as exc:
        info['error'] = str(exc)
    return info
