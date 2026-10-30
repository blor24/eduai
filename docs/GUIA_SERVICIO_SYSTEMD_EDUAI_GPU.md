# Guía: ejecutar EduAI v3 como servicio de Linux (systemd + Docker Compose)

**Entorno previsto:** Ubuntu Server 24.04 LTS · NVIDIA RTX A6000 (driver R570, CUDA 12.8 en el servidor) · Docker Compose · Nginx · HTTPS · `app.eduai.work.gd`.

> **Objetivo.** Iniciar EduAI automáticamente cuando arranque Ubuntu y administrarlo con `systemctl`, sin perder la configuración de GPU, producción y proxy inverso. Este documento presupone que el proyecto ya fue desplegado en `/home/ubuntu/eduai` y contiene los archivos indicados a continuación.

## 1. Arquitectura de servicios

- **`eduai.service` (systemd):** inicia y detiene el conjunto de contenedores de Docker Compose.
- **`docker.service` (systemd):** mantiene funcionando Docker.
- **`nginx.service` (systemd):** recibe las peticiones a `https://app.eduai.work.gd` y las reenvía a los servicios internos.
- **Docker Compose:** ejecuta `frontend` (Django/Gunicorn), `backend` (Flask/Socket.IO), `ai_worker`, `postgres` y `ollama`.

Se combinan tres archivos Compose, **siempre en este orden**:

| Archivo | Función |
|---|---|
| `compose.yaml` | Servicios, redes y volúmenes de la aplicación |
| `compose.gpu.yaml` | Reserva de GPU NVIDIA y variantes de imágenes compatibles con CUDA |
| `compose.prod.yaml` | Ajustes de producción, Gunicorn y configuración detrás de Nginx |

Las variables `EDUAI_EMBEDDING_DEVICE=auto` y `EDUAI_ACCELERATOR=gpu` **no otorgan por sí mismas acceso a la GPU**. El archivo `compose.gpu.yaml` debe estar incluido en el inicio, y NVIDIA Container Toolkit debe funcionar en el host.

## 2. Verificaciones previas

Conéctate al servidor mediante SSH y sitúate en la raíz del proyecto:

```bash
cd /home/ubuntu/eduai
ls -l compose.yaml compose.gpu.yaml compose.prod.yaml
```

Comprueba el controlador NVIDIA y que Docker puede acceder a la GPU:

```bash
nvidia-smi
docker run --rm --gpus all ubuntu:24.04 nvidia-smi
```

Si `nvidia-smi` funciona en Ubuntu pero falla en Docker, comprueba NVIDIA Container Toolkit:

```bash
command -v nvidia-ctk
docker info --format '{{json .Runtimes}}'
```

Si ya está instalado, una posible corrección es:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

> **Atención:** reiniciar Docker puede interrumpir temporalmente servicios activos. Si `nvidia-ctk` no está instalado, consulta la documentación oficial de [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) antes de continuar.

Valida la unión de los archivos Compose:

```bash
docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  config --quiet
```

Confirma que `.env` contiene, como mínimo, las variables de despliegue que correspondan a tu configuración:

```dotenv
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=app.eduai.work.gd,localhost,127.0.0.1,frontend
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.eduai.work.gd
EDUAI_SOCKETIO_ALLOWED_ORIGINS=https://app.eduai.work.gd
EDUAI_EMBEDDING_DEVICE=auto
EDUAI_ACCELERATOR=gpu
```

Mantén además los secretos, credenciales y variables requeridas por PostgreSQL y el backend. No publiques `.env` en Git.

## 3. Primera compilación e inicio manual

Antes de crear el servicio, construye las imágenes una vez:

```bash
cd /home/ubuntu/eduai

docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  up -d --build
```

Comprueba el estado:

```bash
docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  ps
```

Si algo falla, revisa los registros antes de habilitar el inicio automático:

```bash
docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  logs --tail=100
```

## 4. Crear `eduai.service`

Comprueba dónde está instalado el ejecutable Docker:

```bash
command -v docker
```

Los ejemplos utilizan `/usr/bin/docker`. Si el comando anterior muestra otra ruta, sustitúyela en el servicio.

Crea el archivo:

```bash
sudo nano /etc/systemd/system/eduai.service
```

Pega la siguiente configuración:

```ini
[Unit]
Description=EduAI v3 - Plataforma educativa con IA y GPU NVIDIA
Documentation=https://app.eduai.work.gd
Requires=docker.service
Wants=network-online.target
After=docker.service network-online.target
RequiresMountsFor=/home/ubuntu/eduai

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
WorkingDirectory=/home/ubuntu/eduai

# Validar los tres archivos Compose antes del arranque.
ExecStartPre=/usr/bin/docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml config --quiet

# Arrancar las imágenes ya construidas, sin reconstruirlas en cada inicio.
ExecStart=/usr/bin/docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml up -d --no-build

# Detener los contenedores administrados por este proyecto.
ExecStop=/usr/bin/docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml stop

Restart=on-failure
RestartSec=10
TimeoutStartSec=300
TimeoutStopSec=120
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Notas:**

- `Type=oneshot` con `RemainAfterExit=yes` es correcto porque `docker compose up -d` termina tras iniciar los contenedores. `systemctl status` mostrará normalmente **`active (exited)`**.
- El servicio emplea `root` para evitar depender de la configuración del grupo Docker de un usuario. Modificar este aspecto requiere permisos adecuados para acceder al daemon Docker.
- `--no-build` supone que las imágenes ya existen; cuando cambies dependencias o código, reconstruye explícitamente.
- `systemd` **no comprueba continuamente la salud de cada contenedor**. Para recuperarse de fallos de procesos, mantén `restart: unless-stopped` y configura `healthcheck` cuando corresponda.

## 5. Activar y administrar el servicio

Registra la unidad e inicia EduAI:

```bash
sudo systemctl daemon-reload
sudo systemctl enable eduai.service
sudo systemctl start eduai.service
sudo systemctl status eduai.service --no-pager
```

Comandos habituales:

| Acción | Comando |
|---|---|
| Arrancar | `sudo systemctl start eduai` |
| Detener | `sudo systemctl stop eduai` |
| Reiniciar | `sudo systemctl restart eduai` |
| Consultar estado | `sudo systemctl status eduai` |
| Activar al encender | `sudo systemctl enable eduai` |
| Desactivar al encender | `sudo systemctl disable eduai` |
| Ver eventos de la unidad | `sudo journalctl -u eduai.service -f` |

Para ver los registros **de la aplicación** (no solo los eventos de systemd):

```bash
cd /home/ubuntu/eduai

docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  logs -f --tail=100
```

Puedes añadir el nombre de un servicio al final del comando, por ejemplo `backend`, `frontend`, `ollama` o `ai_worker`.

## 6. Habilitar Nginx como servicio independiente

Nginx no debe incorporarse dentro de `eduai.service`; ya tiene su propia unidad systemd:

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl status nginx --no-pager
```

La configuración de Nginx para `app.eduai.work.gd` debe redirigir las solicitudes de Django hacia `127.0.0.1:8000` y la ruta `/socket.io/` hacia `127.0.0.1:8080`, incluyendo los encabezados WebSocket correspondientes. El certificado HTTPS de Certbot y la redirección de HTTP a HTTPS se administran por separado.

Verifica que el dominio resuelva a la IP pública:

```bash
dig +short app.eduai.work.gd
```

Si todavía no configuraste el certificado y el sitio HTTP ya responde, puedes solicitarlo con:

```bash
sudo certbot --nginx -d app.eduai.work.gd --redirect
```

No es necesario publicar directamente los puertos 8000, 8080, 5432 o 11434 en Internet.

## 7. Verificar el acceso a la GPU después del arranque

Tras iniciar el servicio, consulta la detección de PyTorch en el contenedor `backend`:

```bash
cd /home/ubuntu/eduai

docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  exec backend python -c \
  "from eduai.ai.device import hardware_info; print(hardware_info())"
```

Resultado esperado (los detalles pueden variar):

```python
{
    'requested_device': 'auto',
    'selected_device': 'cuda',
    'cuda_available': True,
    'pytorch_version': '2.5.1+cu121',
    'gpu_name': 'NVIDIA RTX A6000',
    # ...
}
```

Para revisar si el contenedor tiene una reserva NVIDIA:

```bash
CONTAINER_ID=$(docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  ps -q backend)

docker inspect "$CONTAINER_ID" \
  --format '{{json .HostConfig.DeviceRequests}}'
```

Si el resultado es `null` o `[]`, revisa si se utilizó el archivo `compose.gpu.yaml` al crear el contenedor. Si el contenedor fue creado sin GPU, recréalo con los tres archivos:

```bash
docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  up -d --build --force-recreate --no-deps backend ai_worker
```

**Importante:** la compilación de PyTorch `2.5.1+cu121` indica soporte CUDA en el paquete, pero **no garantiza** que la GPU sea accesible. Se necesita que Docker entregue el dispositivo al contenedor.

Para Ollama, comprueba primero el acceso NVIDIA y luego dónde está cargado el modelo:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml exec ollama nvidia-smi
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.prod.yaml exec ollama ollama ps
```

`ollama ps` es informativo cuando hay modelos cargados; revisa su columna `PROCESSOR`.

## 8. Políticas de reinicio y supervisión

Comprueba que los servicios apropiados en `compose.yaml` tengan una política de reinicio; para EduAI la opción habitual es:

```yaml
restart: unless-stopped
```

Esto permite que Docker reinicie un contenedor que falla de forma inesperada. No sustituye a los controles de salud (`healthcheck`) ni a la revisión de logs. La unidad `eduai.service` organiza el arranque del conjunto, pero **no pasa a `failed` automáticamente porque Flask o Django se hayan detenido después del `up -d`**.

> Evita administrar el mismo conjunto de contenedores simultáneamente con dos unidades systemd diferentes.

## 9. Actualizar el proyecto

Cuando actualices el código:

```bash
cd /home/ubuntu/eduai

git pull

docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  up -d --build
```

El servicio systemd puede permanecer habilitado. Si modificas el archivo `/etc/systemd/system/eduai.service`, ejecuta:

```bash
sudo systemctl daemon-reload
sudo systemctl restart eduai
```

Haz respaldos antes de cambios de base de datos o de versiones importantes. **No ejecutes `docker compose down -v`**, porque puede eliminar volúmenes persistentes de PostgreSQL, modelos Ollama y otros datos del proyecto.

## 10. Probar el inicio automático tras reiniciar Ubuntu

Cuando todo funcione correctamente:

```bash
sudo reboot
```

Vuelve a conectarte y verifica:

```bash
sudo systemctl is-enabled eduai nginx docker
sudo systemctl status eduai --no-pager
sudo systemctl status nginx --no-pager

cd /home/ubuntu/eduai
docker compose \
  -f compose.yaml \
  -f compose.gpu.yaml \
  -f compose.prod.yaml \
  ps
```

Comprueba finalmente que el sitio y la administración respondan:

- <https://app.eduai.work.gd/>
- <https://app.eduai.work.gd/admin/>

Valida una sesión real, la conexión Socket.IO, la carga de documentos y una consulta al modelo para confirmar que la aplicación funciona además de que los contenedores figuren como iniciados.

## 11. Resolución de problemas rápidos

| Síntoma | Verificación / solución |
|---|---|
| `systemctl` muestra `active (exited)` | Normal para `Type=oneshot` y `RemainAfterExit=yes`; revisa `docker compose ps`. |
| `cuda_available=False` | Ejecuta `nvidia-smi` en host y contenedor, revisa NVIDIA Container Toolkit y la reserva GPU de Compose. |
| `DeviceRequests` es `null` o `[]` | Contenedor creado sin GPU; comprueba `compose.gpu.yaml` y recréalo con los tres archivos. |
| Error `no such image` al iniciar systemd | Compila primero con `docker compose ... up -d --build`; el servicio usa `--no-build`. |
| Error `Failed at step EXEC` | Comprueba `command -v docker` y la ruta de `ExecStart`. |
| Nginx responde `502 Bad Gateway` | Revisa `docker compose ps`, registros de Django/Flask y que los puertos locales estén disponibles. |
| Socket.IO no conecta con HTTPS | Revisa `/socket.io/`, encabezados WebSocket, configuración de orígenes y contenido mixto. |
| No arranca tras reinicio | Consulta `sudo journalctl -u eduai.service -b --no-pager` y `sudo systemctl status docker`. |

## 12. Lista final de verificación

- [ ] `nvidia-smi` detecta la RTX A6000 en Ubuntu.
- [ ] `docker run --rm --gpus all ubuntu:24.04 nvidia-smi` funciona.
- [ ] Los tres archivos Compose están presentes y su configuración valida.
- [ ] Django, Flask, PostgreSQL, AI Worker y Ollama están en ejecución.
- [ ] PyTorch indica `selected_device='cuda'`.
- [ ] `eduai.service` está habilitado para iniciar al encender Ubuntu.
- [ ] `nginx.service` está activo y HTTPS funciona con `app.eduai.work.gd`.
- [ ] Chat, documentos, generación de preguntas y administración funcionan tras un reinicio completo.

---

**Resultado:** EduAI se ejecuta como servicio administrado por `systemd`, con Docker Compose para los componentes de aplicación y GPU, y Nginx como proxy HTTPS independiente.
