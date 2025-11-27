import os
import sys
from typing import List, Dict, Any, Optional

import requests
from requests import RequestException

from search import search_docs

# ==========================
# Configuración del modelo
# ==========================

# Endpoint de vLLM (OpenAI compatible)
VLLM_API_URL = os.getenv(
    "VLLM_API_URL",
    "http://127.0.0.1:8000/v1/chat/completions"
)

# Nombre del modelo tal como lo ve vLLM
VLLM_MODEL_NAME = os.getenv(
    "VLLM_MODEL_NAME",
    "Qwen/Qwen2.5-7B-Instruct"
)

# Área por defecto (opcional), se puede setear en ENV AREA=logistica, etc.
DEFAULT_AREA = os.getenv("AREA", None)


def build_context(
    query: str,
    top_k: int = 5,
    area: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Usa search_docs() para traer contexto desde Chroma y lo concatena en un string.
    Respeta el área (logistica, ventas, sistemas, etc.).
    Regresa también los 'sources' para debug.
    """
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

        source_info = {
            "path": meta.get("path"),
            "type": meta.get("type"),
            "sheet": meta.get("sheet"),
            "distance": distance,
            "preview": text[:200],
        }

        if "source" in meta:
            source_info["source"] = meta["source"]

        sources.append(source_info)

    context = "\n\n---\n\n".join(chunks)

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
    """
    Llama al modelo Qwen vía API vLLM usando el contexto como soporte.
    """

    system_prompt = (
        "Eres un asistente experto que responde ÚNICAMENTE con base en la "
        "información del contexto proporcionado. "
        "Si la respuesta no está en el contexto, dilo claramente. "
        "Si la pregunta está fuera del ámbito del área de trabajo, también indícalo."
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
        "max_tokens": 512,
    }

    print(f"[RAG] Llamando a vLLM en: {VLLM_API_URL}")
    print(f"[RAG] Modelo: {VLLM_MODEL_NAME}")

    try:
        resp = requests.post(VLLM_API_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except RequestException as e:
        # Log para debug en servidor
        print(f"[RAG] ERROR al llamar a vLLM: {e}", file=sys.stderr)
        # Mensaje claro para el usuario / capa superior
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
    """
    Flujo completo:
      1) Buscar contexto en Chroma (respetando el área).
      2) Llamar a Qwen con ese contexto usando vLLM.
      3) Regresar respuesta + contexto + fuentes + área.
    """
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


if __name__ == "__main__":
    """
    Uso desde consola:

      python rag_core.py
        → usa pregunta por defecto y área por defecto (ENV AREA)

      python rag_core.py "pregunta"
        → usa esa pregunta y área por defecto

      python rag_core.py "pregunta" logistica
        → usa esa pregunta y área 'logistica'
    """
    if len(sys.argv) >= 2:
        q = sys.argv[1]
    else:
        q = "¿Qué prompts recomienda el área comercial para ventas y servicio?"

    area_arg: Optional[str] = sys.argv[2] if len(sys.argv) >= 3 else None

    print(f"[RAG] Pregunta: {q}")
    if area_arg:
        print(f"[RAG] Área CLI: {area_arg}")
    elif DEFAULT_AREA:
        print(f"[RAG] Área por defecto (ENV): {DEFAULT_AREA}")
    else:
        print("[RAG] Sin área (modo global).")

    print(f"[RAG] VLLM_API_URL = {VLLM_API_URL}")
    print(f"[RAG] VLLM_MODEL_NAME = {VLLM_MODEL_NAME}")

    result = answer_with_rag(q, top_k=5, area=area_arg)

    print("\n=== RESPUESTA ===\n")
    print(result["answer"])

    print("\n=== ÁREA USADA ===\n")
    print(result["area"])

    print("\n=== FUENTES ===\n")
    for s in result["sources"]:
        print(s)
