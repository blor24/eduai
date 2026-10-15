#!/usr/bin/env python3
"""Instalador incremental conservador para EduAI + kits IA/ODF (octubre 2026)."""
from pathlib import Path
import ast
import shutil
import sys

KIT = Path(__file__).resolve().parent
ROOT = KIT.parent
BACKUP = ROOT / '.eduai_documents_backup'


def read(rel):
    p = ROOT / rel
    if not p.is_file():
        raise RuntimeError(f'No existe el archivo esperado: {rel}')
    return p.read_text(encoding='utf-8')


def replace(text, old, new, rel):
    if old == new or new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(f'{rel}: se esperaba una única coincidencia de {old[:90]!r}; revisar manualmente')
    return text.replace(old, new, 1)


def save(rel, text, *, newfile=False):
    p = ROOT / rel
    if p.exists():
        old = p.read_text(encoding='utf-8')
        if old == text:
            return
        if newfile:
            raise RuntimeError(f'{rel} ya existe con contenido diferente')
        backup = BACKUP / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(p, backup)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    print('Actualizado:', rel)


def run():
    b = 'backend/eduai-backend.py'
    vector = 'backend/vectorstorage.py'
    llm = 'backend/llmchat.py'
    views = 'frontend/djtesis/tesis/views.py'
    urls = 'frontend/djtesis/root/urls.py'
    chat = 'frontend/djtesis/tesis/templates/tesis/chat.html'
    files = 'frontend/djtesis/tesis/templates/tesis/archivos.html'
    for rel in [b, vector, llm, views, urls, chat, files, 'compose.yaml']:
        read(rel)
    if 'def reindex_everyone' not in read(vector) or 'AI_INTERNAL_TOKEN' not in read('compose.yaml'):
        raise RuntimeError('No se detectó la versión actual de EduAI con administración de IA')
    if 'def installed_ollama_models' not in read(b):
        raise RuntimeError('Falta el administrador dinámico de Ollama')

    edits = {}
    # Chroma: limitar búsqueda al origen. Las colecciones y dimensiones permanecen intactas.
    s = read(vector)
    s = replace(s, '''    def retriever(self, username):
        return self.store(username).as_retriever(search_kwargs={'k': 5})''', '''    def retriever(self, username, filenames=None):
        if filenames is None:
            return self.store(username).as_retriever(search_kwargs={'k': 5})
        if not filenames:
            raise ValueError('Selecciona al menos un documento.')
        sources = [f'uploads/{username}/{name}' for name in dict.fromkeys(filenames)]
        where = ({'source': sources[0]} if len(sources) == 1 else
                 {'$or': [{'source': src} for src in sources]})
        return self.store(username).as_retriever(search_kwargs={'k': 5, 'filter': where})''', vector)
    edits[vector] = s

    s = read(llm)
    s = replace(s, '''class PDFStorage:
    def __init__(self, username):
        self.username = username

    def retrieve(self):
        return VectorStorageManager().retriever(self.username)''', '''class PDFStorage:
    def __init__(self, username, filenames=None):
        self.username = username
        self.filenames = filenames

    def retrieve(self):
        return VectorStorageManager().retriever(self.username, self.filenames)''', llm)
    edits[llm] = s

    s = read(b)
    s = replace(s, 'from pathlib import Path\n', 'from pathlib import Path\nfrom document_api import register as register_document_routes\nfrom document_scope import verify as verify_document_scope, InvalidDocumentScope\n', b)
    s = replace(s, 'app = Flask(__name__)\n', 'app = Flask(__name__)\nregister_document_routes(app)\n', b)
    s = replace(s, '''    username = msg.get('username')
    sender_content = msg.get('sender_content')
    receiver = str(msg.get('receiver') or '').strip()''', '''    try:
        username, selected_files = verify_document_scope(msg.get('document_token'))
        if not selected_files:
            raise InvalidDocumentScope('Selecciona documentos disponibles antes de preguntar.')
    except InvalidDocumentScope as exc:
        emit('model_error', {'messageId': msg.get('messageId'), 'error': str(exc)})
        return
    sender_content = msg.get('sender_content')
    if not isinstance(sender_content, str) or not sender_content.strip() or len(sender_content) > 12000:
        emit('model_error', {'messageId': msg.get('messageId'), 'error': 'Mensaje vacío o demasiado largo.'})
        return
    receiver = str(msg.get('receiver') or '').strip()''', b)
    s = replace(s, '    store = PDFStorage(username)\n', '    store = PDFStorage(username, selected_files)\n', b)
    s = replace(s, '''response = requests.post(f"{DJANGO_BASE_URL}/dashboard/chat/save_mensaje/", json=data)''', '''response = requests.post(f"{DJANGO_BASE_URL}/dashboard/chat/save_mensaje/", json=data,
            headers={'X-EduAI-Internal-Token': os.getenv('AI_INTERNAL_TOKEN', '')}, timeout=15)''', b)
    # Endpoints Django->Flask: impedir uso directo por personas sin sesión Django.
    s = replace(s, '''def upload():
    try:''', '''def upload():
    from document_api import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    try:''', b)
    s = replace(s, '''def delete_file():
    try:''', '''def delete_file():
    from document_api import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    try:''', b)
    s = replace(s, """def file():
    qgen = QuestionGenerator()
    try:""", """def file():
    from document_api import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    qgen = QuestionGenerator()
    try:""", b)
    s = replace(s, """def exam():
    qgen = QuestionGenerator()
    try:""", """def exam():
    from document_api import authorized
    if not authorized():
        return jsonify({'error': 'Prohibido'}), 403
    qgen = QuestionGenerator()
    try:""", b)
    edits[b] = s

    s = read(views)
    s = replace(s, '''response = requests.post(flask_url, data=data, files=files)''', '''response = requests.post(flask_url, data=data, files=files,
                    headers={'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')},
                    timeout=180)''', views)
    s = replace(s, '''archivo = Archivo(user=request.user, nombre=file_obj.name, tipo=os.path.splitext(file_obj.name)[1].lower(), fecha_carga=datetime.now())''', '''saved_filename = os.path.basename(response.json()['file_path'])
                archivo = Archivo(user=request.user, nombre=saved_filename,
                    tipo=os.path.splitext(saved_filename)[1].lower(), fecha_carga=datetime.now())''', views)
    s = replace(s, '''            instancia = Archivo.objects.get(user=request.user, id=id_archivo)''', '''            instancia = Archivo.objects.filter(user=request.user, id=id_archivo).first()
            if instancia is None:
                messages.error(request, 'No existe ese archivo en tu biblioteca.')
                return redirect('archivos')
            filename = instancia.nombre  # no confiar en el campo oculto del formulario''', views)
    s = replace(s, '''response = requests.post(flask_url, data=data)
                response_data = response.json()''', '''response = requests.post(flask_url, data=data,
                    headers={'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')},
                    timeout=45)
                response_data = response.json()''', views)
    s = replace(s, '''@csrf_exempt
def save_mensaje(request):
    if request.method == 'POST':''', '''@csrf_exempt
def save_mensaje(request):
    import hmac
    secret = os.environ.get('AI_INTERNAL_TOKEN', '')
    if not secret or not hmac.compare_digest(secret, request.headers.get('X-EduAI-Internal-Token', '')):
        return JsonResponse({'error': 'Prohibido'}, status=403)
    if request.method == 'POST':''', views)
    # Las rutas de exámenes y exportación también requieren el token interno.
    target = 'response = requests.post(flask_url, data=data)'
    replacement = """response = requests.post(flask_url, data=data,
                headers={'X-EduAI-Internal-Token': os.environ.get('AI_INTERNAL_TOKEN', '')},
                timeout=300)"""
    if replacement not in s:
        if s.count(target) != 2:
            raise RuntimeError('No se reconocen ambas solicitudes /exam y /file')
        s = s.replace(target, replacement)
    # Evitar continuar la carga cuando el usuario no selecciona archivo.
    s = replace(s, """                messages.error(request, JsonResponse({'status': 'error', 'message': 'Falta identficación de usuario o archivo.'}, status=400))""",
        """                messages.error(request, 'Selecciona un archivo para cargar.')
                return redirect('archivos')""", views)
    edits[views] = s

    s = read(urls)
    s = replace(s, 'from tesis import views \n', 'from tesis import views \nfrom tesis import document_views\n', urls)
    s = replace(s, "    path('dashboard/archivos', views.archivos, name='archivos'),", '''    path('dashboard/archivos', views.archivos, name='archivos'),
    path('dashboard/archivos/estado/', document_views.document_status, name='archivo_estado'),
    path('dashboard/archivos/<int:file_id>/ver/', document_views.document_preview, name='archivo_vista'),
    path('dashboard/chat/documents/', document_views.chat_documents, name='chat_documents'),''', urls)
    edits[urls] = s

    s = read(chat)
    s = replace(s, '<div id="chat-container"', '''<section class="card mb-3" aria-label="Documentos para consulta">
  <div class="card-body py-2">
    <div class="d-flex justify-content-between align-items-center">
      <strong>Documentos para este chat</strong>
      <button type="button" id="docs-select-all" class="btn btn-outline-secondary btn-sm">Seleccionar todos</button>
    </div>
    <div id="chat-files" style="max-height:128px; overflow-y:auto;" class="d-flex flex-wrap gap-3 mt-2"></div>
    <small id="chat-files-status" class="text-muted" aria-live="polite">Cargando tus documentos...</small>
    <form id="chat-documents-csrf" hidden>{% csrf_token %}</form>
  </div>
</section>
<div id="chat-container"''', chat)
    s = replace(s, '  const sendButton = document.getElementById(\'send-button\');', '''  const sendButton = document.getElementById('send-button');
  let documentToken = null;
  let selectedDocumentIds = [];
  let userDocuments = [];
  const docsTarget = document.getElementById('chat-files');
  const docsStatus = document.getElementById('chat-files-status');
  async function syncDocuments(ids) {
    try {
      const options = {credentials: 'same-origin', cache: 'no-store'};
      if (ids !== undefined) {
        options.method = 'POST';
        options.headers = {'Content-Type':'application/json',
          'X-CSRFToken': document.querySelector('#chat-documents-csrf [name=csrfmiddlewaretoken]').value};
        options.body = JSON.stringify({ids});
      }
      const r = await fetch("{% url 'chat_documents' %}", options);
      if (!r.ok) throw new Error('No se pudo guardar la selección');
      const data = await r.json();
      documentToken = data.token;
      selectedDocumentIds = data.selected;
      userDocuments = data.files;
      docsTarget.replaceChildren();
      for (const f of userDocuments) {
        const label = document.createElement('label');
        label.className = 'd-inline-flex align-items-center gap-1 small';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.value = f.id;
        input.checked = selectedDocumentIds.includes(f.id);
        input.addEventListener('change', () => {
          const choices = Array.from(docsTarget.querySelectorAll('input:checked')).map(n => Number(n.value));
          documentToken = null;
          syncDocuments(choices);
        });
        label.append(input, document.createTextNode(f.name));
        docsTarget.append(label);
      }
      docsStatus.textContent = `${data.selected_count} de ${data.total_count} documentos seleccionados`;
      sendButton.disabled = !(documentToken && selectedDocumentIds.length && modelsDropdown.value);
    } catch (e) {
      documentToken = null;
      docsStatus.textContent = 'No se pudo cargar la selección de documentos.';
      sendButton.disabled = true;
    }
  }
  document.getElementById('docs-select-all').addEventListener('click', () =>
    syncDocuments(userDocuments.map(f => f.id)));
  syncDocuments();
  setInterval(() => syncDocuments(), 300000);
  function escapeChatText(value) {
    return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',
      '"':'&quot;', "'":'&#39;'}[c]));
  }''', chat)
    s = replace(s, '      sendButton.disabled = !modelsDropdown.value;', '      sendButton.disabled = !(documentToken && selectedDocumentIds.length && modelsDropdown.value);', chat)
    s = replace(s, '        responseElement.innerHTML = data.receiver_response;', '        responseElement.textContent = data.receiver_response;', chat)
    s = replace(s, '''    if (!modelValue) {
      modelsStatus.textContent = 'No hay modelos disponibles.';
      return;
    }''', '''    if (!modelValue) {
      modelsStatus.textContent = 'No hay modelos disponibles.';
      return;
    }
    if (!documentToken || !selectedDocumentIds.length) {
      docsStatus.textContent = 'Selecciona primero uno o más documentos.';
      return;
    }''', chat)
    s = replace(s, '''    var chatBox = document.getElementById("messages");
    const messageId = Date.now();''', '''    var chatBox = document.getElementById("messages");
    username = escapeChatText(username);
    const safeMessageText = escapeChatText(messageText);
    modelText = escapeChatText(modelText);
    const messageId = Date.now();''', chat)
    s = replace(s, '''                          +messageText
''', '''                          +safeMessageText
''', chat)
    s = replace(s, '''      "messageId": messageId // Incluye messageId para identificar''', '''      "messageId": messageId,
      "document_token": documentToken // Validado y firmado por Django''', chat)
    # El antiguo código de mensajes entrantes insertaba cadenas externas como HTML.
    s = replace(s, '''+`${data.sender_content}`''', '''                          +escapeChatText(data.sender_content)''', chat)
    s = replace(s, '''+`${data.receiver_response}`''', '''                          +escapeChatText(data.receiver_response)''', chat)
    s = replace(s, '''+`${data.username}`''', '''                          +escapeChatText(data.username)''', chat)
    s = replace(s, '''+`${data.receiver}`''', '''                          +escapeChatText(data.receiver)''', chat)
    edits[chat] = s

    s = read(files)
    s = replace(s, '<th scope="col">Fecha de carga</th>', '<th scope="col">Fecha de carga</th>\n      <th scope="col">Índice activo</th>', files)
    s = replace(s, '''        <td>{{item.fecha_carga}}</td>''', '''        <td>{{item.fecha_carga}}</td>
        <td><span class="badge bg-secondary" data-index-file="{{ item.id }}">Consultando...</span></td>''', files)
    s = replace(s, '''        <td><button type="button" class="btn btn-outline-danger"''', '''        <td><a href="{% url 'archivo_vista' item.id %}" class="btn btn-outline-primary btn-sm" target="_blank" rel="noopener">Abrir</a>
        <button type="button" class="btn btn-outline-danger"''', files)
    s = replace(s, '''<script>
  document.getElementById('searchInput')''', '''<script>
  async function loadDocumentStatuses() {
    try {
      const response = await fetch("{% url 'archivo_estado' %}", {credentials:'same-origin', cache:'no-store'});
      if (!response.ok) throw new Error('Sin conexión');
      const data = await response.json();
      const labels = {indexed: 'Indexado', pending:'Sin indexar', missing:'No disponible', error:'Error'};
      for (const doc of data.documents || []) {
        const el = document.querySelector(`[data-index-file="${doc.id}"]`);
        if (!el) continue;
        el.className = 'badge ' + (doc.status === 'indexed' ? 'bg-success' : 'bg-warning text-dark');
        el.textContent = (labels[doc.status] || 'Error') + (doc.status === 'indexed' ? ` (${doc.chunks})` : '');
      }
    } catch (error) {
      document.querySelectorAll('[data-index-file]').forEach(el => el.textContent = 'Sin conexión');
    }
  }
  loadDocumentStatuses();
  document.getElementById('searchInput')''', files)
    edits[files] = s

    # Validar antes de escribir nada para evitar instalaciones a medias ante cambios conocidos.
    for rel, text in edits.items():
        if rel.endswith('.py'):
            ast.parse(text, filename=rel)
    for src in (KIT / 'archivos').rglob('*.py'):
        ast.parse(src.read_text(encoding='utf-8'), filename=str(src))
    for rel, text in edits.items():
        save(rel, text)
    for path in (KIT / 'archivos').rglob('*.py'):
        target = str(path.relative_to(KIT / 'archivos'))
        save(target, path.read_text(encoding='utf-8'), newfile=True)
    ignore = ROOT / '.gitignore'
    existing = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    if '.eduai_documents_backup/' not in existing:
        save('.gitignore', existing + '\n.eduai_documents_backup/\n')
    print('\nInstalación completada; ejecuta git diff, reconstruye frontend y backend, NO borres los volúmenes.')


if __name__ == '__main__':
    try:
        run()
    except (RuntimeError, OSError, SyntaxError) as exc:
        sys.exit('ERROR: ' + str(exc))
