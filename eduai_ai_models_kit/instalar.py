#!/usr/bin/env python3
"""Parche incremental para EduAI después de los kits Docker/Auth/Ollama.
Respalda los archivos reemplazados; no modifica las credenciales .env ni volúmenes.
"""
from pathlib import Path
import shutil
import re
import sys

KIT = Path(__file__).resolve().parent
ROOT = KIT.parent
BACKUP = ROOT / '.eduai_ai_backup'


def save(rel, text, overwrite=True):
    p = ROOT / rel
    if p.exists():
        old = p.read_text(encoding='utf-8')
        if old == text:
            return
        if not overwrite:
            raise RuntimeError(f'Archivo existente no reconocido: {rel}')
        b = BACKUP / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        if not b.exists():
            shutil.copy2(p, b)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    print('Actualizado:', rel)


def load(rel):
    p = ROOT / rel
    if not p.is_file():
        raise RuntimeError(f'No existe {rel}')
    return p.read_text(encoding='utf-8')


def change_once(text, old, new, path):
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(f'No se encontró una coincidencia única en {path}: {old[:75]!r}')
    return text.replace(old, new, 1)


def main():
    # Validar estructura antes de cualquier escritura.
    files = ['compose.yaml', 'backend/vectorstorage.py', 'backend/llmchat.py',
             'backend/eduai-backend.py', 'backend/llmgeneration.py',
             'frontend/djtesis/tesis/models.py', 'frontend/djtesis/root/urls.py',
             'frontend/djtesis/tesis/ollama_admin.py']
    for p in files:
        load(p)
    if 'installed_ollama_models' not in load('backend/eduai-backend.py'):
        raise RuntimeError('Primero instala el kit previo de gestión de Ollama; no se reconoce el código actual.')
    if 'class QuestionGenerator' not in load('backend/llmgeneration.py'):
        raise RuntimeError('Generador no compatible con el parche')
    if 'class VectorStorageManager' not in load('backend/vectorstorage.py'):
        raise RuntimeError('Almacenamiento no compatible')
    for original in KIT.joinpath('archivos').rglob('*'):
        if original.is_file() and '__pycache__' not in str(original):
            rel = original.relative_to(KIT / 'archivos')
            save(str(rel), original.read_text(encoding='utf-8'))

    # Registrar nuevos modelos de Django sin alterar tablas actuales.
    path = 'frontend/djtesis/tesis/models.py'
    src = load(path)
    marker = 'from .ai_models import AIConfiguration, AIJob, AITestCase'
    if marker not in src:
        if 'from .ai_models import AIConfiguration, AIJob' in src:
            src = src.replace('from .ai_models import AIConfiguration, AIJob', marker)
        else:
            src += '\n\n# Entidades para la administración de modelos y reindexaciones\n' + marker + '\n'
    save(path, src)

    path = 'frontend/djtesis/tesis/admin.py'
    src = load(path)
    if 'class AIJobAdmin' not in src:
        src += '''\n\nfrom .ai_models import AIConfiguration, AIJob, AITestCase\n\n@admin.register(AIConfiguration)\nclass AIConfigurationAdmin(admin.ModelAdmin):\n    list_display = ('generation_model', 'embedding_provider', 'embedding_model', 'index_version', 'updated_at')\n    readonly_fields = ('generation_model', 'embedding_provider', 'embedding_model', 'index_version', 'num_ctx', 'num_predict', 'updated_at')\n    def has_add_permission(self, request):\n        return False\n    def has_delete_permission(self, request, obj=None):\n        return False\n    def has_change_permission(self, request, obj=None):\n        return request.user.is_superuser\n\n@admin.register(AIJob)\nclass AIJobAdmin(admin.ModelAdmin):\n    list_display = ('id', 'kind', 'model_name', 'status', 'progress', 'created_at')\n    list_filter = ('kind', 'status', 'created_at')\n    readonly_fields = ('kind', 'provider', 'model_name', 'status', 'progress', 'error', 'target_version', 'submitted_by', 'created_at', 'started_at', 'finished_at')\n    def has_add_permission(self, request):\n        return False\n    def has_delete_permission(self, request, obj=None):\n        return False\n    def has_change_permission(self, request, obj=None):\n        return request.user.is_superuser\n'''
    if 'class AITestCaseAdmin' not in src:
        src += """

@admin.register(AITestCase)
class AITestCaseAdmin(admin.ModelAdmin):
    list_display = ('username', 'query', 'expected_filename', 'enabled')
    list_filter = ('enabled',)
    search_fields = ('username', 'query', 'expected_filename')
"""
    save(path, src)

    path = 'frontend/djtesis/root/urls.py' 
    src = load(path)
    if 'from tesis import ai_control' not in src:
        src = change_once(src, 'from tesis import ollama_admin', 'from tesis import ollama_admin\nfrom tesis import ai_control', path)
    if "name='ai_panel'" not in src:
        src = change_once(src, 'urlpatterns = [', '''urlpatterns = [\n    path('admin/ia/', admin.site.admin_view(ai_control.panel), name='ai_panel'),\n    path('admin/ia/generator/', admin.site.admin_view(ai_control.set_generator), name='ai_set_generator'),\n    path('admin/ia/jobs/', admin.site.admin_view(ai_control.queue_job), name='ai_queue_job'),\n    path('internal/ai/config/', ai_control.internal_config, name='ai_internal_config'),\n    path('internal/ai/jobs/claim/', ai_control.claim_job, name='ai_job_claim'),\n    path('internal/ai/tests/', ai_control.internal_testcases, name='ai_internal_tests'),\n    path('internal/ai/jobs/<int:job_id>/report/', ai_control.report_job, name='ai_job_report'),''', path)
    save(path, src)

    path = 'frontend/djtesis/tesis/templates/tesis/admin_index_eduai.html'
    src = load(path)
    if "'ai_panel'" not in src:
        src = change_once(src, "<a href=\"{% url 'ollama_admin' %}\">Administrar modelos de Ollama →</a>",
                          "<a href=\"{% url 'ollama_admin' %}\">Administrar modelos de Ollama →</a>"
                          "<p><a href=\"{% url 'ai_panel' %}\">Administración de modelos para preguntas y embeddings →</a></p>", path)
    save(path, src)

    # El generador activo reemplaza el modelo hardcodeado antes protegido.
    path = 'frontend/djtesis/tesis/ollama_admin.py'
    src = load(path)
    if 'from .ai_models import AIConfiguration' not in src:
        src = change_once(src, 'from .ollama_api import OLLAMA_BASE_URL, list_models, valid_model_name',
                          'from .ollama_api import OLLAMA_BASE_URL, list_models, valid_model_name\nfrom .ai_models import AIConfiguration', path)
    src = change_once(src, "'protected_model': PROTECTED_QUESTION_MODEL,",
                      "'protected_model': AIConfiguration.current().generation_model,", path) if "'protected_model': PROTECTED_QUESTION_MODEL," in src else src
    if "'protected_models':" not in src:
        src = change_once(src, "'protected_model': AIConfiguration.current().generation_model,",
            "'protected_model': AIConfiguration.current().generation_model,\n        'protected_models': {AIConfiguration.current().generation_model} | ({AIConfiguration.current().embedding_model} if AIConfiguration.current().embedding_provider == 'ollama' else set()),", path)
    src = change_once(src, 'if name == PROTECTED_QUESTION_MODEL:',
                      "if name == AIConfiguration.current().generation_model or (AIConfiguration.current().embedding_provider == 'ollama' and name == AIConfiguration.current().embedding_model):", path) if 'if name == PROTECTED_QUESTION_MODEL:' in src else src
    save(path, src)

    path = 'frontend/djtesis/tesis/templates/tesis/ollama_admin.html'
    src = load(path)
    src = src.replace('model.name == protected_model', 'model.name in protected_models')
    save(path, src)

    # Evitar instanciar el embedding global en el inicio de Flask; revertir subida fallida.
    path = 'backend/eduai-backend.py'
    src = load(path)
    src = src.replace('vsm = VectorStorageManager()\n', '')
    src = change_once(src, '        file.save(file_path)\n        vsm.insert_collection(file_path, username)',
                       '''        manager = VectorStorageManager()\n        with manager.lock():\n            if os.path.exists(file_path):\n                return jsonify({'status': 'error', 'message': 'El archivo ya existe.'}), 409\n            file.save(file_path)\n            try:\n                manager.insert_collection(file_path, username, already_locked=True)\n            except Exception:\n                os.remove(file_path)\n                raise''', path) if 'vsm.insert_collection' in src else src
    src = change_once(src, '        os.remove(file_path)\n        vsm.delete_collection(username, filename)',
                       '        manager = VectorStorageManager()\n        with manager.lock():\n            manager.delete_collection(username, filename, already_locked=True)\n            os.remove(file_path)', path) if 'vsm.delete_collection' in src else src
    save(path, src)

    # Añadir token a Docker Compose SIN reescribir la configuración de recursos de Ollama.
    path = 'compose.yaml'
    src = load(path)
    if 'AI_INTERNAL_TOKEN:' not in src:
        src = change_once(src, '      DJANGO_BASE_URL: http://frontend:8000',
                    '      DJANGO_BASE_URL: http://frontend:8000\n      AI_INTERNAL_TOKEN: ${AI_INTERNAL_TOKEN:?Configura AI_INTERNAL_TOKEN en .env}', path)
        src = change_once(src, '      FLASK_BASE_URL: http://backend:8080',
                    '      FLASK_BASE_URL: http://backend:8080\n      AI_INTERNAL_TOKEN: ${AI_INTERNAL_TOKEN:?Configura AI_INTERNAL_TOKEN en .env}', path)
    if 'ANONYMIZED_TELEMETRY:' not in src:
        src = change_once(src, '      HF_HOME: /app/.cache/huggingface',
                          '      HF_HOME: /app/.cache/huggingface\n      ANONYMIZED_TELEMETRY: \"FALSE\"', path)
    if '\n  ai_worker:' not in src:
        insert = '''\n  ai_worker:\n    build:\n      context: ./backend\n    command: ["python", "ai_worker.py"]\n    restart: unless-stopped\n    environment:\n      DJANGO_BASE_URL: http://frontend:8000\n      AI_INTERNAL_TOKEN: ${AI_INTERNAL_TOKEN:?Configura AI_INTERNAL_TOKEN en .env}\n      OLLAMA_HOST: http://ollama:11434\n      HF_HOME: /app/.cache/huggingface\n      ANONYMIZED_TELEMETRY: \"FALSE\"\n    volumes:\n      - backend_uploads:/app/uploads\n      - backend_vectors:/app/chroma_dbs\n      - hf_cache:/app/.cache/huggingface\n    depends_on:\n      - frontend\n      - ollama\n'''
        if '\nvolumes:' not in src:
            raise RuntimeError('No hay bloque volumes en compose.yaml')
        src = src.replace('\nvolumes:', '\n' + insert + '\nvolumes:', 1)
    save(path, src)
    path = '.env.example'
    src = load(path) if (ROOT / path).exists() else ''
    if 'AI_INTERNAL_TOKEN=' not in src:
        src += '\n# Generar: python3 -c "import secrets;print(secrets.token_urlsafe(48))"\nAI_INTERNAL_TOKEN=REEMPLAZAR_POR_TOKEN_LARGO\n'
    save(path, src)
    path = '.gitignore'
    src = load(path) if (ROOT / path).exists() else ''
    if '.eduai_ai_backup/' not in src:
        src += '\n.eduai_ai_backup/\n'
    if '\n.env\n' not in '\n' + src:
        src += '\n.env\n'
    save(path, src)
    print('\n¡Código instalado! Revisa git diff, agrega AI_INTERNAL_TOKEN a .env, ejecuta migrate y reconstruye frontend/backend/ai_worker.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as exc:
        sys.exit(f'ERROR: {exc}. Restaurar desde {BACKUP} si necesitas revertir.')
