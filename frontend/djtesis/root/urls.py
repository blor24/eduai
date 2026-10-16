"""
URL configuration for root project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from tesis import ollama_admin
from tesis import ai_control
from tesis import views 
from tesis import banco_views
from tesis import document_views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/ia/', admin.site.admin_view(ai_control.panel), name='ai_panel'),
    path('admin/ia/generator/', admin.site.admin_view(ai_control.set_generator), name='ai_set_generator'),
    path('admin/ia/jobs/', admin.site.admin_view(ai_control.queue_job), name='ai_queue_job'),
    path('internal/ai/config/', ai_control.internal_config, name='ai_internal_config'),
    path('internal/ai/jobs/claim/', ai_control.claim_job, name='ai_job_claim'),
    path('internal/ai/tests/', ai_control.internal_testcases, name='ai_internal_tests'),
    path('internal/ai/jobs/<int:job_id>/report/', ai_control.report_job, name='ai_job_report'),
    path('admin/ollama/', admin.site.admin_view(ollama_admin.panel), name='ollama_admin'),
    path('admin/ollama/pull/', admin.site.admin_view(ollama_admin.pull_model), name='ollama_pull'),
    path('admin/ollama/delete/', admin.site.admin_view(ollama_admin.delete_model), name='ollama_delete'),
    path('admin/', admin.site.urls),
    path('recuperar-contrasena/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
    ), name='password_reset'),
    path('recuperar-contrasena/enviado/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('recuperar-contrasena/confirmar/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
    ), name='password_reset_confirm'),
    path('recuperar-contrasena/completo/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('', views.index, name='index'),
    path('logout', views.logout_user, name='logout'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('dashboard/chat/models/', views.available_ollama_models, name='chat_models'),
    path('dashboard/chat', views.chat, name='chat'),
    path('dashboard/chat/save_mensaje/', views.save_mensaje, name='mensaje'),
    path('dashboard/banco/', banco_views.banco, name='banco_lista'),
    path('dashboard/banco/nueva/', banco_views.pregunta_editar, name='banco_nueva'),
    path('dashboard/banco/<int:pk>/editar/', banco_views.pregunta_editar, name='banco_editar'),
    path('dashboard/banco/<int:pk>/eliminar/', banco_views.pregunta_eliminar, name='banco_eliminar'),
    path('dashboard/banco/importar/', banco_views.importar_generadas, name='banco_importar'),
    path('dashboard/banco/examenes/', banco_views.examenes_guardados, name='banco_examenes'),
    path('dashboard/banco/examenes/crear/', banco_views.examen_crear, name='banco_crear_examen'),
    path('dashboard/banco/examenes/<int:pk>/', banco_views.examen_detalle, name='banco_detalle_examen'),
    path('dashboard/banco/examenes/<int:pk>/practicar/', banco_views.examen_practicar, name='banco_practicar_examen'),
    path('dashboard/banco/examenes/<int:pk>/eliminar/', banco_views.examen_eliminar, name='banco_eliminar_examen'),
    path('dashboard/ayuda/', views.ayuda, name='ayuda'),
    path('dashboard/examen', views.examen, name='examen'),
    path('dashboard/generar', views.generar, name='generar'),
    path('dashboard/archivos', views.archivos, name='archivos'),
    path('dashboard/archivos/estado/', document_views.document_status, name='archivo_estado'),
    path('dashboard/archivos/<int:file_id>/ver/', document_views.document_preview, name='archivo_vista'),
    path('dashboard/chat/documents/', document_views.chat_documents, name='chat_documents'),
    path('dashboard/cuenta', views.cuenta, name='cuenta'),
    path('dashboard/resultados', views.resultados, name='resultados'),
    path('track-session/', views.track_session, name='track_session')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
