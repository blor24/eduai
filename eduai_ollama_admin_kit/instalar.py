#!/usr/bin/env python3
"""Parche incremental para el proyecto EduAI tras instalar los kits Docker + Auth.
No ejecuta comandos Docker ni elimina datos. Ejecutar desde la raíz del repo.
"""
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
KIT = Path(__file__).resolve().parent
TEMPLATE_ROOT = KIT / 'archivos'
changes = {}


def get(name):
    path = ROOT / name
    if not path.is_file():
        sys.exit(f'ERROR: no existe {name}. Ejecuta desde la raíz de eduai.')
    return changes.get(name, path.read_text(encoding='utf-8'))


def sub(name, old, new, *, count=1, regex=False):
    source = get(name)
    # En algunos cambios (imports), el reemplazo es subcadena del original.
    if not new and regex and re.search(old, source, flags=re.M | re.S) is None:
        return
    if new and new in source and not (not regex and new in old and old in source):
        return
    if regex:
        text, n = re.subn(old, lambda m: new, source, count=count, flags=re.M | re.S)
    else:
        n = source.count(old)
        text = source.replace(old, new, count)
    if n != count:
        sys.exit(f'ERROR: {name}: patrón inesperado ({n} coincidencias). No se ha escrito ningún cambio.')
    changes[name] = text


VIEWS = 'frontend/djtesis/tesis/views.py'
URLS = 'frontend/djtesis/root/urls.py'
ADMIN = 'frontend/djtesis/tesis/admin.py'
CHAT = 'frontend/djtesis/tesis/templates/tesis/chat.html'
LLM = 'backend/llmchat.py'
FLASK = 'backend/eduai-backend.py'
COMPOSE = 'compose.yaml'

sub(VIEWS,
    r'#Debe ser igual al array que se encuentra en el backend \(llmchat\.py\).*?\n(?=def index\(request\):)',
    "from .ollama_api import list_models\n\n", regex=True)
sub(VIEWS,
    "    context = {'page':'chat', 'models': OLLAMA_MODELS, 'messages': messages, 'username': user}",
    """    try:
        models = list_models()
    except (requests.RequestException, ValueError, KeyError, TypeError):
        models = []
    context = {'page':'chat', 'models': models, 'messages': messages, 'username': user}""")
sub(VIEWS,
    "@login_required(login_url='index')\ndef chat(request):",
    """@never_cache
@login_required(login_url='index')
def available_ollama_models(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    try:
        return JsonResponse({'models': [item['name'] for item in list_models()]})
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'No se pudo consultar Ollama.'}, status=503)

@login_required(login_url='index')
def chat(request):""")

sub(URLS,
    'from tesis import views',
    'from tesis import ollama_admin\nfrom tesis import views')
sub(URLS,
    "    path('admin/', admin.site.urls),",
    """    path('admin/ollama/', admin.site.admin_view(ollama_admin.panel), name='ollama_admin'),
    path('admin/ollama/pull/', admin.site.admin_view(ollama_admin.pull_model), name='ollama_pull'),
    path('admin/ollama/delete/', admin.site.admin_view(ollama_admin.delete_model), name='ollama_delete'),
    path('admin/', admin.site.urls),""")
sub(URLS,
    "    path('dashboard/chat', views.chat, name='chat'),",
    """    path('dashboard/chat/models/', views.available_ollama_models, name='chat_models'),
    path('dashboard/chat', views.chat, name='chat'),""")

admin_text = get(ADMIN)
if 'admin.site.index_template = "tesis/admin_index_eduai.html"' not in admin_text:
    changes[ADMIN] = admin_text.rstrip() + '\n\nadmin.site.index_template = "tesis/admin_index_eduai.html"\n'

sub(CHAT,
    r'    <label for="model-dropdown">.*?</select>',
    '''    <label for="models" title="Modelos instalados en Ollama">Modelo:</label>
    <select id="models" aria-label="Modelo de Ollama" style="background-color:white; border:1px solid var(--border-color); color:var(--text-color); padding:4px 8px; border-radius:4px; font-size:12px;">
      {% for model in models %}<option value="{{ model.name }}">{{ model.name }}</option>{% empty %}<option value="">Sin modelos disponibles</option>{% endfor %}
    </select>
    <span id="models-status" role="status" aria-live="polite" style="font-size:11px;color:#6b7280;margin-left:6px;"></span>''',
    regex=True)
sub(CHAT,
    '  //Va al final de la conversacion',
    '''  // El selector se sincroniza para todos los usuarios cada 15 segundos.
  const modelsDropdown = document.getElementById('models');
  const modelsStatus = document.getElementById('models-status');
  const sendButton = document.getElementById('send-button');
  async function refreshAvailableModels() {
    try {
      const response = await fetch("{% url 'chat_models' %}", {credentials:'same-origin', cache:'no-store'});
      if (!response.ok) throw new Error('API de modelos no disponible');
      const result = await response.json();
      const names = result.models || [];
      const previous = modelsDropdown.value;
      const changed = names.join('\\0') !== Array.from(modelsDropdown.options).filter(o => o.value).map(o => o.value).join('\\0');
      if (changed) {
        modelsDropdown.replaceChildren();
        if (names.length === 0) {
          modelsDropdown.add(new Option('Sin modelos disponibles', ''));
        } else {
          names.forEach(name => modelsDropdown.add(new Option(name, name)));
          if (names.includes(previous)) modelsDropdown.value = previous;
        }
      }
      sendButton.disabled = !modelsDropdown.value;
      modelsStatus.textContent = names.length ? '' : 'Instala un modelo desde Administración.';
    } catch (error) {
      modelsStatus.textContent = 'No se pudo consultar Ollama.';
    }
  }
  refreshAvailableModels();
  setInterval(refreshAvailableModels, 15000);
  window.addEventListener('focus', refreshAvailableModels);
  socket.on('model_error', function(data) {
    const response = document.getElementById('receiver-response-' + data.messageId);
    if (response) response.textContent = data.error || 'El modelo ya no está disponible.';
    refreshAvailableModels();
  });

  //Va al final de la conversacion''')
sub(CHAT,
    '    if (messageText.trim() === "") return; // No permite enviar mensajes vacíos',
    '''    if (messageText.trim() === "") return; // No permite enviar mensajes vacíos
    if (!modelValue) {
      modelsStatus.textContent = 'No hay modelos disponibles.';
      return;
    }''')

sub(LLM,
    r'ollama_models = \[.*?\]\n',
    '', regex=True)
sub(LLM,
    r'class ChooseModel:.*?(?=\n# Clase para aplicación RAG)',
    '''class ChooseModel:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def choose(self):
        import os
        llm = ChatOllama(
            model=self.model_name,
            temperature=0.1,
            base_url=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
        )
        return prompt | llm | StrOutputParser()
''', regex=True)

sub(FLASK,
    'from llmchat import PDFStorage, RAGApplication, ChooseModel, ollama_models',
    'from llmchat import PDFStorage, RAGApplication, ChooseModel')
sub(FLASK,
    '@socketio.on("message")\ndef handle_message(msg):',
    '''def installed_ollama_models():
    base_url = os.getenv('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')
    response = requests.get(f'{base_url}/api/tags', timeout=(5, 12))
    response.raise_for_status()
    return {item['name'] for item in response.json().get('models', [])}


@socketio.on("message")
def handle_message(msg):''')
sub(FLASK,
    "    receiver = ollama_models[int(msg.get('receiver'))]",
    '''    receiver = str(msg.get('receiver') or '').strip()
    try:
        if receiver not in installed_ollama_models():
            emit('model_error', {
                'messageId': msg.get('messageId'),
                'error': 'Este modelo ya no está instalado. Selecciona otro modelo.'
            })
            return
    except (requests.RequestException, ValueError, KeyError):
        emit('model_error', {
            'messageId': msg.get('messageId'),
            'error': 'No se pudo comprobar la disponibilidad de Ollama.'
        })
        return''')
sub(FLASK,
    '    model = ChooseModel(int(msg.get(\'receiver\')))',
    '    model = ChooseModel(receiver)')
sub(FLASK,
    '    receiver_response = rag_app.run(sender_content)',
    '''    try:
        receiver_response = rag_app.run(sender_content)
    except Exception:
        app.logger.exception('Error al ejecutar el modelo %s', receiver)
        emit('model_error', {
            'messageId': msg.get('messageId'),
            'error': 'La consulta falló. Comprueba el modelo y vuelve a intentarlo.'
        })
        return''')

sub(COMPOSE,
    '      FLASK_BASE_URL: http://backend:8080',
    '      FLASK_BASE_URL: http://backend:8080\n      OLLAMA_BASE_URL: http://ollama:11434')

# Validar archivos adicionales antes de escribir nada.
newfiles = {}
for src in TEMPLATE_ROOT.rglob('*'):
    if not src.is_file():
        continue
    rel = src.relative_to(TEMPLATE_ROOT)
    dst = ROOT / rel
    content = src.read_bytes()
    if dst.exists():
        if dst.read_bytes() != content:
            sys.exit(f'ERROR: {rel} ya existe con contenido distinto. No se escribió ningún cambio.')
    else:
        newfiles[dst] = content

# Verificar sintaxis de los .py a modificar antes de escribir.
for name, content in changes.items():
    if name.endswith('.py'):
        try:
            compile(content, name, 'exec')
        except SyntaxError as exc:
            sys.exit(f'ERROR de sintaxis: {name}: {exc}')
for path, content in newfiles.items():
    if path.suffix == '.py':
        compile(content, str(path), 'exec')

for name, content in changes.items():
    (ROOT / name).write_text(content, encoding='utf-8')
    print('Modificado:', name)
for path, content in newfiles.items():
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print('Creado:', path.relative_to(ROOT))
print('\nInstalación del código completada. Ejecuta git diff y reconstruye frontend/backend.')
