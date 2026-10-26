# Guía integrada de administración (EduAI)

La ayuda para administradores está disponible en `http://localhost:8000/admin/guia/`.

## Funciones incluidas

- Acceso directo desde la portada de Django Admin.
- Enlaces de ayuda contextual en «Modelos de Ollama» y «Administración de IA».
- Explicaciones sobre usuarios y permisos, archivos, mensajes, estadísticas, banco de preguntas, modelos de Ollama, generador, embeddings, reindexación, evaluaciones y resolución de problemas.
- La nueva vista usa `admin.site.admin_view`, que restringe el acceso a personal autorizado. Las secciones de IA se muestran solo a superusuarios; los paneles originales conservan sus permisos.

## Aplicación de los cambios

Si utilizas el ZIP de parche, extráelo **desde la raíz del repositorio EduAI**, donde están `frontend/` y `backend/`:

```bash
unzip -o eduai_guia_admin_parche.zip
```

Luego reconstruye **solo** el frontend:

```bash
docker compose up -d --build frontend
```

Accede a `http://localhost:8000/admin/`, inicia sesión como administrador y pulsa «Consultar la guía de uso del administrador». No es necesario modificar el backend ni crear migraciones.

## Pruebas

```bash
docker compose exec frontend python manage.py check
docker compose exec frontend python manage.py test tesis.test_admin_guide
```

Las pruebas cubren acceso bloqueado para usuarios normales, acceso de personal autorizado, contenido para superusuarios y enlace en la página inicial del administrador.

## Alcance

Los cambios son exclusivamente de interfaz/documentación y una ruta GET de solo lectura. No modifican modelos, migraciones, trabajos de IA ni datos guardados.
