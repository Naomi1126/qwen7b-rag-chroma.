FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/workspace/hf \
    VLLM_WORKSPACE=/workspace \
    VLLM_MODEL_NAME="Qwen/Qwen2.5-7B-Instruct" \
    VLLM_API_URL="http://127.0.0.1:8000/v1/chat/completions" \
    WEBUI_PORT=8090 \
    PATH="/opt/venv/bin:${PATH}" \
    GRADIO_ANALYTICS_ENABLED="False"

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

# 5) Dependencias del proyecto (única fuente de verdad)
COPY requirements.txt /workspace/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /workspace/requirements.txt

# 6) Limpieza
RUN apt-get purge -y build-essential python3.11-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# 7) Usuario no-root + directorios de datos
RUN useradd -m app && chown -R app:app /workspace && \
    mkdir -p /data/docs /data/chroma && chown -R app:app /data

# 8) Código del proyecto
COPY --chown=app:app start.sh /workspace/start.sh
COPY --chown=app:app ingest.py /workspace/ingest.py
COPY --chown=app:app search.py /workspace/search.py
COPY --chown=app:app app.py /workspace/app.py
COPY --chown=app:app rag_core.py /workspace/rag_core.py
COPY --chown=app:app auth.py /workspace/auth.py
COPY --chown=app:app models.py /workspace/models.py
COPY --chown=app:app database.py /workspace/database.py
COPY --chown=app:app app_gradio.py /workspace/app_gradio.py
COPY --chown=app:app init_admin.py /workspace/init_admin.py
COPY --chown=app:app init_areas.py /workspace/init_areas.py

COPY --chown=app:app static /workspace/static

RUN chmod +x /workspace/start.sh

USER app

EXPOSE 8000 7860 9001
ENTRYPOINT ["/workspace/start.sh"]
