FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/workspace/hf \
    VLLM_WORKSPACE=/workspace \
    OPENAI_API_BASE=http://127.0.0.1:8000/v1 \
    WEBUI_PORT=8090 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /workspace

# 1) Paquetes base (incluye libs para OpenCV que algunos parsers usan)
RUN apt-get update && apt-get install -y --no-install-recommends \
      software-properties-common \
      curl ca-certificates git bash tini wget gnupg \
      build-essential \
      libgl1 libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# 2) Python 3.11
RUN add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y --no-install-recommends \
      python3.11 python3.11-venv python3.11-dev \
  && rm -rf /var/lib/apt/lists/*

# 3) Virtualenv y toolchain básico de pip
RUN python3.11 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel

# 4) Torch con CUDA 12.1 (instalado aparte para evitar conflictos del resolver)
RUN /opt/venv/bin/pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.4.1 torchvision==0.19.1

# 5) Resto de dependencias del proyecto (sin torch/torchvision)
COPY requirements.txt /workspace/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /workspace/requirements.txt

# 6) Usuario no-root y directorios de datos
RUN useradd -m app && chown -R app:app /workspace && \
    mkdir -p /data/docs /data/chroma && chown -R app:app /data

# 7) Scripts del proyecto
COPY --chown=app:app start.sh /workspace/start.sh
COPY --chown=app:app ingest.py /workspace/ingest.py
COPY --chown=app:app search.py /workspace/search.py
RUN chmod +x /workspace/start.sh

USER app
EXPOSE 8000 8090

ENTRYPOINT ["/usr/bin/tini","-g","--"]
CMD ["/workspace/start.sh"]
