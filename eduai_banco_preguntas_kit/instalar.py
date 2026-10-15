#!/usr/bin/env python3
"""Parche incremental para una raíz eduai/ con etapa 2 instalada."""
from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

ROOT = Path.cwd()
APP = ROOT / 'frontend/djtesis/tesis'
URLS = ROOT / 'frontend/djtesis/root/urls.py'
KIT = Path(__file__).resolve().parent / 'archivos/frontend/djtesis/tesis'
BACKUP = ROOT / '.eduai_banco_backup'
MARK = 'EDUAI_BANCO_V1'


def main():
    required = [APP / 'models.py', APP / 'views.py', APP / 'admin.py', URLS,
                APP / 'templates/tesis/examen.html', APP / 'templates/tesis/base.html']
    if any(not path.is_file() for path in required):
        raise RuntimeError('Ejecuta este script desde eduai/ con frontend/djtesis presente.')
    models, views, admin, urls = [p.read_text(encoding='utf8') for p in required[:4]]
    exam_html = required[4].read_text(encoding='utf8')
    base_html = required[5].read_text(encoding='utf8')

    # Instalador idempotente: no cambia archivos de una instalación anterior.
    if MARK in models:
        print('Banco de preguntas ya instalado. No se modificó el proyecto.')
        return

    anchors = {
        'models': 'from .ai_models import AIConfiguration, AIJob, AITestCase',
        'urls': "    path('dashboard/examen', views.examen, name='examen'),",
        'views_generate': "request.session['quiz_questions'] = json.dumps(preguntas)",
        'views_get': "    context = {'page':'examen', 'subidos': subidos}\n    return render(request, \"tesis/examen.html\", context)",
        'exam': '  <h2>Examen generado</h2>',
    }
    targets = {'models':models,'urls':urls,'views_generate':views,'views_get':views,'exam':exam_html}
    missing = [key for key, anchor in anchors.items() if anchor not in targets[key]]
    if missing:
        raise RuntimeError(f'Incompatibilidad con el código actual: {missing}. No se escribió nada.')
    for fname in ['banco_models.py','banco_forms.py','banco_logic.py','banco_views.py']:
        target = APP / fname
        if target.exists():
            raise RuntimeError(f'{target} ya existe y no contiene la marca del parche. Revisión manual necesaria.')
    for name in ['banco_lista.html','banco_editar.html','banco_crear_examen.html',
                 'banco_examenes.html','banco_detalle_examen.html']:
        if (APP/'templates/tesis'/name).exists():
            raise RuntimeError(f'Ya existe {name}. Revisión manual necesaria.')

    models += f'\n# {MARK}\nfrom .banco_models import BancoPregunta, ExamenGuardado, ExamenGuardadoItem\n'
    urls = urls.replace('from tesis import views \n', 'from tesis import views \nfrom tesis import banco_views\n', 1)
    if 'from tesis import banco_views' not in urls:
        urls = 'from tesis import banco_views\n' + urls
    additions = '''    path('dashboard/banco/', banco_views.banco, name='banco_lista'),
    path('dashboard/banco/nueva/', banco_views.pregunta_editar, name='banco_nueva'),
    path('dashboard/banco/<int:pk>/editar/', banco_views.pregunta_editar, name='banco_editar'),
    path('dashboard/banco/<int:pk>/eliminar/', banco_views.pregunta_eliminar, name='banco_eliminar'),
    path('dashboard/banco/importar/', banco_views.importar_generadas, name='banco_importar'),
    path('dashboard/banco/examenes/', banco_views.examenes_guardados, name='banco_examenes'),
    path('dashboard/banco/examenes/crear/', banco_views.examen_crear, name='banco_crear_examen'),
    path('dashboard/banco/examenes/<int:pk>/', banco_views.examen_detalle, name='banco_detalle_examen'),
    path('dashboard/banco/examenes/<int:pk>/practicar/', banco_views.examen_practicar, name='banco_practicar_examen'),
    path('dashboard/banco/examenes/<int:pk>/eliminar/', banco_views.examen_eliminar, name='banco_eliminar_examen'),
'''
    urls = urls.replace(anchors['urls'], additions + anchors['urls'], 1)

    admin += f'''
# {MARK}: administración (filtros y búsqueda) para superusuarios de Django
from .banco_models import BancoPregunta, ExamenGuardado, ExamenGuardadoItem

@admin.register(BancoPregunta)
class BancoPreguntaAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'tipo', 'dificultad', 'tema', 'archivo', 'creado')
    list_filter = ('tipo', 'dificultad', 'creado')
    search_fields = ('usuario__username', 'tema', 'enunciado')
    readonly_fields = ('creado', 'actualizado')

@admin.register(ExamenGuardado)
class ExamenGuardadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'usuario', 'creado')
    search_fields = ('titulo', 'usuario__username')
    readonly_fields = ('creado',)

@admin.register(ExamenGuardadoItem)
class ExamenGuardadoItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'examen', 'posicion', 'tipo')
    list_select_related = ('examen',)
'''
    views = views.replace(anchors['views_generate'],
                          anchors['views_generate'] + "\n                    request.session['quiz_source_file_id'] = archivo.pk\n                    request.session['quiz_bank_saved'] = False", 1)
    # En GET, mostrar exámenes guardados en la sesión; el POST existente sigue calificando.
    views = views.replace(anchors['views_get'],
        """    active = request.session.get('quiz_questions')
    if active:
        try:
            preguntas = json.loads(active) if isinstance(active, str) else active
            return render(request, 'tesis/examen.html', {
                'page': 'examen', 'subidos': subidos, 'preguntas': preguntas, 'ready': 1,
                'puede_guardar_banco': not request.session.get('quiz_bank_saved', False),
            })
        except (ValueError, TypeError):
            request.session.pop('quiz_questions', None)
    context = {'page':'examen', 'subidos': subidos}
    return render(request, \"tesis/examen.html\", context)""", 1)
    # El POST que genera nuevas preguntas también puede presentar la acción de guardar.
    views = views.replace("'preguntas':preguntas, 'ready':1}",
                          "'preguntas':preguntas, 'ready':1, 'puede_guardar_banco':True}", 1)

    save_form = '''  {% if puede_guardar_banco %}
  <form method="post" action="{% url 'banco_importar' %}" class="d-flex flex-wrap gap-2 align-items-end p-3 border rounded mb-3">
    {% csrf_token %}
    <div><label class="form-label">Tema (opcional)</label><input name="tema" maxlength="120" class="form-control" placeholder="Tema o unidad"></div>
    <div><label class="form-label">Dificultad</label><select name="dificultad" class="form-select"><option value="basica">Básica</option><option value="intermedia" selected>Intermedia</option><option value="avanzada">Avanzada</option></select></div>
    <button class="btn btn-outline-success" type="submit"><i class="bi bi-save"></i> Guardar preguntas en mi banco</button>
  </form>
  {% endif %}
'''
    exam_html = exam_html.replace(anchors['exam'], anchors['exam']+'\n'+save_form, 1)
    exam_html = exam_html.replace('{% block content %}',
        "{% block content %}\n<p><a class='btn btn-sm btn-outline-secondary' href='{% url \"banco_lista\" %}'>Ir al banco de preguntas</a></p>",1)

    nav = '''          <li class="nav-item">
            <a class="nav-link {% if page == 'banco' %}active{% endif %}" href="{% url 'banco_lista' %}">
              <i class="bi bi-collection"></i> Banco de preguntas
            </a>
          </li>
'''
    # Ambas barras (móvil y escritorio) contienen el enlace del chat.
    pattern = r'(?m)(^[ \t]*<li class="nav-item">\s*<a\s+class="nav-link \{% if page == \'chat\' %\}active\{% endif %\}"\s+href="/dashboard/chat")'
    base_html, count = re.subn(pattern, nav+r'\1', base_html)
    if count < 1:
        raise RuntimeError('No se encontró navegación del chat para agregar Banco. No se escribió nada.')

    writes = {APP/'models.py':models, APP/'views.py':views, APP/'admin.py':admin,
              URLS:urls, required[4]:exam_html, required[5]:base_html}
    ignore = ROOT / '.gitignore'
    original_ignore = ignore.read_text(encoding='utf8') if ignore.exists() else ''
    if '.eduai_banco_backup/' not in original_ignore:
        writes[ignore] = original_ignore.rstrip() + '\n.eduai_banco_backup/\n'
    for source in KIT.iterdir():
        if source.name.endswith('.py'):
            writes[APP/source.name] = source.read_text(encoding='utf8')
    for source in (KIT/'templates/tesis').iterdir():
        writes[APP/'templates/tesis'/source.name] = source.read_text(encoding='utf8')

    # Todas las precondiciones verificadas antes de escribir.
    for target, content in writes.items():
        if target.exists():
            destination = BACKUP/target.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf8')
    print(f'Instalación completada ({len(writes)} archivos). Respaldos en {BACKUP}/')
    print('Siguiente paso: genera migración, revisa las operaciones y reconstruye frontend.')


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
