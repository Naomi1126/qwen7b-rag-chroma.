import os
import sys
from typing import List, Dict, Any, Optional

import requests
from requests import RequestException

from search import search_docs

# ---------------------------
# Configuración de vLLM / modelo
# ---------------------------

# Endpoint OpenAI-compatible de vLLM
VLLM_API_URL = os.getenv(
    "VLLM_API_URL",
    "http://127.0.0.1:8000/v1/chat/completions",
)

# Modelo por defecto: volvemos a Qwen2-7B-Instruct
VLLM_MODEL_NAME = os.getenv(
    "VLLM_MODEL_NAME",
    "Qwen/Qwen2-7B-Instruct",
)

# Área por defecto (opcional, se puede usar a nivel entorno)
DEFAULT_AREA = os.getenv("AREA", None)

# Límite de caracteres de contexto para ahorrar memoria en GPU
# (puedes ajustar por variable de entorno RAG_MAX_CONTEXT_CHARS)
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))

# Límite de tokens de salida del modelo
MAX_COMPLETION_TOKENS = int(os.getenv("RAG_MAX_COMPLETION_TOKENS", "512"))


def build_context(
    query: str,
    top_k: int = 5,
    area: Optional[str] = None,
) -> Dict[str, Any]:
    if area is None:
        area = DEFAULT_AREA

    print(f"[RAG] build_context() → área usada: {area if area else '(global)'}")
    print(f"[RAG] top_k = {top_k}")

    results = search_docs(query, top_k=top_k, area=area)

    chunks: List[str] = []
    sources: List[Dict[str, Any]] = []

    for r in results:
        text = r["text"]
        meta = r.get("metadata", {}) or {}
        distance = r.get("distance")

        chunks.append(text)

        source_info: Dict[str, Any] = {
            "path": meta.get("path"),
            "type": meta.get("type"),
            "sheet": meta.get("sheet"),
            "row": meta.get("row"),
            "page": meta.get("page"),
            "distance": float(distance) if distance is not None else None,
            "preview": text[:200],
        }

        if "source" in meta:
            source_info["source"] = meta["source"]

        sources.append(source_info)

    # ---------------------------
    # Construcción de contexto con límite de longitud
    # para evitar prompts gigantes que saturen la GPU
    # ---------------------------
    sep = "\n\n---\n\n"
    context_parts: List[str] = []
    current_len = 0

    for chunk in chunks:
        # Longitud que añadiría este chunk (incluyendo separador si no es el primero)
        extra_len = len(chunk) + (len(sep) if context_parts else 0)

        if current_len + extra_len > MAX_CONTEXT_CHARS:
            # Todavía cabe una parte del chunk
            remaining = MAX_CONTEXT_CHARS - current_len
            if remaining > 0:
                context_parts.append(chunk[:remaining])
                current_len += remaining
            print(
                f"[RAG] Contexto truncado a {MAX_CONTEXT_CHARS} caracteres "
                f"para ahorrar memoria."
            )
            break

        context_parts.append(chunk)
        current_len += extra_len

    context = sep.join(context_parts)

    return {
        "context": context,
        "sources": sources,
        "area": area,
    }


def call_model_with_context(
    user_query: str,
    context: str,
    area: Optional[str] = None,
) -> str:
    if not context.strip():
        return (
            "No encontré información relevante en los documentos indexados "
            "para responder esta pregunta."
        )

    system_prompt = (
        "Eres un asistente experto que responde ÚNICAMENTE con base en la "
        "información del contexto proporcionado. "
        "Si la respuesta no está en el contexto, dilo claramente. "
        "Si la pregunta está fuera del ámbito del área de trabajo, también indícalo.\n\n"
        "En el contexto pueden aparecer datos provenientes de hojas de cálculo. "
        "Cada fila de Excel se representa típicamente como:\n"
        "'Hoja: NOMBRE_HOJA | Fila: NUMERO | Columna1: valor | Columna2: valor | ...'.\n"
        "Interpreta correctamente filas y columnas para contestar con precisión, "
        "mencionando la hoja e idealmente la fila cuando sea relevante."
    )

    area_text = f"(Área: {area})\n\n" if area else ""

    user_content = (
        f"{area_text}"
        f"Contexto de soporte (extraído de documentos internos):\n\n"
        f"{context}\n\n"
        f"Pregunta del usuario:\n{user_query}\n\n"
        f"Si la información no está en el contexto, responde que no está disponible."
    )

    payload = {
        "model": VLLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": MAX_COMPLETION_TOKENS,
    }

    print(f"[RAG] Llamando a vLLM en: {VLLM_API_URL}")
    print(f"[RAG] Modelo: {VLLM_MODEL_NAME}")
    print(f"[RAG] max_tokens: {MAX_COMPLETION_TOKENS}")
    print(f"[RAG] Longitud de contexto: {len(context)} caracteres")

    try:
        resp = requests.post(VLLM_API_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except RequestException as e:
        print(f"[RAG] ERROR al llamar a vLLM: {e}", file=sys.stderr)
        raise RuntimeError(f"Error al llamar al modelo vLLM: {e}") from e

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        print(f"[RAG] Respuesta inesperada de vLLM: {data}", file=sys.stderr)
        raise RuntimeError(f"Formato de respuesta inválido desde vLLM: {e}") from e


def answer_with_rag(
    user_query: str,
    top_k: int = 5,
    area: Optional[str] = None,
) -> Dict[str, Any]:
    print(f"[RAG] answer_with_rag() → query: {user_query}")
    print(f"[RAG] Área solicitada: {area if area else '(sin especificar)'}")

    ctx = build_context(user_query, top_k=top_k, area=area)
    context = ctx["context"]
    sources = ctx["sources"]
    used_area = ctx["area"]

    answer = call_model_with_context(user_query, context, area=used_area)

    return {
        "answer": answer,
        "context": context,
        "sources": sources,
        "area": used_area,
    }
