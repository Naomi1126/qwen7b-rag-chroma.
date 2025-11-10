FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/workspace/hf \
    VLLM_WORKSPACE=/workspace \
    OPENAI_API_BASE=http://127.0.0.1:8000/v1 \
    WEBUI_PORT=8090 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /workspace

# 1) Paquetes base
RUN apt-get update && apt-get install -y --no-install-recommends \
      software-properties-common \
      curl ca-certificates git bash tini wget gnupg \
      build-essential \
  && rm -rf /var/lib/apt/lists/*

# 2) Python 3.11 (requerido por vLLM recientes)
RUN add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y --no-install-recommends \
      python3.11 python3.11-venv python3.11-dev \
  && rm -rf /var/lib/apt/lists/*

# 3) venv + toolchain
RUN python3.11 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel

# 4) Node.js 18 (para compilar frontend de Open WebUI al instalarlo)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    node -v && npm -v

# 5) Dependencias Python (vía requirements.txt)
COPY requirements.txt /workspace/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /workspace/requirements.txt

# 6) Limpiar Node y caches para reducir peso (el frontend ya quedó construido)
RUN apt-get purge -y nodejs && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /root/.npm /home/*/.npm /tmp/*

# 7) Usuario no-root y rutas de datos persistentes
RUN useradd -m app && chown -R app:app /workspace
RUN mkdir -p /data/docs /data/chroma && chown -R app:app /data

# 8) Scripts
COPY --chown=app:app start.sh /workspace/start.sh
COPY --chown=app:app ingest.py /workspace/ingest.py
COPY --chown=app:app search.py /workspace/search.py
RUN chmod +x /workspace/start.sh

USER app

EXPOSE 8000 8090

ENTRYPOINT ["/usr/bin/tini","-g","--"]
CMD ["/workspace/start.sh"]
