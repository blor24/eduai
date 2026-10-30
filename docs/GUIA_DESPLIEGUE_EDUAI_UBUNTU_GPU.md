# Guía de despliegue de EduAI v3 en Ubuntu Server con GPU NVIDIA

**Versión de la guía:** 28 de octubre de 2026  
**Servidor previsto:** Ubuntu Server 24.04 LTS, controlador NVIDIA R570, CUDA 12.8, RTX A6000, Docker Engine y Docker Compose v2.  
**Dominio de producción:** `https://app.eduai.work.gd`  
**Arquitectura:** Nginx en Ubuntu → Django/Gunicorn y Flask/Socket.IO en Docker → PostgreSQL, Ollama, ChromaDB y worker de IA.  
**Parche de producción:** `preparar_eduai_produccion.py`, **en su variante actualizada para `app.eduai.work.gd`**.

> **Alcance y estado:** esta guía reproduce la configuración analizada de `eduaiv3.zip`, los dos parches compartidos y los problemas encontrados durante el despliegue. No implica que todos los comandos se hayan ejecutado con éxito en tu servidor real. Verifica salidas y respalda datos antes de realizar cambios. Los nombres de servicios corresponden a `compose.yaml` de EduAI v3.

## 0. Lo que aprendimos durante el despliegue

1. **No se puede utilizar directamente `eduai.work.gd` con la configuración DNS disponible.** El subdominio elegido es **`app.eduai.work.gd`**. El panel DNS permite completar el campo anterior a `.eduai.work.gd`, por ejemplo `app`, o `*` si solo admite el comodín.
2. **`EDUAI_EMBEDDING_DEVICE=auto` no otorga a Docker acceso a la GPU.** La variable determina qué dispositivo escoger *dentro del proceso* si la GPU ya es visible.
3. **`EDUAI_ACCELERATOR=gpu` tampoco modifica un `docker compose up` convencional.** El iniciador `iniciar_eduai.sh` puede interpretar esa variable, pero en la instalación de producción debe usarse la combinación de **tres archivos**: `compose.yaml`, `compose.gpu.yaml` y `compose.prod.yaml`.
4. **El diagnóstico real recibido fue:**

   ```python
   {
       'requested_device': 'auto',
       'selected_device': 'cpu',
       'cuda_available': False,
       'mps_available': False,
       'pytorch_version': '2.5.1+cu121',
       'gpu_name': None,
       'gpu_total_memory_gib': None,
       'error': None
   }
   ```

   Esto confirma que **PyTorch fue instalado con soporte CUDA 12.1**, pero **el contenedor `backend` no pudo acceder a CUDA** en esa prueba. **No confirma todavía la causa exacta**: hay que distinguir entre el controlador del host, NVIDIA Container Toolkit, la reserva GPU de Compose y la visibilidad efectiva desde el contenedor.
5. **El driver R570 y la etiqueta CUDA 12.8 del host no obligan a instalar PyTorch CUDA 12.8.** El PyTorch `2.5.1+cu121` del parche puede funcionar con un controlador NVIDIA suficientemente reciente, siempre que Docker exponga el dispositivo.
6. **El script `iniciar_eduai.sh` del parche GPU utiliza solo una o dos capas Compose y no incluye `compose.prod.yaml`.** Para este despliegue público con Gunicorn/Nginx/HTTPS se recomiendan los comandos explícitos de tres capas descritos aquí.

---

## 1. Topología y exposición de puertos

```text
                   Internet
                      |
            https://app.eduai.work.gd
                      |
                TCP 443 / 80
                      |
               Nginx en Ubuntu
                  /         \
                 /           \
      /, /admin/, /static/  /socket.io/
               |               |
       127.0.0.1:8000    127.0.0.1:8080
            Django           Flask
           Gunicorn        Socket.IO
               |               |
               +-------+-------+
                       |
           Red interna Docker Compose
           /          |          \
       PostgreSQL   Ollama     AI Worker
                     GPU      Embeddings GPU
                       \
                    ChromaDB / volúmenes
```

| Componente | Dirección o puerto | Acceso |
|---|---|---|
| Sitio EduAI | `https://app.eduai.work.gd` | Público |
| Administración | `https://app.eduai.work.gd/admin/` | Requiere autenticación |
| Socket.IO | `wss://app.eduai.work.gd/socket.io/` | Mediante Nginx |
| Django/Gunicorn | `127.0.0.1:8000` en el host | Solo local |
| Flask | `127.0.0.1:8080` en el host | Solo local |
| PostgreSQL | `postgres:5432` | Red interna Docker |
| Ollama | `ollama:11434` | Red interna Docker |

**No abras públicamente** los puertos `8000`, `8080`, `5432` ni `11434`. Comprueba que el parche de producción cambió los bindings de Django y Flask a `127.0.0.1`; Docker puede publicar puertos sin quedar totalmente sujeto a UFW.

## 2. DNS: crear el registro para `app.eduai.work.gd`

El panel descrito muestra el sufijo `.eduai.work.gd` automáticamente.

**Opción A (preferida): registro A específico**

| Campo | Valor |
|---|---|
| Tipo | `A` |
| Host Name | `app` |
| IP is | `Static` |
| IP Address | IPv4 pública de tu servidor |
| TTL | 5 minutos a 1 hora |

**Opción B (si el panel solo acepta `*`): registro wildcard**

| Campo | Valor |
|---|---|
| Tipo | `A` |
| Host Name | `*` |
| IP is | `Static` |
| IP Address | IPv4 pública de tu servidor |

Un registro `*.eduai.work.gd` puede resolver `app.eduai.work.gd`; **no hace que `eduai.work.gd` resuelva automáticamente**. No crees un CNAME adicional para `app` si ya tiene un A específico.

Comprueba desde Ubuntu o desde tu equipo local:

```bash
dig @1.1.1.1 +short A app.eduai.work.gd
dig +short AAAA app.eduai.work.gd
dig +short CAA app.eduai.work.gd
```

El registro A debe devolver tu IP pública. Un AAAA incorrecto puede causar problemas de acceso/validación IPv6. Si el DNS contiene restricciones CAA, verifica que permitan certificados de `letsencrypt.org`. Para un certificado del **nombre exacto** `app.eduai.work.gd`, no necesitas validar un certificado wildcard.

## 3. Preparación inicial del servidor

Verifica primero el sistema y los recursos:

```bash
cat /etc/os-release
uname -r
free -h
df -h
nvidia-smi
docker --version
docker compose version
```

Instala solo las utilidades que falten (el servidor puede traer Docker preinstalado):

```bash
sudo apt update
sudo apt install -y nginx git curl ca-certificates gnupg dnsutils snapd ufw
sudo systemctl enable --now nginx
```

En tu proveedor cloud abre **TCP 22** (o tu puerto SSH, idealmente restringido a tu IP) y **TCP 80/443**. Configura UFW **sin cerrar SSH**:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status verbose
```

Si utilizas otro puerto SSH, autorízalo antes de activar UFW. Si administras el servidor remotamente, asegúrate de tener acceso de recuperación desde el proveedor.

---

## 4. GPU: comprobarla en cada capa **antes** de compilar EduAI

### 4.1. Capa 1: host Ubuntu

```bash
nvidia-smi
nvidia-smi -L
```

Se espera identificar la **NVIDIA RTX A6000**. Si estos comandos fallan, el problema está en el driver/hardware o la instalación del host: **no intentes arreglarlo cambiando PyTorch dentro de Docker**.

### 4.2. Capa 2: Docker Engine y NVIDIA Container Toolkit

Prueba un contenedor aislado, sin usar aún EduAI:

```bash
docker run --rm --gpus all ubuntu:24.04 nvidia-smi
```

- **Funciona:** Docker puede solicitar la GPU. Continúa.
- **Falla, pero el `nvidia-smi` del host funciona:** revisa NVIDIA Container Toolkit y la configuración del runtime de Docker.
- **Falla porque no puedes conectarte al daemon:** resuelve primero permisos/conexión a Docker; no equivale a un error CUDA.

Comandos de inspección:

```bash
command -v nvidia-ctk || true
docker info --format '{{json .Runtimes}}'
sudo systemctl status docker --no-pager
```

Si NVIDIA Container Toolkit **ya está instalado** y Docker aún no dispone del runtime NVIDIA:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

docker run --rm --gpus all ubuntu:24.04 nvidia-smi
```

> **Atención:** reiniciar Docker puede interrumpir los servicios. Hazlo cuando puedas tolerar una breve parada. No reinstales drivers ni CUDA del host sin diagnosticar el fallo.

Si `nvidia-ctk` **no está instalado**, utiliza el repositorio oficial:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg2

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

docker run --rm --gpus all ubuntu:24.04 nvidia-smi
```

Referencia: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html>.

### 4.3. Capa 3: reserva explícita de GPU en Docker Compose

El archivo debe contener reservas similares a las siguientes **en los tres servicios** (`backend`, `ai_worker`, `ollama`):

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.gpu
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Revisa tu archivo:

```bash
cd ~/eduai
cat compose.gpu.yaml
```

No basta con tener esa configuración en disco: **debes incluir el archivo cuando ejecutas `docker compose up`**. Más adelante validaremos las reservas efectivas y recrearemos los contenedores.

---

## 5. Subir EduAI v3 y aplicar los parches

Si todavía no lo has clonado:

```bash
cd ~
git clone https://github.com/TU_USUARIO/eduai.git eduai
cd ~/eduai
```

Cambia la URL por la de tu repositorio real. Asegúrate de usar la misma versión de EduAI v3 examinada en este proyecto. Evita subir el `.env` o respaldos al repositorio.

Desde tu equipo local, puedes copiar únicamente los scripts (ejemplo, sustituye usuario e IP):

```bash
scp preparar_eduai_produccion.py \
  USUARIO@IP_PUBLICA:~/eduai/
```

En el servidor, confirma antes de aplicar parches:

```bash
cd ~/eduai
ls compose.yaml preparar_eduai_produccion.py
```

### 5.1. Aplicar el parche de producción con el dominio correcto

El script de producción debe ser **la versión actualizada que utiliza `app.eduai.work.gd`**, no la versión anterior que generaba `eduai.work.gd`. Antes de ejecutarlo:

```bash
grep -n 'app.eduai.work.gd' preparar_eduai_produccion.py
python3 -m py_compile preparar_eduai_produccion.py
```

En una copia nueva/no modificada:

```bash
python3 preparar_eduai_produccion.py . --dry-run
python3 preparar_eduai_produccion.py .
```

Generará/ajustará archivos entre los que están:

- `compose.prod.yaml` (Gunicorn, Django modo producción y orígenes Flask).
- `deploy/nginx/app.eduai.work.gd.conf` (Nginx y ruta `/socket.io/`).
- `frontend/djtesis/root/settings.py` (WhiteNoise, HTTPS detrás de proxy, cookies seguras).
- `frontend/djtesis/tesis/templates/tesis/chat.html` (Socket.IO por el mismo origen, sin `:8080`).
- `frontend/djtesis/requirements.txt` (Gunicorn y WhiteNoise).

Respaldos de los parches: `.eduai_gpu_backup/` y `.eduai_prod_backup/`. **No ejecutes a ciegas el script de producción sobre una instalación ya modificada manualmente:** haz primero `--dry-run`, compara cambios y conserva los respaldos.

### 5.2. Si ejecutaste antes la versión con `eduai.work.gd`

No necesitas desinstalar todo ni borrar volúmenes. Revisa estos puntos:

```bash
# Referencias al dominio antiguo que todavía queden en la configuración:
grep -n 'eduai.work.gd' .env compose.prod.yaml
ls -lah deploy/nginx/
```

**Interpretación:** una coincidencia que contenga `app.eduai.work.gd` es correcta. La que contenga exclusivamente `https://eduai.work.gd` o `server_name eduai.work.gd;` corresponde al dominio anterior. Modifica **solo esas entradas**, sin reemplazar indiscriminadamente `eduai.work.gd`, ya que eso podría convertir `app.eduai.work.gd` en `app.app.eduai.work.gd`.

Si únicamente dispones de `deploy/nginx/eduai.work.gd.conf` y no del nuevo, puedes preparar una copia sin tocar la original:

```bash
mkdir -p deploy/nginx
sed 's/server_name eduai\.work\.gd;/server_name app.eduai.work.gd;/' \
  deploy/nginx/eduai.work.gd.conf \
  > deploy/nginx/app.eduai.work.gd.conf
```

Revisa el resultado antes de instalarlo. No vuelvas a ejecutar un parche antiguo que regenere configuraciones con el dominio equivocado.

---

## 6. Variables `.env` para producción

Si es una instalación nueva:

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

Utiliza valores seguros y **diferentes** para los secretos (genera uno por vez):

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Ejemplo de variables requeridas o recomendadas (no uses los valores de marcador en producción):

```dotenv
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=app.eduai.work.gd,localhost,127.0.0.1,frontend
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.eduai.work.gd
EDUAI_SOCKETIO_ALLOWED_ORIGINS=https://app.eduai.work.gd

DJANGO_SECRET_KEY=GENERAR_CLAVE_ALEATORIA
AI_INTERNAL_TOKEN=GENERAR_TOKEN_ALEATORIO_DISTINTO
POSTGRES_DB=eduai
POSTGRES_USER=eduai_user
POSTGRES_PASSWORD=GENERAR_PASSWORD_SEGURO_DISTINTO

EDUAI_EMBEDDING_DEVICE=auto
EDUAI_ACCELERATOR=gpu
```

**Interpretación de las variables GPU:**

| Variable | Función | Limitación |
|---|---|---|
| `EDUAI_EMBEDDING_DEVICE=auto` | Elige CUDA si PyTorch la detecta, si no CPU | No asigna dispositivos a Docker |
| `EDUAI_EMBEDDING_DEVICE=cuda` | Fuerza CUDA y falla si no está disponible | Útil temporalmente para diagnosticar, no como arreglo |
| `EDUAI_EMBEDDING_DEVICE=cpu` | Fuerza procesamiento CPU | Para pruebas o recuperación |
| `EDUAI_ACCELERATOR=gpu` | Preferencia del iniciador `iniciar_eduai.sh` | `docker compose up` no la interpreta automáticamente |

**Importante:** la configuración GPU para el servicio `backend` y `ai_worker` utiliza la imagen alternativa `backend/Dockerfile.gpu` y la reserva GPU de `compose.gpu.yaml`. Ollama gestiona su propia aceleración; no depende de que PyTorch detecte CUDA.

El correo de recuperación de contraseñas debe tener un SMTP funcional en producción. El backend `django.core.mail.backends.console.EmailBackend` imprime mensajes en logs y **no envía correo**.

---

## 7. Ejecutar SIEMPRE las tres capas Compose

La combinación correcta para el servidor de producción es:

```bash
cd ~/eduai

docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  config --quiet
```

**Las capas tienen funciones diferentes:**

1. `compose.yaml`: aplicaciones, base de datos, volúmenes y variables comunes.
2. `compose.gpu.yaml`: `Dockerfile.gpu` y dispositivos NVIDIA para Ollama, Flask/backend y AI Worker.
3. `compose.prod.yaml`: Gunicorn y ajustes para Nginx/HTTPS.

**No despliegues esta instalación de producción con `docker compose up -d` sin archivos, ni con `./iniciar_eduai.sh` original del parche GPU**: ambos pueden omitir alguna capa necesaria y recrear servicios con una configuración distinta.

### 7.1. Verificar el modelo Compose antes de arrancar

Comprueba que hay reserva GPU y que los servicios correctos usan imagen GPU:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  config --format json | python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
for name in ("backend", "ai_worker", "ollama"):
    service = services[name]
    devices = (service.get("deploy", {}).get("resources", {})
                     .get("reservations", {}).get("devices", []))
    ok = any("gpu" in d.get("capabilities", []) for d in devices)
    print(name, "GPU solicitada:", ok)
    if not ok:
        raise SystemExit("ERROR: falta reserva GPU en " + name)
for name in ("backend", "ai_worker"):
    dockerfile = services[name].get("build", {}).get("dockerfile")
    print(name, "Dockerfile:", dockerfile)
    if dockerfile != "Dockerfile.gpu":
        raise SystemExit("ERROR: no usa Dockerfile.gpu en " + name)
'
```

Debe imprimir `GPU solicitada: True` para los tres servicios y `Dockerfile.gpu` para backend y worker.

**Revisa las publicaciones de puertos**:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  config --format json | python3 -c '
import json, sys
s=json.load(sys.stdin)["services"]
for n in ("frontend", "backend"):
    print(n, s[n].get("ports", []))
'
```

Los bindings de `8000` y `8080` deben indicar `127.0.0.1`, no `0.0.0.0`.

### 7.2. Construir e iniciar servicios

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  up -d --build

docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  ps

docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  logs --tail=100 frontend backend ai_worker ollama postgres
```

La primera compilación puede descargar dependencias CUDA y modelos grandes. No borres volúmenes persistentes para resolver errores de arranque.

### 7.3. Caso especial: antes arrancaste sin `compose.gpu.yaml`

La configuración `.env` no cambia de forma retroactiva los dispositivos de contenedores ya creados. Si Docker reconoce la GPU pero el `backend` actual no tiene reserva, **recréalo** (junto con worker y Ollama) utilizando las tres capas:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  up -d --build --force-recreate --no-deps backend ai_worker ollama
```

Puede haber una interrupción breve del chat y del procesamiento. `--no-deps` supone que PostgreSQL, frontend y los demás servicios ya funcionan. Si es la primera instalación o faltan dependencias, utiliza el `up -d --build` completo del apartado anterior.

Para evitar escribir las capas durante una sola sesión, opcionalmente:

```bash
export COMPOSE_FILE=compose.yaml:compose.gpu.yaml:compose.prod.yaml
docker compose ps
```

El `export` no persiste entre sesiones. Si no está establecido, sigue usando `-f` explícitamente.

---

## 8. Validación obligatoria: ¿el backend **realmente** tiene GPU?

### 8.1. Inspeccionar la reserva del contenedor en ejecución

**Utiliza la misma combinación Compose al consultar el identificador:**

```bash
CONTAINER_ID="$(docker compose \
  -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  ps -q backend)"

if [ -z "$CONTAINER_ID" ]; then
  echo 'No existe el contenedor backend; revisa docker compose ps'
else
  docker inspect "$CONTAINER_ID" \
    --format '{{json .HostConfig.DeviceRequests}}'
fi
```

- `null` o `[]`: no hay reserva GPU para el contenedor inspeccionado. Revisa el archivo GPU efectivo y recréalo.
- Una entrada `Driver: nvidia` con `Capabilities: [[gpu]]`: la GPU fue solicitada al daemon. **No garantiza aún que PyTorch la vea**.

### 8.2. Comprobar la GPU dentro del contenedor

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec backend nvidia-smi

docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec backend python -c 'import torch; print("PyTorch:", torch.__version__); print("CUDA:", torch.cuda.is_available()); print("GPU count:", torch.cuda.device_count()); print("CUDA runtime:", torch.version.cuda)'
```

Después ejecuta el diagnóstico específico de EduAI:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec backend python -c 'from eduai.ai.device import hardware_info; print(hardware_info())'

docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec ai_worker python -c 'from eduai.ai.device import hardware_info; print(hardware_info())'
```

**Resultado esperado (valores ilustrativos):**

```python
{
    'requested_device': 'auto',
    'selected_device': 'cuda',
    'cuda_available': True,
    'mps_available': False,
    'pytorch_version': '2.5.1+cu121',
    'gpu_name': 'NVIDIA RTX A6000',
    'gpu_total_memory_gib': 47.XX,
    'error': None
}
```

No confíes solo en `torch.__version__`: un wheel `+cu121` **puede estar bien instalado y aun así devolver `cuda_available=False`**.

### 8.3. Validar GPU de Ollama por separado

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec ollama nvidia-smi

docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec ollama ollama pull gemma3:4b
```

Carga el modelo realizando una consulta desde EduAI o con Ollama y, mientras esté residente:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec ollama ollama ps

nvidia-smi
```

La columna `PROCESSOR` de `ollama ps` permite ver si Ollama lo está ejecutando en GPU, CPU o una combinación. `ollama ps` vacío solo indica que no hay modelos cargados en ese momento. Si tu configuración usa modelos adicionales, descárgalos también.

---

## 9. Configurar Nginx para `app.eduai.work.gd`

El parche actualizado debería generar:

```text
deploy/nginx/app.eduai.work.gd.conf
```

Inspecciona el sitio y comprueba que contiene `server_name app.eduai.work.gd;` y `location /socket.io/`:

```bash
grep -nE 'server_name|location /socket.io/|proxy_pass' \
  deploy/nginx/app.eduai.work.gd.conf
```

Instálalo en Ubuntu:

```bash
sudo cp deploy/nginx/app.eduai.work.gd.conf \
  /etc/nginx/sites-available/app.eduai.work.gd

sudo ln -sfn \
  /etc/nginx/sites-available/app.eduai.work.gd \
  /etc/nginx/sites-enabled/app.eduai.work.gd

sudo nginx -t
sudo systemctl reload nginx
```

Si tenías activada la configuración previa **`eduai.work.gd`** que ya no utilizas, retira *solo el enlace* de ese sitio y vuelve a validar Nginx:

```bash
# Ejecuta únicamente si ese sitio antiguo es tuyo y ya no está en uso:
# sudo rm /etc/nginx/sites-enabled/eduai.work.gd
# sudo nginx -t && sudo systemctl reload nginx
```

Socket.IO debe conectarse mediante el **mismo origen** de la web:

```javascript
const socket = io(window.location.origin, {path: "/socket.io/"});
```

El navegador no debe solicitar `https://app.eduai.work.gd:8080`; Nginx se encarga de conectar internamente con Flask en `127.0.0.1:8080` y de reenviar correctamente la actualización WebSocket.

Verifica localmente antes de emitir el certificado:

```bash
curl -I http://127.0.0.1:8000/admin/login/
curl -I -H 'Host: app.eduai.work.gd' http://127.0.0.1/
```

Si hay `502 Bad Gateway`, consulta logs de Nginx y de los contenedores Django/Flask.

---

## 10. Certificado HTTPS con Let's Encrypt

Con DNS correcto y los puertos 80/443 disponibles:

```bash
sudo snap install certbot --classic
command -v certbot || sudo ln -s /snap/bin/certbot /usr/local/bin/certbot

sudo certbot --nginx -d app.eduai.work.gd --redirect
sudo nginx -t
sudo certbot renew --dry-run
```

Estas instrucciones solicitan un certificado **solo para `app.eduai.work.gd`**. No solicites un wildcard a menos que necesites proteger otros subdominios; los certificados wildcard requieren el procedimiento DNS-01.

Comprueba:

```bash
curl -I https://app.eduai.work.gd/
curl -I https://app.eduai.work.gd/admin/login/
curl -I https://app.eduai.work.gd/static/admin/css/base.css
```

Si falla la emisión: verifica `dig`, puertos 80/443, Nginx `server_name`, posibles registros AAAA obsoletos, CAA y que el proveedor no bloquee HTTP entrante.

---

## 11. Primer arranque de la aplicación

Ejecuta migraciones/colección de estáticos mediante el arranque de producción (configurado en `compose.prod.yaml`); revisa que no haya fallos:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  logs --tail=150 frontend
```

Crea un superusuario **solo si aún no existe**:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec frontend python manage.py createsuperuser
```

Realiza comprobación de despliegue Django:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  exec frontend python manage.py check --deploy
```

Examina las advertencias de seguridad; no todas implican el mismo riesgo y algunas pueden requerir ajustes específicos del proxy o el contexto de ejecución.

### Pruebas funcionales mínimas

- Abrir `https://app.eduai.work.gd/`, iniciar sesión y entrar a `/admin/`.
- Abrir `/admin/ia/` y comprobar que el backend registra dispositivo CUDA.
- Verificar que el chat abre una conexión WebSocket `wss://app.eduai.work.gd/socket.io/` **sin `:8080`**.
- Subir un documento de prueba, procesarlo e inspeccionar los logs del worker.
- Generar preguntas y exámenes; comprobar creación y descarga PDF/DOCX.
- Confirmar que cada usuario solo puede acceder a sus propios documentos/descargas.
- Verificar la recuperación de contraseña cuando el SMTP esté configurado.

**Nota importante sobre exportaciones:** en EduAI v3 Flask genera un ZIP con PDF/DOCX y Django lo extrae en su `MEDIA_ROOT/exports/...`. Por eso las descargas deben verificarse sobre el volumen `django_media` y la ruta de Django autenticada; si responden 404, comprueba la ruta, el nombre exacto del documento y la existencia de los archivos en `/app/media/exports/` del contenedor `frontend`. No expongas `/media/` como directorio público sin validación de acceso.

---

## 12. Diagnóstico rápido de problemas conocidos

| Síntoma | Posible causa | Prueba / acción |
|---|---|---|
| `nvidia-smi` del host falla | Driver o GPU del servidor | Resolver en host antes de Docker |
| Host ve la GPU, `docker run --gpus all ...` falla | NVIDIA Container Toolkit/runtime | Sección 4.2 |
| Docker aislado ve la GPU, `hardware_info()` devuelve CPU | Contenedor creado sin capa GPU o entorno CUDA no visible | Secciones 7 y 8 |
| `torch==2.5.1+cu121` y `cuda_available=False` | Wheel CUDA instalado, **pero acceso GPU no confirmado** | Inspeccionar `DeviceRequests` y `nvidia-smi` dentro de backend |
| `docker inspect ...DeviceRequests` es `null` o `[]` | Reserva GPU ausente en contenedor actual | Recrear con las tres capas |
| `DeviceRequests` tiene NVIDIA, PyTorch aún devuelve `False` | Dispositivos/librerías visibles de forma incorrecta u otra incompatibilidad | Ver logs, runtime, `nvidia-smi` en contenedor, `torch.cuda.device_count()` |
| `EDUAI_ACCELERATOR=gpu` pero sigue en CPU | Ejecutaste `docker compose` sin overlay GPU | Usar `-f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml` |
| `404`/DNS no resuelve en `eduai.work.gd` | Solo puedes usar subdominios | Utiliza `app.eduai.work.gd` |
| `400` o errores al conectar Socket.IO | Origen CORS o URL/puerto incorrectos | Revisar `EDUAI_SOCKETIO_ALLOWED_ORIGINS`, proxy y JS |
| `502` en Nginx | Django o Flask no responde en loopback | `curl 127.0.0.1:8000`, logs contenedores y Nginx |
| Error `DisallowedHost` de Django | Falta host en `.env` o contenedor no recreado | Revisar `DJANGO_ALLOWED_HOSTS` efectivo |
| Error CSRF en HTTPS | Origen HTTPS o proxy mal configurado | Comprobar `DJANGO_CSRF_TRUSTED_ORIGINS` y `X-Forwarded-Proto` |
| Archivos estáticos faltantes | `collectstatic` o WhiteNoise falló | Revisar logs frontend y `curl /static/admin/css/base.css` |
| PDF/DOCX con `404` | Ruta `/media/exports` o autorización no coincidente | Revisar `/app/media/exports` en frontend y vista de descarga |
| Ollama usa CPU mientras embeddings usan GPU | Configuración de Ollama independiente | `ollama ps`, `nvidia-smi`, reserva del contenedor Ollama |
| GPU sin memoria | Modelos y embeddings compiten por VRAM | Revisar `nvidia-smi`, reducir simultaneidad/tamaño de modelo |

### Comandos de diagnóstico para copiar y pegar

```bash
cd ~/eduai

# 1. El host ve la GPU
nvidia-smi

# 2. Docker puede solicitar GPU
docker run --rm --gpus all ubuntu:24.04 nvidia-smi

# 3. Configuración efectiva con GPU y producción
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml config --quiet

# 4. El contenedor backend recibió GPU
CID="$(docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml ps -q backend)"
docker inspect "$CID" --format '{{json .HostConfig.DeviceRequests}}'

# 5. GPU y CUDA dentro de backend
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml exec backend nvidia-smi
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml exec backend python -c 'from eduai.ai.device import hardware_info; print(hardware_info())'

# 6. GPU y modelos de Ollama
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml exec ollama ollama ps

# 7. Estado y errores
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml ps
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml logs --tail=80 backend ai_worker ollama frontend
```

**Cómo interpretar las pruebas:**

1. Si falla (1), revisa el host.
2. Si funciona (1) y falla (2), revisa NVIDIA Container Toolkit.
3. Si funciona (2), pero falla (3), revisa el YAML/variables.
4. Si (3) funciona y (4) muestra `[]`/`null`, recrea usando las tres capas.
5. Si (4) incluye reserva NVIDIA, pero (5) muestra CUDA `False`, investiga el runtime/dispositivos **dentro** del contenedor; no asumas que reinstalar PyTorch resolverá el problema.
6. Si backend muestra CUDA `True` y Ollama no utiliza GPU, diagnostica el contenedor Ollama de forma independiente.

---

## 13. Operación, seguridad, actualizaciones y respaldos

### Actualizar el código

```bash
cd ~/eduai
git status
git pull

docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml \
  up -d --build
```

Revisa los cambios antes del `git pull` cuando haya archivos modificados localmente. **No ejecutes los parches antiguos de nuevo** después de cada actualización; verifica que el repositorio ya los incluya.

### Reiniciar o consultar logs

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml restart backend ai_worker

docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml logs -f --tail=100 backend
```

`restart` **no aplica cambios en la configuración Compose o en la imagen**. Para eso utiliza `up -d --build` y recreación cuando corresponda.

### Respaldos y continuidad

Conserva copias de PostgreSQL, documentos, índices vectoriales y modelos. Volúmenes identificados en EduAI v3:

- `postgres_data`: base PostgreSQL.
- `django_media`: archivos generados/medios Django.
- `backend_uploads`: documentos subidos a Flask.
- `backend_vectors`: persistencia ChromaDB.
- `ollama_data`: modelos Ollama.
- `hf_cache`: caché de modelos Hugging Face.
- Otros volúmenes auxiliares: `django_data`, `backend_exports`, `backend_images`, `backend_pdfs`.

**No ejecutes `docker compose down -v`**, salvo que realmente desees eliminar los volúmenes. Para respaldar PostgreSQL, utiliza un procedimiento consistente de `pg_dump`/`pg_restore` y comprueba periódicamente la restauración en un entorno aislado. Si migras datos desde una máquina anterior, no basta con copiar el código: también necesitas los volúmenes y el estado de base de datos correspondiente.

### Seguridad mínima antes de abrir acceso público

- Mantén `.env` fuera de Git; revisa si hubo exposición previa y rota secretos si fue necesario.
- No publiques los puertos internos y verifica los bindings de Docker.
- No expongas Ollama, PostgreSQL ni rutas internas de Flask directamente a Internet.
- Verifica que Nginx bloquea `/internal/` del lado público; los servicios Docker deben seguir pudiendo comunicarse internamente.
- Configura copias de seguridad y actualizaciones de seguridad del host.
- Verifica acceso a descargas solo con sesión y propietario correctos.
- Configura SMTP si se utilizará recuperación de contraseñas.
- Comprueba Certbot con `sudo certbot renew --dry-run`.
- Supervisa `nvidia-smi`, uso de memoria RAM, disco, logs de Docker y errores 5xx de Nginx.

---

## 14. Lista final de verificación

- [ ] El DNS de `app.eduai.work.gd` apunta a la IP pública.
- [ ] El controlador NVIDIA detecta la RTX A6000 en el host.
- [ ] `docker run --rm --gpus all ubuntu:24.04 nvidia-smi` funciona.
- [ ] El conjunto de **tres** archivos Compose valida correctamente.
- [ ] `backend`, `ai_worker` y `ollama` tienen reservas GPU.
- [ ] Backend y AI Worker usan `Dockerfile.gpu`.
- [ ] `DeviceRequests` del contenedor backend contiene NVIDIA.
- [ ] `hardware_info()` indica `selected_device='cuda'` y `cuda_available=True`.
- [ ] Ollama utiliza GPU al cargar un modelo (`ollama ps`).
- [ ] Django y Flask están publicados solo en `127.0.0.1`.
- [ ] Nginx sirve `app.eduai.work.gd` y hace proxy de `/socket.io/`.
- [ ] Let's Encrypt emitió un certificado válido para `app.eduai.work.gd`.
- [ ] HTTPS, login, administración y estáticos funcionan.
- [ ] El chat conecta mediante `wss://` sin el puerto 8080.
- [ ] Carga de documentos, embeddings, exámenes y descargas PDF/DOCX funcionan.
- [ ] Hay un respaldo probado de PostgreSQL y archivos/volúmenes críticos.

## Fuentes oficiales

- NVIDIA — Container Toolkit: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html>
- Docker — GPU en Docker Compose: <https://docs.docker.com/compose/how-tos/gpu-support/>
- Docker — Combinación de varios archivos Compose: <https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/>
- Certbot — Uso con Nginx: <https://certbot.eff.org/instructions?ws=nginx&os=snap>
- Nginx — Proxy de WebSocket: <https://nginx.org/en/docs/http/websocket.html>
- PyTorch — Verificación de CUDA: <https://pytorch.org/get-started/locally/>

---

**Conclusión:** en este despliegue el dominio correcto es **`app.eduai.work.gd`** y la condición indispensable para utilizar la RTX A6000 no es tener `EDUAI_ACCELERATOR=gpu` en `.env`, sino que **Docker pueda asignar el dispositivo NVIDIA y que PyTorch/Ollama lo detecten dentro de sus contenedores**. El diagnóstico anterior (`torch 2.5.1+cu121`, CUDA `False`) debe resolverse con las verificaciones escalonadas de esta guía, sin reemplazar innecesariamente el driver o la versión de PyTorch.
