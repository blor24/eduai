FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# Tesseract en inglés y español, compiladores para ruedas nativas,
# libgomp para dependencias de ML.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt /app/requirements.docker.txt
# CPU-only PyTorch evita descargar bibliotecas CUDA si no usas GPU.
RUN python -m pip install --upgrade pip && \
    python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.docker.txt

COPY . /app
RUN mkdir -p /app/uploads /app/chroma_dbs /app/images /app/exports /app/pdfs /app/.cache/huggingface

EXPOSE 8080
CMD ["python", "eduai-backend.py"]
