import os
import sys
from typing import List, Dict, Any, Optional

import requests
from requests import RequestException

from search import search_docs

VLLM_API_URL = os.getenv("VLLM_API_URL", "http://127.0.0.1:8000/v1/chat/completions")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
DEFAULT_AREA = os.getenv("AREA", None)


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
        "max_tokens": 512,
    }

    print(f"[RAG] Llamando a vLLM en: {VLLM_API_URL}")
    print(f"[RAG] Modelo: {VLLM_MODEL_NAME}")

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
