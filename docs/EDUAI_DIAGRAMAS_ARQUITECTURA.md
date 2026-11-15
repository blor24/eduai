# Diagramas de arquitectura y funcionamiento de EduAI

> Diagramas en **Mermaid** para visualizar directamente en archivos Markdown (`.md`) compatibles con GitHub. Representan la arquitectura funcional y el despliegue descritos en la documentación del proyecto. Los nombres exactos de volúmenes, redes y algunas rutas internas deben contrastarse con los archivos `compose.yaml`, `compose.gpu.yaml`, `compose.prod.yaml` y la configuración vigente de Nginx.

## 1. Arquitectura del proyecto

Este diagrama presenta las capas de interfaz, lógica de aplicación, procesamiento de inteligencia artificial y almacenamiento. **ChromaDB** es el índice vectorial persistente utilizado por los procesos de IA; no se representa necesariamente como un contenedor independiente.

```mermaid
flowchart TB
    U["Docente / estudiante<br/>Navegador web"]
    N["Nginx<br/>HTTPS y proxy inverso"]

    subgraph APP["Capa de aplicación"]
        D["Django<br/>Interfaz, autenticación,<br/>archivos y estadísticas"]
        F["Flask + Socket.IO<br/>Chat RAG y generación<br/>de preguntas / exámenes"]
        W["AI Worker<br/>Procesamiento de trabajos"]
    end

    subgraph AI["Capa de inteligencia artificial"]
        E["Hugging Face / SentenceTransformers<br/>Embeddings"]
        L["Ollama<br/>Modelos de lenguaje locales"]
    end

    subgraph DATA["Persistencia"]
        P[("PostgreSQL<br/>Usuarios, registros y estadísticas")]
        C[("ChromaDB<br/>Índices vectoriales por usuario")]
        A[("Archivos cargados<br/>PDF, DOC, DOCX, PPTX, TXT")]
    end

    U -->|"HTTPS"| N
    N -->|"Páginas y API web"| D
    N -->|"Conexión Socket.IO"| F
    D <-->|"API HTTP interna / configuración"| F
    W <-->|"Obtención y actualización de trabajos"| D
    D <-->|"Datos de la aplicación"| P
    D -->|"Administración de archivos"| A
    F -->|"Lectura de documentos"| A
    F -->|"Recuperación RAG"| C
    F -->|"Vectorización de consultas"| E
    W -->|"Procesamiento documental"| E
    E -->|"Vectores"| C
    F -->|"Inferencia"| L
    W -->|"Tareas de IA, según trabajo"| L
```

## 2. Cómo funciona la aplicación

Este flujo describe las tres operaciones centrales: cargar e indexar documentos, conversar con un documento mediante recuperación aumentada (RAG), y generar actividades o exámenes. La aplicación también puede registrar resultados y ofrecer exportaciones según la funcionalidad utilizada.

```mermaid
flowchart TD
    IN(["Usuario ingresa a EduAI"])
    LOGIN["Iniciar sesión en Django"]
    DASH["Acceder al panel"]
    OP{"¿Qué desea realizar?"}

    IN --> LOGIN --> DASH --> OP

    subgraph DOC["A. Gestión documental"]
        UP["Cargar archivo compatible"]
        TEXT["Extraer y dividir contenido en fragmentos"]
        VECT["Generar embeddings"]
        INDEX[("Guardar índice en ChromaDB<br/>asociado al usuario")]
        READY["Documento disponible para consulta"]
        UP --> TEXT --> VECT --> INDEX --> READY
    end

    subgraph CHAT["B. Chat con documentos (RAG)"]
        SCOPE["Elegir documentos autorizados"]
        ASK["Enviar pregunta mediante Socket.IO"]
        SEARCH["Buscar fragmentos relevantes en ChromaDB"]
        CONTEXT["Construir solicitud con contexto"]
        ANSWER["Generar respuesta con Ollama"]
        SHOW["Mostrar respuesta al usuario"]
        SCOPE --> ASK --> SEARCH --> CONTEXT --> ANSWER --> SHOW
    end

    subgraph EXAM["C. Generación de exámenes"]
        CFG["Seleccionar documento, tipo,<br/>cantidad y dificultad"]
        CONTENT["Recuperar contenido relevante"]
        GEN["Generar preguntas mediante IA"]
        VALID["Validar estructura y preparar actividad"]
        RESULT["Presentar examen, resultados<br/>y exportación si aplica"]
        CFG --> CONTENT --> GEN --> VALID --> RESULT
    end

    OP -->|"Cargar documentos"| UP
    OP -->|"Consultar mediante chat"| SCOPE
    OP -->|"Crear examen"| CFG
    READY -.->|"Disponible para selección"| SCOPE
    READY -.->|"Fuente de contenido"| CFG
```

## 3. Despliegue en el servidor con GPU

La aplicación se expone en **`https://app.eduai.work.gd`** mediante Nginx y HTTPS. La pila utiliza Docker Compose con archivos base, GPU y producción. La aceleración se proporciona mediante la **NVIDIA RTX A6000**; el uso efectivo de CUDA depende de los permisos del contenedor, el runtime y el dispositivo configurado para cada proceso.

```mermaid
flowchart TB
    CLIENT["Usuarios<br/>Internet"]
    DNS["DNS<br/>app.eduai.work.gd"]
    CLIENT --> DNS

    subgraph HOST["Servidor Ubuntu Linux<br/>AMD EPYC 7763 · 58 GiB RAM"]
        NG["Nginx en el host<br/>TLS / HTTPS :443"]

        subgraph DOCKER["Docker Compose<br/>compose.yaml + compose.gpu.yaml + compose.prod.yaml"]
            WEB["frontend<br/>Django / Gunicorn :8000"]
            API["backend<br/>Flask / Socket.IO :8080"]
            WORKER["ai_worker<br/>Trabajos de IA"]
            OLL["ollama<br/>Servicio de modelos LLM"]
            EMB["Biblioteca de embeddings<br/>en backend / ai_worker"]
        end

        subgraph DATA_HOST["Persistencia configurada en el despliegue"]
            PG[("PostgreSQL<br/>Datos persistentes")]
            CHROMA[("ChromaDB<br/>Índice persistente")]
            FILES[("Archivos y datos<br/>persistentes")]
        end

        GPU["NVIDIA RTX A6000<br/>≈48 GiB VRAM<br/>Driver 570.195.03"]
    end

    DNS --> NG
    NG -->|"/ y rutas web"| WEB
    NG -->|"/socket.io/"| API
    WEB <-->|"API HTTP interna"| API
    WEB <-->|"Gestión de trabajos"| WORKER
    WEB <-->|"SQL"| PG
    WEB --> FILES
    API --> FILES
    API <--> CHROMA
    WORKER --> EMB
    API --> EMB
    EMB --> CHROMA
    API -->|"Generación de texto"| OLL
    WORKER -.->|"Según trabajo"| OLL
    GPU -.->|"CUDA / acceso GPU"| OLL
    GPU -.->|"CUDA si está habilitado"| EMB
```

### Notas para el README

- **Servicios de la aplicación:** `frontend` (Django), `backend` (Flask y Socket.IO), `ai_worker` y `ollama`.
- **Datos:** PostgreSQL almacena registros de aplicación; ChromaDB persiste vectores para búsqueda semántica, y los archivos cargados se conservan en almacenamiento persistente.
- **Proxy y seguridad:** Nginx termina HTTPS y enruta el tráfico hacia los componentes correspondientes.
- **GPU:** NVIDIA RTX A6000 (aprox. 48 GiB de memoria gráfica). El comando `nvidia-smi` mostraba CUDA 12.8 como versión admitida por el controlador, no necesariamente la versión del toolkit instalada en cada contenedor.
- **Alcance:** diagramas de alto nivel. La ubicación exacta de PostgreSQL y los montajes de ChromaDB/archivos debe validarse con la configuración desplegada; no implican que cada componente de persistencia sea un contenedor separado.
