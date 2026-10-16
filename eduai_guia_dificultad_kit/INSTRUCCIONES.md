# EduAI — Guía de uso + dificultad para generar preguntas

Kit incremental para la versión de EduAI que ya tiene instaladas las etapas de **administración de modelos IA**, **OpenDocument**, **gestión documental**, **fuentes del chat** y **banco de preguntas**.

## Incluye

1. Nueva ruta autenticada `/dashboard/ayuda/` y acceso desde la navegación móvil y de escritorio.
2. Centro de ayuda en español: primeros pasos, formatos compatibles, índice activo, chat y fuentes, exámenes, banco, resultados y preguntas frecuentes.
3. Enlaces contextuales junto a **Índice activo**, selección de documentos y fuentes.
4. Selector de dificultad **Básica, Intermedia, Avanzada o Mixta** en Examen y Generar preguntas (PDF/DOCX).
5. Instrucciones de complejidad añadidas a los prompts para los cuatro tipos de preguntas; no cambia el esquema JSON requerido.
6. En la modalidad mixta distribuye cantidades entre tres niveles cuando genera preguntas individuales; emparejamiento es un ejercicio con los pares solicitados e instrucciones de complejidad variada.
7. El banco guarda por separado la **dificultad solicitada** y la **clasificación de cada pregunta**, que el usuario puede editar. No se presenta como evaluación automática de calidad.

**Nota:** La dificultad solicitada no garantiza que el LLM efectivamente genere un nivel cognitivo determinado. Hay que comprobar las preguntas antes de utilizarlas.

## Instalación

Desde la raíz de tu repositorio `eduai/`:

```bash
cd ~/Documents/tesis-v2/eduai

git status
git add .
git commit -m "Backup antes de añadir ayuda y dificultad"

unzip ~/Downloads/eduai_guia_dificultad_kit.zip -d .
python3 eduai_guia_dificultad_kit/instalar.py

git diff
git status
```

El instalador no ejecuta Docker ni altera la base de datos. Comprueba los puntos de modificación antes de escribir, realiza copias de los archivos originales en `.eduai_guia_backup/` y puede ejecutarse nuevamente sin duplicar sus cambios. Si el código se apartó de las versiones usadas para preparar el parche, se detendrá sin modificar archivos.

### Migración de Django

Esta etapa **añade un campo** a `BancoPregunta` para guardar la dificultad solicitada. Genera la migración con la versión de Django del contenedor, escribiéndola en la carpeta del equipo:

```bash
docker compose build frontend backend

docker compose run --rm --no-deps \
  -v "$PWD/frontend/djtesis/tesis/migrations:/app/tesis/migrations" \
  frontend python manage.py makemigrations tesis --name dificultad_solicitada
```

**Revisa el archivo generado** antes de migrar. Debe agregar `dificultad_solicitada` a `BancoPregunta`; no debería eliminar modelos, datos o columnas existentes. En preguntas antiguas y creadas manualmente se inicializa a `intermedia`, porque no conocemos el nivel solicitado durante su generación.

```bash
docker compose up -d --build frontend backend

docker compose exec frontend python manage.py migrate
docker compose exec frontend python manage.py check
docker compose exec frontend python manage.py makemigrations --check --dry-run
```

No hace falta reconstruir `ai_worker` u Ollama, porque no modificamos su código. **Nunca utilices `docker compose down -v` para esta instalación.**

### Si necesitas devolver los cambios

Puedes revertir el commit mediante Git o consultar los originales en `.eduai_guia_backup/`. Si ya aplicaste la migración, planifica cuidadosamente su reversión: la eliminación del campo perdería sus datos. No elimines volúmenes.

## Pruebas manuales

1. Accede como usuario a `http://localhost:8000/dashboard/ayuda/`: revisa enlaces, anclas, FAQs y las dos barras laterales (móvil y escritorio).
2. En Archivos, pulsa el signo de interrogación de **Índice activo**. En Chat, verifica la ayuda de selección y fuentes.
3. Genera 3 preguntas de selección múltiple con dificultad `basica` y luego `avanzada` usando el mismo documento; revisa si las preguntas difieren sin asumir que el nivel solicitado sea siempre correcto.
4. Genera 7 preguntas de respuesta corta con `mixta`. El backend las reparte 3 básicas, 2 intermedias y 2 avanzadas (puedes comprobar las etiquetas al guardarlas).
5. Guarda las preguntas en el banco: debe aparecer la dificultad solicitada y la clasificación individual; edita esta última si es necesario.
6. Verifica emparejamiento con 4 pares y `mixta` (es un ejercicio con 4 pares).
7. En Generar preguntas, descarga PDF y DOCX usando dificultad avanzada y revisa el contenido.
8. Regresión: carga documental, chat con citas, examen existente y examen guardado deben continuar funcionando.

Logs útiles:

```bash
docker compose logs --tail=100 frontend backend
docker compose exec frontend python manage.py check
```

## Validación del kit

Se reconstruyó la versión integrada a partir de los ZIP originales y parches previos, y se aplicó este instalador. Se validó la sintaxis Python, la idempotencia y la distribución de la modalidad mixta mediante pruebas automatizadas. **No se ha ejecutado en tus contenedores reales**, así que confirma los puntos anteriores antes de considerar cerrada la etapa.
