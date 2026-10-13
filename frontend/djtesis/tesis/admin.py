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
