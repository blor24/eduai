from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('tesis', '0014_alter_estadistica_puntaje_and_more'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(name='AIConfiguration', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('generation_model', models.CharField(default='gemma3:4b', max_length=180)),
            ('embedding_provider', models.CharField(choices=[('hf', 'Hugging Face'), ('ollama', 'Ollama')], default='hf', max_length=10)),
            ('embedding_model', models.CharField(default='sentence-transformers/all-MiniLM-L12-v2', max_length=200)),
            ('index_version', models.CharField(default='legacy', max_length=24)),
            ('num_ctx', models.PositiveIntegerField(default=4096)),
            ('num_predict', models.PositiveIntegerField(default=1024)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name='AIJob', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('kind', models.CharField(choices=[('reindex', 'Reindexar documentos'), ('download', 'Descargar Hugging Face'), ('delete', 'Eliminar caché Hugging Face'), ('benchmark', 'Evaluar índice activo')], max_length=12)),
            ('provider', models.CharField(choices=[('hf', 'Hugging Face'), ('ollama', 'Ollama')], default='hf', max_length=10)),
            ('model_name', models.CharField(max_length=200)),
            ('target_version', models.CharField(blank=True, max_length=24)),
            ('status', models.CharField(choices=[('queued', 'En cola'), ('running', 'Ejecutándose'), ('success', 'Completado'), ('failed', 'Error')], db_index=True, default='queued', max_length=10)),
            ('progress', models.CharField(blank=True, max_length=250)),
            ('error', models.TextField(blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('started_at', models.DateTimeField(blank=True, null=True)),
            ('finished_at', models.DateTimeField(blank=True, null=True)),
            ('submitted_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ('-created_at',)}),
        migrations.CreateModel(name='AITestCase', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('username', models.CharField(max_length=150)),
            ('query', models.TextField()),
            ('expected_filename', models.CharField(max_length=255)),
            ('enabled', models.BooleanField(default=True)),
        ]),
    ]
