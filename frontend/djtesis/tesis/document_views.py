"""Selección, estado y descarga de documentos: siempre por request.user."""
import mimetypes
import os
from pathlib import Path
import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods
import re
import unicodedata
from .models import Archivo
from .document_scope import make_token

BASE = os.environ.get('FLASK_BASE_URL', 'http://backend:8080').rstrip('/')
HEADERS = {'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')}
MAX_FILES = 250


def _files(request):
    return list(Archivo.objects.filter(user=request.user).order_by('-fecha_carga', '-id')[:MAX_FILES])


def _filename(name):
    # El upload de Flask guarda el nombre mediante secure_filename.
    name = unicodedata.normalize('NFKD', Path(name).name).encode('ascii', 'ignore').decode('ascii')
    name = '_'.join(name.split())
    return re.sub(r'[^A-Za-z0-9_.-]', '', name).strip('._')


@login_required(login_url='index')
@require_http_methods(['GET', 'POST'])
def chat_documents(request):
    files = _files(request)
    known = {obj.pk for obj in files}
    if request.method == 'POST':
        try:
            import json
            body = json.loads(request.body)
            ids = body['ids']
            if not isinstance(ids, list) or len(ids) > MAX_FILES:
                raise ValueError('Lista inválida')
            chosen = [int(value) for value in ids]
            if len(chosen) != len(set(chosen)) or any(pk not in known for pk in chosen):
                raise ValueError('Archivo no pertenece al usuario')
        except (ValueError, KeyError, TypeError):
            return JsonResponse({'error': 'Selección de documentos inválida.'}, status=400)
        request.session['eduai_selected_file_ids'] = chosen
    remembered = request.session.get('eduai_selected_file_ids')
    chosen = known if remembered is None else (set(remembered) & known)
    authorized = [_filename(obj.nombre) for obj in files if obj.pk in chosen]
    token = make_token(request.user.username, authorized)
    return JsonResponse({
        'files': [{'id': obj.pk, 'name': obj.nombre, 'type': obj.tipo,
                   'stored_name': _filename(obj.nombre),
                   'preview_url': f'/dashboard/archivos/{obj.pk}/ver/'} for obj in files],
        'selected': [obj.pk for obj in files if obj.pk in chosen],
        'token': token,
        'selected_count': len(chosen),
        'total_count': len(files),
    })


@login_required(login_url='index')
@require_GET
def document_status(request):
    files = _files(request)
    if not files:
        return JsonResponse({'documents': []})
    try:
        res = requests.post(f'{BASE}/internal/documents/status',
            json={'username': request.user.username,
                  'filenames': [_filename(item.nombre) for item in files]},
            headers=HEADERS, timeout=(5, 20))
        res.raise_for_status()
        data = res.json()
    except (requests.RequestException, ValueError):
        return JsonResponse({'error': 'No se pudo consultar ChromaDB.'}, status=503)
    statuses = data.get('documents', {})
    return JsonResponse({'documents': [
        {'id': obj.pk, 'status': statuses.get(_filename(obj.nombre), {}).get('status', 'error'),
         'chunks': statuses.get(_filename(obj.nombre), {}).get('chunks', 0)}
        for obj in files], 'index_version': data.get('index_version')})


@login_required(login_url='index')
@require_GET
def document_preview(request, file_id):
    obj = get_object_or_404(Archivo, pk=file_id, user=request.user)
    filename = _filename(obj.nombre)
    if not filename:
        raise Http404
    try:
        upstream = requests.get(f'{BASE}/internal/documents/file',
            params={'username': request.user.username, 'filename': filename},
            headers=HEADERS, stream=True, timeout=(5, 30))
    except requests.RequestException:
        return JsonResponse({'error': 'Backend no disponible'}, status=503)
    if upstream.status_code == 404:
        upstream.close()
        raise Http404
    if upstream.status_code != 200:
        upstream.close()
        return JsonResponse({'error': 'No se pudo abrir el documento'}, status=502)
    mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    inline = mimetype in ('application/pdf', 'text/plain', 'text/markdown')
    def chunks():
        try:
            yield from upstream.iter_content(chunk_size=65536)
        finally:
            upstream.close()
    response = StreamingHttpResponse(chunks(), content_type=mimetype)
    response['Content-Disposition'] = ('inline' if inline else 'attachment') + '; filename="' + filename.replace('"', '') + '"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response

# EDUAI_FUENTES_V1
