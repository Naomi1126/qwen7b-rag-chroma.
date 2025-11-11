#!/usr/bin/env bash
set -euo pipefail

: "${MODEL:=Qwen/Qwen2-14B-Instruct}"
: "${HF_HOME:=/workspace/hf}"
: "${MAX_MODEL_LEN:=16384}"
: "${GPU_MEM_UTIL:=0.90}"
: "${SWAP_SPACE_GB:=20}"
: "${OPENAI_API_KEY:=dummy}"
: "${OPENAI_API_BASE:=http://127.0.0.1:8000/v1}"
: "${WEBUI_PORT:=8090}"   # Evita choque con Jupyter (8080)

echo "[start] vLLM sirviendo modelo: ${MODEL}"
/opt/venv/bin/vllm serve "${MODEL}" \
  --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 1 \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEM_UTIL}" \
  --swap-space "${SWAP_SPACE_GB}" \
  --download-dir "${HF_HOME}" \
  --dtype auto \
  --api-key "${OPENAI_API_KEY}" &

echo "[start] esperando a vLLM en :8000 ..."
for i in {1..120}; do
  if curl -sSf http://127.0.0.1:8000/v1/models >/dev/null 2>&1; then
    echo "[start] vLLM listo."
    break
  fi
  sleep 1
done

export OPENAI_API_BASE="${OPENAI_API_BASE}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"

echo "[start] OpenWebUI en :${WEBUI_PORT} (apunta a ${OPENAI_API_BASE})"
/opt/venv/bin/open-webui serve --host 0.0.0.0 --port "${WEBUI_PORT}"
