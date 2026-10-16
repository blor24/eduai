#!/usr/bin/env python3
"""EduAI: guía de ayuda + dificultad real en LLM y etiquetas de banco.

Aplicación incremental e idempotente. Se detiene ante estructuras inesperadas.
"""
from pathlib import Path
import shutil
import sys

ROOT = Path.cwd()
KIT = Path(__file__).resolve().parent
APP = ROOT / 'frontend/djtesis/tesis'
BACKEND = ROOT / 'backend'
BACKUP = ROOT / '.eduai_guia_backup'
MARK = 'EDUAI_GUIDE_DIFFICULTY_V1'
changes = {}


def take(rel):
    path = ROOT / rel
    if not path.is_file():
        raise RuntimeError(f'Archivo requerido no encontrado: {rel}')
    return changes.get(rel, path.read_text(encoding='utf-8'))


def replace(rel, old, new, count=1):
    content = take(rel)
    found = content.count(old)
    if found != count:
        raise RuntimeError(f'{rel}: se esperaban {count} coincidencias y se encontraron {found} para {old[:90]!r}')
    changes[rel] = content.replace(old, new, count)


def write_new(rel, body):
    if (ROOT / rel).exists():
        raise RuntimeError(f'Ya existe {rel}; no se sobrescribió.')
    changes[rel] = body


def run():
    views = 'frontend/djtesis/tesis/views.py'
    urls = 'frontend/djtesis/root/urls.py'
    base = 'frontend/djtesis/tesis/templates/tesis/base.html'
    exam = 'frontend/djtesis/tesis/templates/tesis/examen.html'
    export = 'frontend/djtesis/tesis/templates/tesis/genera-preguntas.html'
    files = 'frontend/djtesis/tesis/templates/tesis/archivos.html'
    chat = 'frontend/djtesis/tesis/templates/tesis/chat.html'
    bank = 'frontend/djtesis/tesis/banco_views.py'
    bankmodel = 'frontend/djtesis/tesis/banco_models.py'
    banklist = 'frontend/djtesis/tesis/templates/tesis/banco_lista.html'
    bankedit = 'frontend/djtesis/tesis/templates/tesis/banco_editar.html'
    admin = 'frontend/djtesis/tesis/admin.py'
    flask = 'backend/eduai-backend.py'
    llm = 'backend/llmgeneration.py'
    for path in (views, urls, base, exam, export, files, chat, bank, bankmodel, banklist, bankedit, admin, flask, llm):
        take(path)
    if MARK in take(views):
        print('Kit ya instalado. No se hicieron modificaciones.')
        return

    # 1. Vista y navegación de ayuda
    replace(urls, "    path('dashboard/examen', views.examen, name='examen'),",
            "    path('dashboard/ayuda/', views.ayuda, name='ayuda'),\n    path('dashboard/examen', views.examen, name='examen'),")
    replace(views, "@login_required(login_url='index')\ndef resultados(request):",
            f"# {MARK}\n@login_required(login_url='index')\ndef ayuda(request):\n    return render(request, 'tesis/ayuda.html', {{'page': 'ayuda'}})\n\n@login_required(login_url='index')\ndef resultados(request):")
    nav = '''          <li class="nav-item">
            <a class="nav-link {% if page == 'ayuda' %}active{% endif %}" href="{% url 'ayuda' %}">
              <i class="bi bi-question-circle"></i> Guía de uso
            </a>
          </li>
'''
    replace(base, '          {% if request.user.is_staff %}', nav+'          {% if request.user.is_staff %}', count=2)
    write_new('frontend/djtesis/tesis/templates/tesis/ayuda.html',
              (KIT/'archivos/frontend/djtesis/tesis/templates/tesis/ayuda.html').read_text(encoding='utf-8'))

    # 2. Ayuda contextual
    replace(files, '<th scope="col">Índice activo</th>',
            '<th scope="col">Índice activo <a href="{% url \'ayuda\' %}#documentos" class="text-decoration-none" title="¿Qué significa índice activo?" aria-label="Explicación del índice activo"><i class="bi bi-question-circle"></i></a></th>')
    replace(chat, '<strong>Documentos para este chat</strong>',
            '<strong>Documentos para este chat <a href="{% url \'ayuda\' %}#chat" aria-label="Cómo seleccionar documentos" title="Cómo funciona la selección"><i class="bi bi-question-circle"></i></a></strong>')
    replace(chat, '<strong class="small">Fuentes y fragmentos consultados</strong>',
            '<strong class="small">Fuentes y fragmentos consultados <a href="{% url \'ayuda\' %}#chat" title="Cómo interpretar estas fuentes" aria-label="Explicación de fuentes"><i class="bi bi-question-circle"></i></a></strong>')

    # 3. Formulario de dificultad en ambos generadores
    select = '''      <div class="col">
        <label for="dificultadSelect" class="form-label">Dificultad <a href="{% url 'ayuda' %}#examenes" title="Qué cambia con la dificultad" aria-label="Ayuda sobre la dificultad"><i class="bi bi-question-circle"></i></a></label>
        <select class="form-select" id="dificultadSelect" name="dificultad" required>
          <option value="basica">Básica</option>
          <option value="intermedia" selected>Intermedia</option>
          <option value="avanzada">Avanzada</option>
          <option value="mixta">Mixta</option>
        </select>
      </div>
'''
    for path in (exam, export):
        replace(path, '<div class="row row-cols-4">', '<div class="row row-cols-1 row-cols-md-2 row-cols-xl-5 g-3">')
        replace(path, '      <div class="col d-flex align-items-center">', select+'      <div class="col d-flex align-items-center">')
    # Banco: ya no asigna una sola dificultad arbitraria al grupo.
    replace(exam,
            '<div><label class="form-label">Dificultad</label><select name="dificultad" class="form-select"><option value="basica">Básica</option><option value="intermedia" selected>Intermedia</option><option value="avanzada">Avanzada</option></select></div>',
            '<div class="small text-muted">Dificultad solicitada: <strong>{{ dificultad_solicitada|default:"Intermedia" }}</strong>. Las etiquetas iniciales pueden revisarse individualmente en el banco.</div>')
    replace(exam, '  <h2>Examen generado</h2>',
            '  <h2>Examen generado</h2>\n  <p class="text-muted small">Nivel solicitado: {{ dificultad_solicitada|default:"Intermedia" }}. Comprueba que las preguntas y respuestas sean apropiadas.</p>')

    # 4. Django comunica y conserva el parámetro solicitado
    replace(views,
            "            tipo_preguntas = request.POST.getlist('tipoPregunta')\n\n            flask_url = f\"{FLASK_BASE_URL}/exam\"",
            "            tipo_preguntas = request.POST.getlist('tipoPregunta')\n            dificultad = request.POST.get('dificultad', 'intermedia')\n            if dificultad not in ('basica', 'intermedia', 'avanzada', 'mixta'):\n                messages.error(request, 'Dificultad de examen inválida.')\n                return redirect('examen')\n\n            flask_url = f\"{FLASK_BASE_URL}/exam\"")
    replace(views,
            "                'tipo': tipo_preguntas\n            }",
            "                'tipo': tipo_preguntas,\n                'dificultad': dificultad\n            }")
    replace(views,
            "            'tipo': tipo_preguntas\n        }",
            "            'tipo': tipo_preguntas,\n            'dificultad': dificultad\n        }")
    replace(views,
            "                    request.session['quiz_bank_saved'] = False",
            "                    request.session['quiz_bank_saved'] = False\n                    request.session['quiz_requested_difficulty'] = dificultad")
    replace(views,
            "'puede_guardar_banco':True}",
            "'puede_guardar_banco':True, 'dificultad_solicitada':dificultad.title()}")
    replace(views,
            "                'puede_guardar_banco': not request.session.get('quiz_bank_saved', False),",
            "                'puede_guardar_banco': not request.session.get('quiz_bank_saved', False),\n                'dificultad_solicitada': request.session.get('quiz_requested_difficulty', 'intermedia').title(),")
    replace(views,
            "        tipo_preguntas = request.POST.getlist('tipoPregunta')\n\n        flask_url = f\"{FLASK_BASE_URL}/file\"",
            "        tipo_preguntas = request.POST.getlist('tipoPregunta')\n        dificultad = request.POST.get('dificultad', 'intermedia')\n        if dificultad not in ('basica', 'intermedia', 'avanzada', 'mixta'):\n            messages.error(request, 'Dificultad de generación inválida.')\n            return redirect('generar')\n\n        flask_url = f\"{FLASK_BASE_URL}/file\"")
    # POST validado en Flask. No cambia las funciones de generación del chat.
    replace(flask,
            "        tipo = request.form.getlist('tipo')  \n",
            "        tipo = request.form.getlist('tipo')  \n        dificultad = request.form.get('dificultad', 'intermedia')\n", count=2)
    replace(flask,
            'results = qgen.generate_all_types(types=tipo, number=numero, namespace=username, filename=archivo)',
            'results = qgen.generate_all_types(types=tipo, number=numero, namespace=username, filename=archivo, dificultad=dificultad)', count=2)

    # 5. Motor de generación: prompt cognitivo explícito por lote, con metadatos para banco
    insert = 'from eduai_difficulty import instrucciones, plan_generacion, NIVELES\n'
    replace(llm, 'from ai_runtime import config\n', 'from ai_runtime import config\n'+insert)
    replace(llm, '                Text:\n                {documents}',
            '                **COGNITIVE DIFFICULTY INSTRUCTIONS:**\n                {difficulty_guide}\n\n                Text:\n                {documents}', count=4)
    replace(llm, 'input_variables=["number", "documents"]',
            'input_variables=["number", "documents", "difficulty_guide"]', count=4)
    replace(llm, '    def _batch(self, kind, amount, passage):',
            '    def _batch(self, kind, amount, passage, dificultad):')
    replace(llm, "raw = chain.invoke({'number': amount, 'documents': passage})",
            "raw = chain.invoke({'number': amount, 'documents': passage, 'difficulty_guide': instrucciones(dificultad)})")
    replace(llm,
            '    def generate_all_types(self, types, number, namespace, filename):',
            "    def generate_all_types(self, types, number, namespace, filename, dificultad='intermedia'):")
    replace(llm,
            "        if not types or any(kind not in self.prompts for kind in types):\n            raise ValueError('Tipo de pregunta no permitido')",
            "        if not types or any(kind not in self.prompts for kind in types):\n            raise ValueError('Tipo de pregunta no permitido')\n        if dificultad not in NIVELES:\n            raise ValueError('Dificultad no permitida')")
    replace(llm,
            '''            batches = 1 if kind == 'emparejar' else math.ceil(number / 4)
            all_items = []
            for i in range(batches):
                amount = number if kind == 'emparejar' else min(4, number - len(all_items))
                position = min(len(docs) - 1, int(i * len(docs) / batches))
                # Distribuye las preguntas sobre distintas secciones; nunca concatena todo el PDF.
                passage = '\\n'.join(docs[position:position+3])[:4200]
                all_items.extend(self._batch(kind, amount, passage))''',
            '''            plan = plan_generacion(kind, number, dificultad)
            all_items = []
            for i, (level, amount) in enumerate(plan):
                position = min(len(docs) - 1, int(i * len(docs) / len(plan)))
                # Distribuye las preguntas sobre distintas secciones; nunca concatena todo el PDF.
                passage = '\\n'.join(docs[position:position+3])[:4200]
                items = self._batch(kind, amount, passage, level)
                for item in items:
                    # Metadato interno, nunca solicitado al LLM.
                    item['eduai_dificultad'] = level if level != 'mixta' else 'intermedia'
                all_items.extend(items)''')
    write_new('backend/eduai_difficulty.py', (KIT/'archivos/backend/eduai_difficulty.py').read_text(encoding='utf-8'))

    # 6. Banco: conservar solicitado y clasificado; «mixta» se desglosa por pregunta.
    replace(bankmodel,
            "    dificultad = models.CharField(max_length=12, choices=DIFICULTADES, default='intermedia')",
            "    dificultad = models.CharField(max_length=12, choices=DIFICULTADES, default='intermedia')\n    dificultad_solicitada = models.CharField(max_length=12, choices=DIFICULTADES + [('mixta', 'Mixta')], default='intermedia', editable=False)")
    replace(bank,
            "    dificultad = request.POST.get('dificultad', 'intermedia')\n    if dificultad not in dict(BancoPregunta.DIFICULTADES):\n        dificultad = 'intermedia'",
            """    solicitada = request.session.get('quiz_requested_difficulty', 'intermedia')
    if solicitada not in ('basica', 'intermedia', 'avanzada', 'mixta'):
        solicitada = 'intermedia'
    # Conserva el orden de los grupos y preguntas del JSON antes de normalizarlos.
    original = json.loads(current) if isinstance(current, str) else current
    etiquetas = [q.get('eduai_dificultad') for grupo in original.values()
                 for q in grupo.get('questions', [])]
    if len(etiquetas) != len(preguntas):
        messages.error(request, 'Inconsistencia en las etiquetas de dificultad.')
        return redirect('examen')""")
    replace(bank,
            '''            for data in preguntas:
                instance = BancoPregunta(
                    usuario=request.user, archivo=archivo, tema=tema, dificultad=dificultad, **data
                )''',
            '''            for data, etiqueta in zip(preguntas, etiquetas):
                nivel = etiqueta if etiqueta in dict(BancoPregunta.DIFICULTADES) else (
                    solicitada if solicitada in dict(BancoPregunta.DIFICULTADES) else 'intermedia'
                )
                instance = BancoPregunta(
                    usuario=request.user, archivo=archivo, tema=tema,
                    dificultad=nivel, dificultad_solicitada=solicitada, **data
                )''')
    replace(banklist,
            '{{ p.get_dificultad_display }}</span>',
            '{{ p.get_dificultad_display }}</span> <span class="text-muted small" title="Dificultad solicitada al generador (no verificada automáticamente)">Solicitada: {{ p.get_dificultad_solicitada_display }}</span>')
    replace(bankedit,
            '<form method="post" class="card card-body"',
            '''{% if editando %}<p class="small text-muted">Dificultad solicitada durante la generación: <strong>{{ form.instance.get_dificultad_solicitada_display }}</strong>. La dificultad editable es una clasificación revisable, no verificación automática.</p>{% endif %}
<form method="post" class="card card-body"''')
    replace(admin,
            "list_display = ('id', 'usuario', 'tipo', 'dificultad', 'tema', 'archivo', 'creado')",
            "list_display = ('id', 'usuario', 'tipo', 'dificultad', 'dificultad_solicitada', 'tema', 'archivo', 'creado')")
    # Evita propagar el nivel de un examen generado a prácticas del banco.
    replace(bank,
            "    request.session['quiz_bank_saved'] = True\n    return redirect('examen')",
            "    request.session['quiz_bank_saved'] = True\n    request.session['quiz_requested_difficulty'] = 'intermedia'\n    return redirect('examen')")

    # Ignorar copias de seguridad locales
    gitignore = '.gitignore'
    original = (ROOT/gitignore).read_text(encoding='utf-8') if (ROOT/gitignore).exists() else ''
    if '.eduai_guia_backup/' not in original:
        changes[gitignore] = original.rstrip() + '\n.eduai_guia_backup/\n'

    # Todas las precondiciones se validaron antes de escribir.
    for rel, contents in changes.items():
        dest = ROOT/rel
        if dest.exists():
            bk = BACKUP/rel
            bk.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, bk)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding='utf-8')
    print(f'Instalación completada: {len(changes)} archivos modificados/creados; respaldo: {BACKUP}')
    print('IMPORTANTE: crear y revisar la migración para BancoPregunta.dificultad_solicitada.')
    print('Reconstruye frontend y backend; no borres volúmenes ni bases de datos.')


if __name__ == '__main__':
    try:
        run()
    except RuntimeError as err:
        print(f'ERROR: {err}', file=sys.stderr)
        sys.exit(1)
