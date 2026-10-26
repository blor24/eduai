"""Estado único de modelos; los índices viejos permanecen accesibles hasta una migración exitosa."""
from django.db import models
from django.utils import timezone

# Recomendaciones para el selector de Hugging Face, no una lista obligatoria.
# El administrador puede indicar otros repositorios compatibles.
HF_MODELS = (
    'sentence-transformers/all-MiniLM-L12-v2',
    'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    'intfloat/multilingual-e5-small',
    'intfloat/multilingual-e5-base',
)
PROVIDERS = (('hf', 'Hugging Face'), ('ollama', 'Ollama'))


class AIConfiguration(models.Model):
    """Singleton pk=1. El índice legacy usa la colección de Chroma original."""
    generation_model = models.CharField(max_length=180, default='gemma3:4b')
    embedding_provider = models.CharField(max_length=10, choices=PROVIDERS, default='hf')
    embedding_model = models.CharField(max_length=200, default=HF_MODELS[0])
    index_version = models.CharField(max_length=24, default='legacy')
    num_ctx = models.PositiveIntegerField(default=4096)
    num_predict = models.PositiveIntegerField(default=1024)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Configuración activa de EduAI'


class AIJob(models.Model):
    TYPES = (('reindex', 'Reindexar documentos'), ('download', 'Descargar Hugging Face'),
             ('delete', 'Eliminar caché Hugging Face'), ('benchmark', 'Evaluar índice activo'))
    STATES = (('queued', 'En cola'), ('running', 'Ejecutándose'),
              ('success', 'Completado'), ('failed', 'Error'))
    kind = models.CharField(max_length=12, choices=TYPES)
    provider = models.CharField(max_length=10, choices=PROVIDERS, default='hf')
    model_name = models.CharField(max_length=200)
    target_version = models.CharField(max_length=24, blank=True)
    status = models.CharField(max_length=10, choices=STATES, default='queued', db_index=True)
    progress = models.CharField(max_length=250, blank=True)
    error = models.TextField(blank=True)
    submitted_by = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.get_kind_display()} {self.model_name} ({self.status})'


class AITestCase(models.Model):
    """Consulta de prueba con archivo fuente conocido; sin almacenar información confidencial en logs."""
    username = models.CharField(max_length=150)
    query = models.TextField()
    expected_filename = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.username}: {self.query[:55]}'
