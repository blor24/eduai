# EduAI — etapa 3: Banco de preguntas y exámenes reutilizables

## Alcance

Este parche integra un **banco privado de preguntas por usuario** con las cuatro modalidades de pregunta de EduAI (`multiple`, `corta`, `espacio`, `emparejar`), búsqueda y filtros, edición, borrado, clasificación por **tema, dificultad y documento**, e importación explícita de preguntas de la pantalla **Examen**. Permite seleccionar preguntas del banco para guardar un **examen reutilizable**, que se inicia sin llamar a Ollama ni a Flask. Se utiliza la pantalla y calificación de exámenes que ya existen.

Cada examen guardado conserva **copias JSON** de las preguntas al momento de crearlo. Si el estudiante edita o elimina la pregunta original, el examen guardado no cambia. Borrar el documento original deja las preguntas sin el vínculo con el archivo; no elimina el banco.

**No realiza migraciones de ChromaDB ni cambia el LLM.** No necesita nuevas dependencias de Python. El módulo se implementa íntegramente en Django, manteniendo Flask intacto.

## Instalación

1. Realiza un respaldo de la base de datos de Django, de tus archivos y volúmenes. Desde la raíz `eduai/`:

```bash
git add .
git commit -m "Backup: antes del banco de preguntas"
```

2. Descomprime el archivo ZIP **en la raíz `eduai/`** y ejecuta el instalador:

```bash
unzip ~/Downloads/eduai_banco_preguntas_kit.zip -d .
python3 eduai_banco_preguntas_kit/instalar.py
git diff
```

El instalador comprueba puntos de integración y crea copias de respaldo en `.eduai_banco_backup/`. Es idempotente. Si el código del proyecto difiere de lo esperado, detendrá la instalación sin modificar archivos: **no fuerces reemplazos**.

3. Construye el frontend con los modelos nuevos:

```bash
docker compose build frontend
```

4. Genera la migración Django **en tu carpeta local**, no solamente dentro de la imagen:

```bash
docker compose run --rm --no-deps \
  -v "$PWD/frontend/djtesis/tesis/migrations:/app/tesis/migrations" \
  frontend python manage.py makemigrations tesis --name banco_preguntas
```

Revisa que el archivo generado `frontend/djtesis/tesis/migrations/00XX_banco_preguntas.py` incluya la creación de `BancoPregunta`, `ExamenGuardado` y `ExamenGuardadoItem` y su restricción de orden. Dependiendo de tus migraciones anteriores, puede haber pequeños cambios de campos pendientes. **No apliques eliminaciones o cambios inesperados** sin revisarlos.

5. Reconstruye con la migración generada y aplícala:

```bash
docker compose up -d --build frontend
docker compose exec frontend python manage.py migrate
docker compose exec frontend python manage.py check
docker compose exec frontend python manage.py makemigrations --check --dry-run
```

No uses `docker compose down -v`. No necesitas reiniciar Ollama, backend Flask ni `ai_worker`.

## Rutas de usuario

- `http://localhost:8000/dashboard/banco/` — explorar y filtrar preguntas.
- `/dashboard/banco/nueva/` — crear una pregunta manual.
- `/dashboard/banco/examenes/` — exámenes guardados.
- `/dashboard/banco/examenes/crear/` — crear un examen seleccionando preguntas.
- `/dashboard/examen` — sigue generando y calificando exámenes, ahora con botón **Guardar preguntas en mi banco** cuando se han generado preguntas nuevas.

Se agrega un enlace **Banco de preguntas** en la navegación principal (móvil y escritorio), y un enlace desde la pantalla de exámenes.

## Pruebas funcionales

1. Inicia sesión como un usuario normal y genera 2 preguntas de selección múltiple, 2 de respuesta corta, 2 de completar y 1 ejercicio de emparejar. Confirma el resultado visible.
2. Antes de enviar el examen, introduce un tema y selecciona dificultad. Haz clic en **Guardar preguntas en mi banco**. Deberías ver las preguntas en `/dashboard/banco/`. La acción solo puede ejecutarse una vez por examen generado activo.
3. Edita una pregunta y comprueba validaciones: múltiple requiere exactamente 4 opciones distintas y una respuesta que coincida; completar requiere `___`; corta y completar requieren respuesta de una sola palabra; emparejar requiere entre 1 y 40 pares únicos.
4. Filtra por tipo, dificultad, tema y documento. Prueba crear otra pregunta manualmente.
5. Selecciona preguntas en **Crear examen reutilizable** y guárdalo. Ábrelo e inicia el examen. No debería aparecer una petición nueva de generación en los logs de Flask ni necesitar que Ollama esté generando preguntas.
6. Responde el examen; debería aparecer la pantalla de resultados y registrarse la estadística como antes.
7. Edita o elimina una de las preguntas originales; vuelve a abrir el examen guardado y verifica que mantiene el contenido inicial.
8. Accede desde una cuenta distinta e intenta abrir una URL de edición o un examen de otro usuario: debe devolver 404. Las acciones de edición/eliminación importación/práctica requieren POST+CSRF.

**Limitación de esta etapa:** la importación automática está integrada en `dashboard/examen`, donde el resultado está estructurado como JSON. Los PDF/DOCX exportados desde `dashboard/generar` no se importan automáticamente porque ese endpoint devuelve un ZIP, no el JSON de preguntas. El banco y los exámenes guardados tampoco registran aún intentos de examen individualizados (se mantiene la estadística actual). Cuando pasemos a evaluación y optimización, podremos contemplar su ampliación.

## Diagnóstico

```bash
docker compose logs --tail=100 frontend
docker compose exec frontend python manage.py shell -c \
  "from tesis.models import BancoPregunta,ExamenGuardado,ExamenGuardadoItem; print(BancoPregunta.objects.count())"
```

Si aparece `no such table`, revisa primero la migración. Si una pregunta generada no puede importarse, el formulario mostrará un mensaje y deshará la importación parcial. Los modelos y los datos de ChromaDB permanecen intactos.

## Pruebas de lógica incluidas

```bash
python3 -m unittest discover -s eduai_banco_preguntas_kit/tests -v
```

Estas pruebas validan transformaciones de preguntas, selección múltiple, emparejamiento y errores de formato. También se verifica la sintaxis de los archivos, los puntos de integración y la idempotencia del instalador **contra una copia local del proyecto de referencia**. No se ha ejecutado la integración completa con Docker ni las migraciones sobre tu base de datos real.
