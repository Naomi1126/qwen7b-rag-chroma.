
# STAGE 1: Build Frontend (Node)
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copiar package files (incluye package.json y, si existe, package-lock.json)
COPY frontend/package*.json ./

# Instalar dependencias necesarias para BUILD (incluye devDependencies)
# - npm ci requiere package-lock.json
# - si no existe lockfile, usamos npm install
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Copiar código fuente del frontend
COPY frontend/ ./

# Build para producción (genera dist/)
RUN npm run build

# Verificar que se generó dist/
RUN echo "=== FRONTEND DIST ===" && ls -la dist/


# ==========================================
# STAGE 2: Backend + vLLM (Python + CUDA)
# ==========================================
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/workspace/hf \
    VLLM_WORKSPACE=/workspace \
    VLLM_MODEL_NAME="Qwen/Qwen2.5-7B-Instruct" \
    VLLM_API_URL="http://127.0.0.1:8000/v1/chat/completions" \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /workspace

# 1) Paquetes base
RUN apt-get update && apt-get install -y --no-install-recommends \
      software-properties-common \
      curl ca-certificates git bash wget gnupg \
      build-essential \
      libgl1 libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# 2) Python 3.11
RUN add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y --no-install-recommends \
      python3.11 python3.11-venv python3.11-dev \
  && rm -rf /var/lib/apt/lists/*

# 3) Virtualenv
RUN python3.11 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel

# 4) Torch + vLLM
RUN /opt/venv/bin/pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu121 \
    "torch==2.4.0" "torchvision==0.19.0" && \
    /opt/venv/bin/pip install --no-cache-dir \
    "vllm==0.6.0"

# 5) Dependencias del proyecto
COPY requirements.txt /workspace/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /workspace/requirements.txt

# 6) Limpieza
RUN apt-get purge -y build-essential python3.11-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# 7) Usuario no-root + directorios de datos
RUN useradd -m app && chown -R app:app /workspace && \
    mkdir -p /data/docs /data/chroma && chown -R app:app /data

# 8) Copiar frontend build desde stage 1 (esto es lo que se sirve)
COPY --from=frontend-builder --chown=app:app /frontend/dist /workspace/dist

# 8.1) Copiar también el código fuente del frontend al runtime (para inspección/debug)
# Esto NO afecta lo servido (lo servido es /workspace/dist), pero te deja ver src dentro del contenedor.
COPY --from=frontend-builder --chown=app:app /frontend /workspace/frontend

# Quitar node_modules del runtime para que no pese tanto (opcional pero recomendado)
RUN rm -rf /workspace/frontend/node_modules || true

# 9) Copiar código del backend (aplanado)
COPY --chown=app:app start.sh /workspace/start.sh
COPY --chown=app:app backend/ingest.py /workspace/ingest.py
COPY --chown=app:app backend/search.py /workspace/search.py
COPY --chown=app:app backend/app.py /workspace/app.py
COPY --chown=app:app backend/rag_core.py /workspace/rag_core.py
COPY --chown=app:app backend/auth.py /workspace/auth.py
COPY --chown=app:app backend/models.py /workspace/models.py
COPY --chown=app:app backend/database.py /workspace/database.py
COPY --chown=app:app backend/init_admin.py /workspace/init_admin.py
COPY --chown=app:app backend/init_areas.py /workspace/init_areas.py
COPY --chown=app:app backend/manage_users.py /workspace/manage_users.py

# 10) Copiar assets estáticos (logos)
COPY --chown=app:app static /workspace/static

RUN chmod +x /workspace/start.sh

# 11) Verificar estructura final
RUN echo "=== Verificando estructura ===" && \
    ls -la /workspace/dist/ && \
    ls -la /workspace/frontend/src/ && \
    ls -la /workspace/*.py

USER app

# Solo exponemos puerto 7860 (FastAPI sirve frontend + API)
EXPOSE 7860

ENTRYPOINT ["/workspace/start.sh"]
