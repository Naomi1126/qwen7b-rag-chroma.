set -euo pipefail

# Variables de entorno base
: "${MODEL:=Qwen/Qwen2.5-7B-Instruct}"
: "${HF_HOME:=/workspace/hf}"
: "${MAX_MODEL_LEN:=4096}"
: "${GPU_MEM_UTIL:=0.6}"
: "${SWAP_SPACE_GB:=20}"

# vLLM OpenAI-like
: "${OPENAI_API_KEY:=dummy-key}"
: "${OPENAI_API_BASE:=http://127.0.0.1:8000/v1}"

# FastAPI RAG
: "${RAG_API_PORT:=9001}"

# rag_core.py
: "${VLLM_API_URL:=http://127.0.0.1:8000/v1/chat/completions}"
: "${VLLM_MODEL_NAME:=${MODEL}}"

# Admin defaults
: "${ADMIN_EMAIL:=admin@comarket.com}"
: "${ADMIN_PASSWORD:=1234}"
: "${ADMIN_NAME:=Administrador}"

export OPENAI_API_KEY OPENAI_API_BASE
export VLLM_API_URL VLLM_MODEL_NAME
export BACKEND_URL="http://127.0.0.1:${RAG_API_PORT}"
export HF_HOME
export ADMIN_EMAIL ADMIN_PASSWORD ADMIN_NAME

echo "[start] Configuración:"
echo "  MODEL=${MODEL}"
echo "  HF_HOME=${HF_HOME}"
echo "  MAX_MODEL_LEN=${MAX_MODEL_LEN}"
echo "  GPU_MEM_UTIL=${GPU_MEM_UTIL}"
echo "  SWAP_SPACE_GB=${SWAP_SPACE_GB}"
echo "  OPENAI_API_BASE=${OPENAI_API_BASE}"
echo "  VLLM_API_URL=${VLLM_API_URL}"
echo "  VLLM_MODEL_NAME=${VLLM_MODEL_NAME}"
echo "  BACKEND_URL=${BACKEND_URL}"
echo "  ADMIN_EMAIL=${ADMIN_EMAIL}"

echo "[start] Activando entorno virtual /opt/venv"
source /opt/venv/bin/activate

# Evitar duplicados si reinicias dentro del mismo contenedor
pkill -f "vllm serve" 2>/dev/null || true
pkill -f "uvicorn app:app" 2>/dev/null || true
pkill -f "python.*app_gradio.py" 2>/dev/null || true

# 1) Lanzar vLLM
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
  --guided-decoding-backend "none" \
  > /workspace/log_vllm.log 2>&1 &

VLLM_PID=$!
echo "[start] vLLM PID=${VLLM_PID} en :8000"

echo "[start] Esperando a que vLLM responda en :8000 ..."
VLLM_READY="0"
for i in {1..180}; do
  if curl -sSf http://127.0.0.1:8000/v1/models \
       -H "Authorization: Bearer ${OPENAI_API_KEY}" >/dev/null 2>&1; then
    echo "[start] vLLM listo."
    VLLM_READY="1"
    break
  fi
  sleep 1
done

if [ "${VLLM_READY}" != "1" ]; then
  echo "[start] ERROR: vLLM no levantó en 180s. Revisa /workspace/log_vllm.log"
  exit 1
fi

# 2) Inicializar DB: áreas y admin
echo "[start] Inicializando áreas..."
/opt/venv/bin/python /workspace/init_areas.py > /workspace/log_init_areas.log 2>&1 || true

echo "[start] Inicializando/asegurando usuario admin..."
/opt/venv/bin/python /workspace/init_admin.py > /workspace/log_init_admin.log 2>&1 || true

# 3) Lanzar API RAG (FastAPI)
echo "[start] Lanzando API RAG (FastAPI) en :${RAG_API_PORT}"
/opt/venv/bin/uvicorn app:app \
  --host 0.0.0.0 \
  --port "${RAG_API_PORT}" \
  > /workspace/log_rag_api.log 2>&1 &

API_PID=$!
echo "[start] FastAPI PID=${API_PID} en :${RAG_API_PORT}"

# 4) Lanzar frontend Gradio
echo "[start] Lanzando frontend Gradio en :7860"
export GRADIO_SERVER_NAME="0.0.0.0"
export GRADIO_SERVER_PORT="7860"
export GRADIO_ANALYTICS_ENABLED="False"

/opt/venv/bin/python /workspace/app_gradio.py \
  > /workspace/log_gradio.log 2>&1 &

GRADIO_PID=$!
echo "[start] Gradio PID=${GRADIO_PID} en :7860"

echo "[start] Todos los servicios lanzados. Esperando que alguno termine..."
wait -n
