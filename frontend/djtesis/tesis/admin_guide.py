"""Guía de administración integrada con los permisos nativos de Django Admin.

La ruta está protegida por admin.site.admin_view desde root/urls.py.
"""
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def guide(request):
    """Muestra ayuda de lectura; las operaciones sensibles conservan sus permisos."""
    return render(request, 'tesis/admin_guide.html', {
        'title': 'Guía de administración de EduAI',
    })
