FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/workspace/hf \
    VLLM_WORKSPACE=/workspace \
    VLLM_MODEL_NAME="Qwen/Qwen2.5-7B-Instruct" \
    VLLM_API_URL="http://127.0.0.1:8000/v1/chat/completions" \
    WEBUI_PORT=8090 \
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

# 3b) Node.js 18 + Yarn (para AnythingLLM)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get update && apt-get install -y nodejs && \
    npm install -g yarn

# 4) Torch + vLLM + pyairports (¡muy importante el orden!)
RUN /opt/venv/bin/pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.4.0 torchvision==0.19.0 && \
    /opt/venv/bin/pip install --no-cache-dir \
    vllm==0.6.0 outlines==0.0.46 pyairports==0.0.1

# 5) Open-WebUI (lo dejamos instalado aunque no lo lancemos por defecto)
RUN /opt/venv/bin/pip install --no-cache-dir open-webui==0.3.25

# 6) Dependencias de TU proyecto Python
COPY requirements.txt /workspace/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /workspace/requirements.txt

# >>> NUEVO: instalar libs útiles si aún no están en requirements.txt
# (Puedes quitarlas de aquí si ya las agregaste a requirements.txt)
RUN /opt/venv/bin/pip install --no-cache-dir \
    "python-jose[cryptography]" \
    "passlib[bcrypt]" \
    pandas \
    openpyxl

# 6b) AnythingLLM bare-metal
RUN git clone https://github.com/Mintplex-Labs/anything-llm.git /workspace/anything-llm && \
    cd /workspace/anything-llm && \
    yarn setup && \
    cp server/.env.example server/.env && \
    mkdir -p /workspace/anything-llm/storage && \
    echo 'STORAGE_DIR=/workspace/anything-llm/storage' >> server/.env && \
    cd frontend && yarn build && cd .. && \
    rm -rf server/public && cp -R frontend/dist server/public && \
    cd server && npx prisma generate --schema=./prisma/schema.prisma && \
    npx prisma migrate deploy --schema=./prisma/schema.prisma

# 7) Limpieza para reducir tamaño
RUN apt-get purge -y build-essential python3.11-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

# 8) Usuario no-root + directorios de datos
RUN useradd -m app && chown -R app:app /workspace && \
    mkdir -p /data/docs /data/chroma && chown -R app:app /data

# 9) Código del proyecto
COPY --chown=app:app start.sh /workspace/start.sh
COPY --chown=app:app ingest.py /workspace/ingest.py
COPY --chown=app:app search.py /workspace/search.py
COPY --chown=app:app app.py /workspace/app.py
COPY --chown=app:app rag_core.py /workspace/rag_core.py
COPY --chown=app:app auth.py /workspace/auth.py
COPY --chown=app:app models.py /workspace/models.py
COPY --chown=app:app database.py /workspace/database.py

RUN chmod +x /workspace/start.sh /workspace/ingest.py /workspace/search.py /workspace/app.py /workspace/rag_core.py

USER app

EXPOSE 8000 8090 3001 9001

ENTRYPOINT ["/workspace/start.sh"]
