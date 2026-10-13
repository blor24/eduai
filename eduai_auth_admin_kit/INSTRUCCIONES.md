# EduAI: recuperar contraseña y administración de Django

Este kit es un parche incremental para la estructura de Docker Compose compartida. **No reemplaza el backend Flask, la configuración de Ollama ni tus bases de datos**.

## Instalación

1. Copia `eduai_auth_admin_kit/` dentro de la raíz de tu repositorio, donde está `compose.yaml`.
2. Haz un commit de seguridad o comprueba que `git status` está limpio.
3. Desde la carpeta raíz, ejecuta:

   ```bash
   python3 eduai_auth_admin_kit/instalar.py
   git diff
   docker compose up -d --build frontend
   docker compose exec frontend python manage.py migrate
   docker compose exec frontend python manage.py createsuperuser
   ```

4. Abre `http://localhost:8000/admin/` e inicia sesión con el superusuario.
5. Abre `http://localhost:8000/`, pulsa `Entrar` → `¿Olvidaste tu contraseña?`.

## Recuperación de contraseña: modo de prueba

Por defecto, los mensajes se envían a la **consola del contenedor**, no a un correo externo:

```bash
docker compose logs -f frontend
```

Utiliza el correo que registraste para un usuario activo. Al enviar el formulario, el enlace de recuperación se mostrará en los logs. Cópialo en el navegador y establece una contraseña nueva. El enlace vence en una hora. **No expongas logs que contienen enlaces de recuperación.**

## Configurar SMTP para correo real

Edita el archivo `.env` **local** (no `.env.example`) e incorpora, adaptando a tu proveedor:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.ejemplo.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu-cuenta@ejemplo.com
EMAIL_HOST_PASSWORD=CONTRASENA_DE_APLICACION_O_CREDENCIAL_SMTP
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=tu-cuenta@ejemplo.com
```

Aplica los cambios reiniciando el servicio:

```bash
docker compose up -d --force-recreate frontend
```

En el modo SMTP, los mensajes **sí se envían de verdad**. Revisa también spam y configura el remitente autorizado según tu proveedor. Para producción, utiliza HTTPS, configuración correcta de proxy y un servicio transaccional de correo.

## Notas importantes

- El correo registrado en la cuenta es necesario para restablecer la contraseña. Los usuarios antiguos sin correo deben actualizar su perfil desde el admin.
- El formulario de registro obliga a indicar correo y evita, a nivel de formulario, registros duplicados por correo. Si hay duplicados preexistentes, revísalos en el admin.
- El panel administrador de Django sólo permite acceso a cuentas con `is_staff=True` y permisos adecuados. Un superusuario tiene todos los permisos.
- A usuarios `is_staff` se les presenta un enlace «Administración» en los menús del dashboard.
- La aplicación utiliza todavía `runserver` para desarrollo; antes de exponerla en internet utiliza un despliegue seguro.
- Django Admin ya incluye administración del modelo `User`, por ser parte de `django.contrib.auth`.
- **Conserva tu volumen** `django_data`: no ejecutes `docker compose down -v`, o borrarías los volúmenes y sus datos.
- No se requieren migraciones nuevas del modelo; `migrate` asegura que las tablas de autenticación estén disponibles.
- El script es idempotente para los archivos originales esperados; si tu código difiere, se detiene antes de escribir.

## Archivos modificados

- `frontend/djtesis/root/urls.py`
- `frontend/djtesis/root/settings.py`
- `frontend/djtesis/tesis/admin.py`
- `frontend/djtesis/tesis/forms.py`
- `frontend/djtesis/tesis/views.py` (mantiene los errores del formulario de registro)
- `frontend/djtesis/tesis/models.py` (corrige el `__str__` de `Mensaje`, puesto que `receiver` es texto)
- `frontend/djtesis/tesis/templates/tesis/index.html`
- `frontend/djtesis/tesis/templates/tesis/base.html`
- `frontend/djtesis/tesis/templates/registration/*` (plantillas nuevas)
- `compose.yaml`
- `.env.example`
