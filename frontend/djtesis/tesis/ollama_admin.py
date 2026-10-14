"""Vistas Django Admin para descargar/eliminar modelos en Ollama."""
import json
import logging

import requests
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .ollama_api import OLLAMA_BASE_URL, list_models, valid_model_name

logger = logging.getLogger(__name__)
# Este modelo se usa por defecto para generar preguntas en llmgeneration.py.
# No debe eliminarse sin modificar primero la configuración del generador.
PROTECTED_QUESTION_MODEL = 'gemma3:4b'


def require_superuser(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied('Esta acción requiere una cuenta de superusuario.')


def error_response(message, status=400):
    return JsonResponse({'error': message}, status=status)


@require_GET
def panel(request):
    require_superuser(request)
    models, error = [], None
    try:
        models = list_models()
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning('No se pudo consultar Ollama: %s', exc)
        error = 'No se pudo conectar con Ollama. Comprueba que el servicio esté activo.'
    return render(request, 'tesis/ollama_admin.html', {
        'title': 'Modelos de Ollama',
        'models': models,
        'error': error,
        'protected_model': PROTECTED_QUESTION_MODEL,
    })


@require_POST
def pull_model(request):
    require_superuser(request)
    name = (request.POST.get('model') or '').strip()
    if not valid_model_name(name):
        return error_response('Nombre de modelo inválido. Ejemplo: qwen3:4b.')

    # Respuesta NDJSON transmitida al navegador. No deja una petición Django
    # esperando a que termine toda la descarga antes de mostrar progreso.
    def stream_pull():
        try:
            with requests.post(
                f'{OLLAMA_BASE_URL}/api/pull',
                json={'model': name, 'stream': True},
                stream=True,
                timeout=(10, 1800),
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        update = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    # Sólo transmitimos campos conocidos, sin volcar mensajes ajenos.
                    result = {k: update[k] for k in ('status', 'total', 'completed', 'error') if k in update}
                    yield json.dumps(result, ensure_ascii=False) + '\n'
                    if 'error' in update:
                        return
        except requests.RequestException as exc:
            logger.warning('Descarga fallida de modelo %s: %s', name, exc)
            yield json.dumps({'error': 'Falló la descarga o se interrumpió la conexión con Ollama.'}) + '\n'

    response = StreamingHttpResponse(stream_pull(), content_type='application/x-ndjson; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['X-Accel-Buffering'] = 'no'
    return response


@require_POST
def delete_model(request):
    require_superuser(request)
    name = (request.POST.get('model') or '').strip()
    if not valid_model_name(name):
        return error_response('Nombre de modelo inválido.')
    if request.POST.get('confirm') != 'ELIMINAR':
        return error_response('Debes confirmar la eliminación del modelo.')
    if name == PROTECTED_QUESTION_MODEL:
        return error_response('Este modelo está reservado para generar preguntas. Cambia primero el modelo de llmgeneration.py.')
    try:
        # Importante: sólo se permite borrar nombres que realmente existen.
        if name not in {m['name'] for m in list_models()}:
            return error_response('El modelo ya no está instalado.', 404)
        r = requests.delete(f'{OLLAMA_BASE_URL}/api/delete', json={'model': name}, timeout=(5, 60))
        r.raise_for_status()
        return JsonResponse({'ok': True, 'message': f'{name} eliminado correctamente.'})
    except requests.RequestException as exc:
        logger.warning('Error al eliminar modelo %s: %s', name, exc)
        return error_response('No se pudo eliminar el modelo desde Ollama.', 502)
