#!/usr/bin/env bash
set -euo pipefail

# ==========================
# Variables de entorno base
# ==========================
: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
: "${HF_HOME:=/workspace/hf}"
: "${MAX_MODEL_LEN:=4096}"
: "${GPU_MEM_UTIL:=0.75}"
: "${SWAP_SPACE_GB:=20}"

# Compat con Open-WebUI / clientes OpenAI-like
: "${OPENAI_API_KEY:=dummy}"
: "${OPENAI_API_BASE:=http://127.0.0.1:8000/v1}"

# Puerto del WebUI (lo dejamos desactivado por ahora)
: "${WEBUI_PORT:=8090}"

# Para el backend RAG (FastAPI)
: "${RAG_API_PORT:=9001}"

# Para rag_core.py
: "${VLLM_API_URL:=http://127.0.0.1:8000/v1/chat/completions}"
: "${VLLM_MODEL_NAME:=${MODEL}}"

# Puerto de AnythingLLM
: "${ANYTHINGLLM_PORT:=3001}"

export OPENAI_API_KEY OPENAI_API_BASE
export VLLM_API_URL VLLM_MODEL_NAME

echo "[start] Activando entorno virtual /opt/venv"
source /opt/venv/bin/activate

# ==========================
# 1) Lanzar vLLM
# ==========================
echo "[start] Lanzando vLLM con modelo: ${MODEL}"
/opt/venv/bin/vllm serve "${MODEL}" \
  --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 1 \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEM_UTIL}" \
  --swap-space "${SWAP_SPACE_GB}" \
  --download-dir "${HF_HOME}" \
  --dtype auto \
  --api-key "${OPENAI_API_KEY}" \
  > /workspace/log_vllm.log 2>&1 &

echo "[start] Esperando a que vLLM responda en :8000 ..."
for i in {1..120}; do
  if curl -sSf http://127.0.0.1:8000/v1/models >/dev/null 2>&1; then
    echo "[start] vLLM listo."
    break
  fi
  sleep 1
done

# ==========================
# 2) Lanzar API RAG (FastAPI)
# ==========================
echo "[start] Lanzando API RAG (FastAPI) en :${RAG_API_PORT}"
/opt/venv/bin/uvicorn app:app \
  --host 0.0.0.0 \
  --port "${RAG_API_PORT}" \
  > /workspace/log_rag_api.log 2>&1 &

# ==========================
# 3) Lanzar AnythingLLM (server + collector)
# ==========================
echo "[start] Lanzando AnythingLLM server en :${ANYTHINGLLM_PORT}"
/usr/bin/env bash -c 'cd /workspace/anything-llm/server && NODE_ENV=production node index.js' \
  > /workspace/log_anything_server.log 2>&1 &

echo "[start] Lanzando AnythingLLM collector"
/usr/bin/env bash -c 'cd /workspace/anything-llm/collector && NODE_ENV=production node index.js' \
  > /workspace/log_anything_collector.log 2>&1 &

# ==========================
# 4) Open-WebUI (OPCIONAL - desactivado)
# ==========================
# echo "[start] Open-WebUI en :${WEBUI_PORT} (apunta a ${OPENAI_API_BASE})"
# /opt/venv/bin/open-webui serve \
#   --host 0.0.0.0 \
#   --port "${WEBUI_PORT}"

# Mantener el contenedor vivo
tail -f /dev/null
