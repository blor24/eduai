"""Banco privado por usuario. Las acciones que escriben datos requieren POST+CSRF."""
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .banco_forms import BancoPreguntaForm
from .banco_logic import extraer_generadas, armar_examen, MAX_PREGUNTAS
from .banco_models import BancoPregunta, ExamenGuardado, ExamenGuardadoItem
from .models import Archivo


@login_required(login_url='index')
def banco(request):
    qs = BancoPregunta.objects.filter(usuario=request.user).select_related('archivo')
    tipo = request.GET.get('tipo', '')
    dificultad = request.GET.get('dificultad', '')
    archivo_id = request.GET.get('archivo', '')
    query = request.GET.get('q', '').strip()[:100]
    if tipo in dict(BancoPregunta.TIPOS):
        qs = qs.filter(tipo=tipo)
    if dificultad in dict(BancoPregunta.DIFICULTADES):
        qs = qs.filter(dificultad=dificultad)
    if archivo_id.isdigit():
        qs = qs.filter(archivo_id=archivo_id)
    if query:
        qs = qs.filter(Q(enunciado__icontains=query) | Q(tema__icontains=query))
    from django.core.paginator import Paginator
    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    return render(request, 'tesis/banco_lista.html', {
        'page': 'banco', 'preguntas': page, 'archivos': Archivo.objects.filter(user=request.user),
        'tipos': BancoPregunta.TIPOS, 'dificultades': BancoPregunta.DIFICULTADES,
        'filtro': {'tipo': tipo, 'dificultad': dificultad, 'archivo': archivo_id, 'q': query},
    })


@login_required(login_url='index')
def pregunta_editar(request, pk=None):
    pregunta = get_object_or_404(BancoPregunta, pk=pk, usuario=request.user) if pk else None
    if request.method == 'POST':
        form = BancoPreguntaForm(request.POST, instance=pregunta, usuario=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pregunta guardada en el banco.')
            return redirect('banco_lista')
    else:
        form = BancoPreguntaForm(instance=pregunta, usuario=request.user)
    return render(request, 'tesis/banco_editar.html', {
        'page': 'banco', 'form': form, 'editando': bool(pregunta)
    })


@require_POST
@login_required(login_url='index')
def pregunta_eliminar(request, pk):
    get_object_or_404(BancoPregunta, pk=pk, usuario=request.user).delete()
    messages.success(request, 'Pregunta eliminada del banco. Los exámenes guardados conservan su copia.')
    return redirect('banco_lista')


@require_POST
@login_required(login_url='index')
def importar_generadas(request):
    if request.session.get('quiz_bank_saved'):
        messages.info(request, 'Las preguntas de este examen ya fueron guardadas.')
        return redirect('banco_lista')
    current = request.session.get('quiz_questions')
    if not current:
        messages.error(request, 'No hay un examen generado activo para guardar.')
        return redirect('examen')
    try:
        preguntas = extraer_generadas(json.loads(current) if isinstance(current, str) else current)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        messages.error(request, f'No se pudieron validar las preguntas: {exc}')
        return redirect('examen')
    archivo_id = request.session.get('quiz_source_file_id')
    archivo = Archivo.objects.filter(pk=archivo_id, user=request.user).first() if archivo_id else None
    tema = (request.POST.get('tema') or '').strip()[:120]
    dificultad = request.POST.get('dificultad', 'intermedia')
    if dificultad not in dict(BancoPregunta.DIFICULTADES):
        dificultad = 'intermedia'
    try:
        with transaction.atomic():
            for data in preguntas:
                instance = BancoPregunta(
                    usuario=request.user, archivo=archivo, tema=tema, dificultad=dificultad, **data
                )
                instance.full_clean()
                instance.save()
    except Exception:
        # Rollback: nunca insertar parcialmente preguntas generadas.
        messages.error(request, 'No fue posible guardar el examen. Verifica que las preguntas sean válidas.')
        return redirect('examen')
    request.session['quiz_bank_saved'] = True
    messages.success(request, f'Se guardaron {len(preguntas)} preguntas. Puedes editarlas en el banco.')
    return redirect('banco_lista')


@login_required(login_url='index')
def examenes_guardados(request):
    examenes = ExamenGuardado.objects.filter(usuario=request.user).prefetch_related('items')
    return render(request, 'tesis/banco_examenes.html', {'page': 'banco', 'examenes': examenes})


@login_required(login_url='index')
def examen_crear(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()[:2000]
        raw_ids = request.POST.getlist('preguntas')
        if not titulo or len(titulo) > 160 or not raw_ids or len(raw_ids) > MAX_PREGUNTAS:
            messages.error(request, 'Introduce un título y selecciona entre 1 y 100 preguntas.')
            return redirect('banco_crear_examen')
        if any(not val.isascii() or not val.isdecimal() for val in raw_ids):
            messages.error(request, 'Selección inválida de preguntas.')
            return redirect('banco_crear_examen')
        ids = [str(int(val)) for val in raw_ids]
        if len(set(ids)) != len(ids):
            messages.error(request, 'Selección inválida de preguntas.')
            return redirect('banco_crear_examen')
        qs = BancoPregunta.objects.filter(usuario=request.user, id__in=ids)
        by_id = {str(obj.pk): obj for obj in qs}
        if len(by_id) != len(ids):
            messages.error(request, 'Una o más preguntas no pertenecen a tu banco.')
            return redirect('banco_crear_examen')
        with transaction.atomic():
            examen = ExamenGuardado.objects.create(usuario=request.user, titulo=titulo, descripcion=descripcion)
            ExamenGuardadoItem.objects.bulk_create([
                ExamenGuardadoItem(examen=examen, pregunta=by_id[identifier], posicion=pos,
                                    tipo=by_id[identifier].tipo, contenido=by_id[identifier].exportar())
                for pos, identifier in enumerate(ids, 1)
            ])
        messages.success(request, 'Examen guardado. Puedes practicarlo cuando quieras.')
        return redirect('banco_detalle_examen', pk=examen.pk)
    preguntas = BancoPregunta.objects.filter(usuario=request.user).select_related('archivo').order_by('-creado')[:500]
    return render(request, 'tesis/banco_crear_examen.html', {
        'page': 'banco', 'preguntas': preguntas, 'max_preguntas': MAX_PREGUNTAS
    })


@login_required(login_url='index')
def examen_detalle(request, pk):
    examen = get_object_or_404(ExamenGuardado.objects.prefetch_related('items'), pk=pk, usuario=request.user)
    return render(request, 'tesis/banco_detalle_examen.html', {'page': 'banco', 'examen': examen})


@require_POST
@login_required(login_url='index')
def examen_practicar(request, pk):
    examen = get_object_or_404(ExamenGuardado, pk=pk, usuario=request.user)
    items = list(examen.items.order_by('posicion').values_list('tipo', 'contenido'))
    try:
        data = armar_examen(items)
    except ValueError:
        messages.error(request, 'El examen guardado no tiene preguntas válidas.')
        return redirect('banco_detalle_examen', pk=pk)
    # Reutiliza la misma corrección de tesis.views.examen, sin nueva llamada al LLM.
    request.session['quiz_questions'] = json.dumps(data, ensure_ascii=False)
    request.session['quiz_source_file_id'] = None
    request.session['quiz_bank_saved'] = True
    return redirect('examen')


@require_POST
@login_required(login_url='index')
def examen_eliminar(request, pk):
    get_object_or_404(ExamenGuardado, pk=pk, usuario=request.user).delete()
    messages.success(request, 'Examen eliminado; las preguntas del banco se mantienen.')
    return redirect('banco_examenes')
