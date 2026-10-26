"""Panel Admin y API interna. Nunca se expone la API sin token compartido."""
import os
import re
import secrets
import uuid
import logging
import requests
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from .ai_models import AIConfiguration, AIJob, AITestCase, HF_MODELS
from .ollama_api import (
    list_chat_models, list_embedding_models, valid_model_name, OLLAMA_BASE_URL
)

log = logging.getLogger(__name__)


def _superuser(request):
    if not request.user.is_authenticated or not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied('Se requiere superusuario')


def _internal(request):
    configured = os.environ.get('AI_INTERNAL_TOKEN', '')
    provided = request.headers.get('X-EduAI-Internal-Token', '')
    return bool(configured and provided and secrets.compare_digest(configured, provided))


# Los nombres HF son identificadores de repositorios; solo superusuarios pueden enviarlos.
# La lista HF_MODELS queda como sugerencias, no como lista exclusiva.
HF_REPO_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$')


def _allowed(provider, name):
    if not isinstance(name, str) or not 1 <= len(name) <= 200:
        return False
    if provider == 'hf':
        return bool(HF_REPO_RE.fullmatch(name))
    if provider == 'ollama':
        return valid_model_name(name) and any(
            model['name'] == name for model in list_embedding_models()
        )
    return False


def _ongoing():
    return AIJob.objects.filter(kind='reindex', status__in=('queued', 'running')).exists()


@require_GET
def panel(request):
    _superuser(request)
    try:
        installed = {x['name'] for x in list_chat_models()}
    except requests.RequestException:
        installed = set()
        messages.warning(request, 'No se pudo consultar Ollama.')
    try:
        installed_embeds = [x['name'] for x in list_embedding_models()]
    except requests.RequestException:
        installed_embeds = []
        messages.warning(request, 'No se pudieron consultar los embeddings instalados en Ollama.')
    # Estado del backend (no presupone que el worker tenga idéntico hardware).
    hardware = None
    hardware_error = None
    try:
        backend_url = os.getenv('FLASK_BASE_URL', 'http://backend:8080').rstrip('/')
        token = os.getenv('AI_INTERNAL_TOKEN', '')
        response = requests.get(
            f'{backend_url}/internal/ai/hardware',
            headers={'X-EduAI-Internal-Token': token}, timeout=(2, 5)
        )
        response.raise_for_status()
        hardware = response.json()
    except (requests.RequestException, ValueError):
        hardware_error = 'No fue posible consultar el hardware del backend.'

    ollama_running = []
    ollama_error = None
    try:
        response = requests.get(f'{OLLAMA_BASE_URL}/api/ps', timeout=(2, 5))
        response.raise_for_status()
        for item in response.json().get('models', []):
            total = max(0, int(item.get('size') or 0))
            vram = max(0, int(item.get('size_vram') or 0))
            state = 'CPU'
            if vram > 0:
                state = 'GPU' if total and vram >= total else 'GPU + CPU'
            ollama_running.append({
                'name': str(item.get('name', ''))[:180],
                'state': state,
                'vram_gib': round(vram / (1024 ** 3), 2),
            })
    except (requests.RequestException, ValueError, TypeError, KeyError):
        ollama_error = 'No fue posible consultar los modelos residentes en Ollama.'

    # EDUAI-AUTO-GPU-V1
    return render(request, 'tesis/ai_panel.html', {
        'title': 'Administración de IA',
        'config': AIConfiguration.current(),
        'jobs': AIJob.objects.all()[:25],
        'hf_models': HF_MODELS,
        'ollama_embeds': installed_embeds,
        'ollama_models': sorted(installed),
        'busy': _ongoing(),
        'hardware': hardware,
        'hardware_error': hardware_error,
        'ollama_running': ollama_running,
        'ollama_error': ollama_error,
    })


@require_POST
def set_generator(request):
    _superuser(request)
    model = (request.POST.get('generation_model') or '').strip()
    try:
        installed = {x['name'] for x in list_chat_models()}
    except requests.RequestException:
        messages.error(request, 'Ollama no está disponible.')
        return redirect('ai_panel')
    if not valid_model_name(model) or model not in installed:
        messages.error(request, 'Selecciona un LLM instalado.')
        return redirect('ai_panel')
    try:
        response = requests.post(f'{OLLAMA_BASE_URL}/api/show', json={'model': model}, timeout=(5, 20))
        response.raise_for_status()
        capabilities = response.json().get('capabilities', [])
        if not isinstance(capabilities, list) or 'completion' not in capabilities:
            messages.error(request, 'El modelo elegido no es conversacional.')
            return redirect('ai_panel')
    except requests.RequestException:
        messages.error(request, 'No fue posible verificar la capacidad del modelo.')
        return redirect('ai_panel')
    try:
        num_ctx = int(request.POST.get('num_ctx') or 4096)
        num_predict = int(request.POST.get('num_predict') or 1024)
    except ValueError:
        messages.error(request, 'Parámetros numéricos incorrectos.')
        return redirect('ai_panel')
    if not (512 <= num_ctx <= 32768 and 64 <= num_predict <= 4096):
        messages.error(request, 'Contexto o número de tokens fuera del rango permitido.')
        return redirect('ai_panel')
    cfg = AIConfiguration.current()
    cfg.generation_model, cfg.num_ctx, cfg.num_predict = model, num_ctx, num_predict
    cfg.save(update_fields=('generation_model', 'num_ctx', 'num_predict', 'updated_at'))
    messages.success(request, 'Modelo generador actualizado. Se aplicará en las próximas solicitudes.')
    return redirect('ai_panel')


@require_POST
def queue_job(request):
    _superuser(request)
    kind = (request.POST.get('kind') or '').strip()
    provider = (request.POST.get('provider') or '').strip()
    name = (request.POST.get('model_name') or '').strip()
    if provider == 'hf':
        custom_hf_name = (request.POST.get('hf_custom_model') or '').strip()
        if custom_hf_name:
            name = custom_hf_name
    if kind == 'benchmark':
        current = AIConfiguration.current()
        provider, name = current.embedding_provider, current.embedding_model
    if kind not in ('download', 'delete', 'reindex', 'benchmark'):
        messages.error(request, 'Operación no permitida.')
        return redirect('ai_panel')
    try:
        permitted = _allowed(provider, name)
    except requests.RequestException:
        messages.error(request, 'No se pudo verificar si el embedding está instalado en Ollama.')
        return redirect('ai_panel')
    if not permitted:
        messages.error(request, 'Modelo no válido o no instalado con capacidad de embeddings.')
        return redirect('ai_panel')
    cfg = AIConfiguration.current()
    if kind == 'delete' and provider != 'hf':
        messages.error(request, 'Los modelos de Ollama se administran en el panel de Ollama.')
        return redirect('ai_panel')
    if kind == 'delete' and (cfg.embedding_provider, cfg.embedding_model) == (provider, name):
        messages.error(request, 'No se puede eliminar el embedding activo.')
        return redirect('ai_panel')
    if kind == 'delete' and AIJob.objects.filter(kind='reindex', model_name=name,
                                                   status__in=('queued', 'running')).exists():
        messages.error(request, 'Modelo utilizado por una migración activa.')
        return redirect('ai_panel')
    if kind == 'reindex' and _ongoing():
        messages.error(request, 'Ya existe una reindexación en curso.')
        return redirect('ai_panel')
    AIJob.objects.create(kind=kind, provider=provider, model_name=name,
                         target_version=uuid.uuid4().hex[:12] if kind == 'reindex' else '',
                         submitted_by=request.user)
    messages.success(request, 'Trabajo registrado. El proceso ai-worker lo ejecutará en segundo plano.')
    return redirect('ai_panel')


@csrf_exempt
@require_GET
def internal_config(request):
    if not _internal(request):
        return HttpResponseForbidden()
    c = AIConfiguration.current()
    return JsonResponse({'generation_model': c.generation_model,
                         'embedding_provider': c.embedding_provider,
                         'embedding_model': c.embedding_model,
                         'index_version': c.index_version,
                         'num_ctx': c.num_ctx, 'num_predict': c.num_predict})


@csrf_exempt
@require_POST
def claim_job(request):
    if not _internal(request):
        return HttpResponseForbidden()
    with transaction.atomic():
        job = AIJob.objects.select_for_update().filter(status='queued').order_by('created_at').first()
        if not job:
            return JsonResponse({'job': None})
        job.status, job.started_at = 'running', timezone.now()
        job.save(update_fields=('status', 'started_at'))
    return JsonResponse({'job': {'id': job.id, 'kind': job.kind,
                                'provider': job.provider, 'model_name': job.model_name,
                                'target_version': job.target_version}})


@csrf_exempt
@require_POST
def report_job(request, job_id):
    if not _internal(request):
        return HttpResponseForbidden()
    try:
        payload = __import__('json').loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    status = payload.get('status')
    if status not in ('progress', 'success', 'failed'):
        return JsonResponse({'error': 'Estado inválido'}, status=400)
    with transaction.atomic():
        try:
            job = AIJob.objects.select_for_update().get(pk=job_id, status='running')
        except AIJob.DoesNotExist:
            return JsonResponse({'error': 'Trabajo inexistente o terminado'}, status=409)
        job.progress = str(payload.get('progress') or '')[:250]
        if status != 'progress':
            job.status = status
            job.error = str(payload.get('error') or '')[:4000] if status == 'failed' else ''
            job.finished_at = timezone.now()
            if status == 'success' and job.kind == 'reindex':
                c = AIConfiguration.objects.select_for_update().get(pk=1)
                c.embedding_provider = job.provider
                c.embedding_model = job.model_name
                c.index_version = job.target_version
                c.save(update_fields=('embedding_provider', 'embedding_model', 'index_version', 'updated_at'))
        job.save()
    return JsonResponse({'ok': True})


@csrf_exempt
@require_GET
def internal_testcases(request):
    if not _internal(request):
        return HttpResponseForbidden()
    return JsonResponse({'cases': list(AITestCase.objects.filter(enabled=True).values(
        'username', 'query', 'expected_filename'))})
