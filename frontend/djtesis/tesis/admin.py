from django.contrib import admin

# Register your models here.

from .models import Archivo, Estadistica, Mensaje

admin.site.site_header = "Administración de EduAI"
admin.site.site_title = "EduAI Admin"
admin.site.index_title = "Gestión de la plataforma"

@admin.register(Archivo)
class ArchivoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'user', 'tipo', 'fecha_carga')
    list_filter = ('tipo', 'fecha_carga')
    search_fields = ('nombre', 'user__username')
    readonly_fields = ('fecha_carga',)
    list_select_related = ('user',)

@admin.register(Estadistica)
class EstadisticaAdmin(admin.ModelAdmin):
    list_display = ('user', 'puntaje', 'tiempo_estudio', 'tiempo_chat', 'momento_uso')
    list_filter = ('momento_uso',)
    search_fields = ('user__username',)
    readonly_fields = ('momento_uso',)
    list_select_related = ('user',)

@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('sender__username', 'receiver', 'sender_content', 'receiver_response')
    readonly_fields = ('timestamp',)
    list_select_related = ('sender',)

admin.site.index_template = "tesis/admin_index_eduai.html"


from .ai_models import AIConfiguration, AIJob, AITestCase

@admin.register(AIConfiguration)
class AIConfigurationAdmin(admin.ModelAdmin):
    list_display = ('generation_model', 'embedding_provider', 'embedding_model', 'index_version', 'updated_at')
    readonly_fields = ('generation_model', 'embedding_provider', 'embedding_model', 'index_version', 'num_ctx', 'num_predict', 'updated_at')
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(AIJob)
class AIJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'kind', 'model_name', 'status', 'progress', 'created_at')
    list_filter = ('kind', 'status', 'created_at')
    readonly_fields = ('kind', 'provider', 'model_name', 'status', 'progress', 'error', 'target_version', 'submitted_by', 'created_at', 'started_at', 'finished_at')
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(AITestCase)
class AITestCaseAdmin(admin.ModelAdmin):
    list_display = ('username', 'query', 'expected_filename', 'enabled')
    list_filter = ('enabled',)
    search_fields = ('username', 'query', 'expected_filename')
