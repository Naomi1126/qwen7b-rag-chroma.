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

# Compat con clientes OpenAI-like (vLLM)
: "${OPENAI_API_KEY:=dummy}"
: "${OPENAI_API_BASE:=http://127.0.0.1:8000/v1}"

# Puerto del backend RAG (FastAPI)
: "${RAG_API_PORT:=9001}"

# Para rag_core.py (llamadas a vLLM)
: "${VLLM_API_URL:=http://127.0.0.1:8000/v1/chat/completions}"
: "${VLLM_MODEL_NAME:=${MODEL}}"

export OPENAI_API_KEY OPENAI_API_BASE
export VLLM_API_URL VLLM_MODEL_NAME

# URL que usará Gradio para hablar con FastAPI
export BACKEND_URL="http://127.0.0.1:${RAG_API_PORT}"

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

VLLM_PID=$!
echo "[start] vLLM PID=${VLLM_PID} en :8000"

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

API_PID=$!
echo "[start] FastAPI PID=${API_PID} en :${RAG_API_PORT}"

# ==========================
# 3) Lanzar frontend Gradio
# ==========================
echo "[start] Lanzando frontend Gradio en :7860"
/opt/venv/bin/python /workspace/app_gradio.py \
  > /workspace/log_gradio.log 2>&1 &

GRADIO_PID=$!
echo "[start] Gradio PID=${GRADIO_PID} en :7860"

echo "[start] Todos los servicios lanzados. Esperando que alguno termine..."
wait -n
