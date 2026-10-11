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
from django.urls import path
from tesis import views 
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', views.index, name='index'),
    path('logout', views.logout_user, name='logout'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('dashboard/chat', views.chat, name='chat'),
    path('dashboard/chat/save_mensaje/', views.save_mensaje, name='mensaje'),
    path('dashboard/examen', views.examen, name='examen'),
    path('dashboard/generar', views.generar, name='generar'),
    path('dashboard/archivos', views.archivos, name='archivos'),
    path('dashboard/cuenta', views.cuenta, name='cuenta'),
    path('dashboard/resultados', views.resultados, name='resultados'),
    path('track-session/', views.track_session, name='track_session')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
