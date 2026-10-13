#!/usr/bin/env python3
"""Añade recuperación de contraseña y Django Admin sin sobrescribir otros cambios de EduAI.

Ubicación: eduai/eduai_auth_admin_kit/instalar.py
Ejecución: python3 eduai_auth_admin_kit/instalar.py
"""
from pathlib import Path
import re
import sys

KIT = Path(__file__).resolve().parent
ROOT = KIT.parent
DJANGO = ROOT / 'frontend' / 'djtesis'
if not (DJANGO / 'manage.py').is_file() or not (ROOT / 'compose.yaml').exists():
    sys.exit('ERROR: Descomprime el kit en la raíz de eduai (junto a compose.yaml) antes de ejecutarlo.')

changes = {}

def load(name):
    p = ROOT / name
    if not p.is_file():
        sys.exit(f'ERROR: No se encuentra {name}')
    return p.read_text(encoding='utf-8')

def replace_once(name, old, new, optional_if=None):
    text = changes.get(name, load(name))
    if optional_if and optional_if in text:
        return
    if text.count(old) != 1:
        sys.exit(f'ERROR: No se encontró un punto de modificación único en {name}: {old[:80]!r}.\n'
                 'Los archivos parecen haber cambiado. No se aplicó ningún cambio.')
    changes[name] = text.replace(old, new, 1)

urls = 'frontend/djtesis/root/urls.py'
replace_once(urls, 'from django.contrib import admin\n',
    'from django.contrib import admin\nfrom django.contrib.auth import views as auth_views\n',
    optional_if='from django.contrib.auth import views as auth_views')

url_items = '''    path('admin/', admin.site.urls),
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
'''
replace_once(urls, 'urlpatterns = [\n', 'urlpatterns = [\n' + url_items,
    optional_if="name='password_reset_complete'")

admin = 'frontend/djtesis/tesis/admin.py'
admin_snippet = '''
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
'''
text = changes.get(admin, load(admin))
if '@admin.register(Archivo)' not in text and '@admin.register(Estadistica)' not in text and '@admin.register(Mensaje)' not in text:
    changes[admin] = text.rstrip() + '\n' + admin_snippet
elif not all(x in text for x in ['@admin.register(Archivo)', '@admin.register(Estadistica)', '@admin.register(Mensaje)']):
    sys.exit('ERROR: admin.py tiene registros parciales; revisa antes de instalar. No se aplicó ningún cambio.')

forms = 'frontend/djtesis/tesis/forms.py'
old_form = '''class CrearUserForm(UserCreationForm):
    class Meta:
       model = User
       fields = ['username', 'email', 'password1', 'password2']'''
new_form = '''class CrearUserForm(UserCreationForm):
    # El correo es obligatorio para recuperar la contraseña.
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este correo electrónico ya está registrado.')
        return email
'''
replace_once(forms, old_form, new_form, optional_if='def clean_email(self):')

# Soluciona un bug previo: "receiver" es un TextField, no un objeto User.
models = 'frontend/djtesis/tesis/models.py'
replace_once(models,
    '''return f"Message from {self.sender.username} to {self.receiver.username if self.receiver else 'Unknown'}"''',
    '''return f"Mensaje de {self.sender.username} a {self.receiver or 'asistente'}"''',
    optional_if='return f"Mensaje de {self.sender.username} a {self.receiver or')

views = 'frontend/djtesis/tesis/views.py'
replace_once(views,
    """            else:
                messages.warning(request, "Creación fallida. Revise los datos ingresados.")
                return redirect('index')""",
    """            else:
                # Conserva los errores del formulario para mostrarlos al usuario.
                messages.warning(request, "Creación fallida. Revise los datos ingresados.")""",
    optional_if='Conserva los errores del formulario para mostrarlos al usuario.')

index = 'frontend/djtesis/tesis/templates/tesis/index.html'
replace_once(index,
    '                            {{ login_form.password }}',
    '''                            {{ login_form.password }}
                            <div class="text-end mt-2 mb-3">
                                <a href="{% url 'password_reset' %}">¿Olvidaste tu contraseña?</a>
                            </div>''',
    optional_if="{% url 'password_reset' %}")

replace_once(index,
    """                    <form method="POST" autocomplete="off" name="registro">""",
    """                    {% if register_form.errors %}
                    <div class="alert alert-danger" role="alert">
                        {% for field in register_form %}
                            {% for error in field.errors %}
                                <div><strong>{{ field.label }}:</strong> {{ error }}</div>
                            {% endfor %}
                        {% endfor %}
                        {% for error in register_form.non_field_errors %}<div>{{ error }}</div>{% endfor %}
                    </div>
                    {% endif %}
                    <form method="POST" autocomplete="off" name="registro">""",
    optional_if='{% if register_form.errors %}')
replace_once(index,
    """    <script>
        function togglePassword() {""",
    """    {% if register_form.errors %}
    <script>
        document.addEventListener('DOMContentLoaded', function () {
            bootstrap.Modal.getOrCreateInstance(document.getElementById('registerModal')).show();
        });
    </script>
    {% endif %}
    <script>
        function togglePassword() {""",
    optional_if="bootstrap.Modal.getOrCreateInstance(document.getElementById('registerModal'))")

base = 'frontend/djtesis/tesis/templates/tesis/base.html'
text = changes.get(base, load(base))
if "{% url 'admin:index' %}" not in text:
    link = '''          {% if request.user.is_staff %}
          <li class="nav-item">
            <a class="nav-link" href="{% url 'admin:index' %}">
              <i class="bi bi-shield-lock"></i> Administración
            </a>
          </li>
          {% endif %}
'''
    pattern = r'(<ul class="nav nav-(?:pills|underline) flex-column">)(.*?)(\s*</ul>)'
    def add_admin_link(match):
        return match.group(1) + match.group(2) + '\n' + link + match.group(3)
    text, count = re.subn(pattern, add_admin_link, text, flags=re.S)
    if count != 2:
        sys.exit(f'ERROR: se esperaban 2 menús en base.html; encontrados {count}. No se aplicó ningún cambio.')
    changes[base] = text

settings = 'frontend/djtesis/root/settings.py'
text = changes.get(settings, load(settings))
if 'import os\n' not in text:
    replace_once(settings, 'from pathlib import Path\n', 'from pathlib import Path\nimport os\n')
email_settings = '''
# Recuperación de contraseña: correo en la consola durante desarrollo.
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '0') == '1'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', '0') == '1'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'EduAI <no-reply@localhost>')
PASSWORD_RESET_TIMEOUT = 3600  # 1 hora
'''
replace_once(settings, "MEDIA_ROOT = BASE_DIR / 'media'", "MEDIA_ROOT = BASE_DIR / 'media'\n" + email_settings,
    optional_if='PASSWORD_RESET_TIMEOUT = 3600')

compose = 'compose.yaml'
compose_email = '''      EMAIL_BACKEND: ${EMAIL_BACKEND:-django.core.mail.backends.console.EmailBackend}
      EMAIL_HOST: ${EMAIL_HOST:-}
      EMAIL_PORT: ${EMAIL_PORT:-587}
      EMAIL_HOST_USER: ${EMAIL_HOST_USER:-}
      EMAIL_HOST_PASSWORD: ${EMAIL_HOST_PASSWORD:-}
      EMAIL_USE_TLS: ${EMAIL_USE_TLS:-0}
      EMAIL_USE_SSL: ${EMAIL_USE_SSL:-0}
      DEFAULT_FROM_EMAIL: ${DEFAULT_FROM_EMAIL:-no-reply@localhost}
'''
replace_once(compose, '      FLASK_BASE_URL: http://backend:8080\n',
             '      FLASK_BASE_URL: http://backend:8080\n' + compose_email,
             optional_if='      EMAIL_BACKEND: ${EMAIL_BACKEND')

envexample = '.env.example'
email_example = '''
# Pruebas: el enlace de recuperación aparecerá en docker compose logs frontend.
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# Para enviar correo real, cambia EMAIL_BACKEND a:
# django.core.mail.backends.smtp.EmailBackend
# y configura tu proveedor SMTP en .env (nunca subas ese archivo a Git).
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=0
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=no-reply@localhost
'''
text = changes.get(envexample, load(envexample))
if '\nEMAIL_BACKEND=' not in text:
    changes[envexample] = text.rstrip() + '\n' + email_example

# Preparar templates sin sobreescribir ediciones previas.
template_src = KIT / 'plantillas' / 'registration'
template_dst = DJANGO / 'tesis' / 'templates' / 'registration'
new_templates = {}
for src in template_src.iterdir():
    dest = template_dst / src.name
    if dest.exists():
        if dest.read_bytes() != src.read_bytes():
            sys.exit(f'ERROR: {dest} ya existe y es diferente; no se sobrescribirá. No se aplicó ningún cambio.')
    else:
        new_templates[dest] = src.read_bytes()

# Escritura sólo si se validaron todas las modificaciones.
for name, content in changes.items():
    target = ROOT / name
    target.write_text(content, encoding='utf-8')
    print('Actualizado:', name)
for target, data in new_templates.items():
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print('Creado:', target.relative_to(ROOT))
print('\nListo. Revisa los cambios con: git diff && git status')
print('Después ejecuta: docker compose up -d --build frontend')
