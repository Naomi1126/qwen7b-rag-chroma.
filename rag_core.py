# rag_core.py
import os
from typing import List, Dict, Any

import requests
from search import search_docs

# Endpoint de vLLM (OpenAI-compatible)
VLLM_API_URL = os.getenv("VLLM_API_URL", "http://127.0.0.1:8000/v1/chat/completions")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "qwen")


def build_context(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Usa search_docs() para traer contexto y lo concatena en un string.
    Regresa también los 'sources' para debug.
    """
    results = search_docs(query, top_k=top_k)

    chunks: List[str] = []
    sources: List[Dict[str, Any]] = []

    for r in results:
        text = r["text"]
        meta = r.get("metadata", {})
        distance = r.get("distance")

        chunks.append(text)

        sources.append(
            {
                "source": meta.get("source"),
                "distance": distance,
                "preview": text[:200],
            }
        )

    context = "\n\n---\n\n".join(chunks)
    return {
        "context": context,
        "sources": sources,
    }


def call_model_with_context(user_query: str, context: str) -> str:
    """
    Llama al modelo Qwen vía API vLLM usando el contexto como soporte.
    """
    system_prompt = (
        "Eres un asistente experto que responde ÚNICAMENTE con base en la "
        "información del contexto proporcionado. "
        "Si la respuesta no está en el contexto, dilo claramente."
    )

    user_content = (
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

    resp = requests.post(VLLM_API_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    return data["choices"][0]["message"]["content"]


def answer_with_rag(user_query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Flujo completo:
      1) Buscar contexto en Chroma.
      2) Llamar a Qwen con ese contexto.
      3) Regresar respuesta + contexto + fuentes.
    """
    ctx = build_context(user_query, top_k=top_k)
    context = ctx["context"]
    sources = ctx["sources"]

    answer = call_model_with_context(user_query, context)

    return {
        "answer": answer,
        "context": context,
        "sources": sources,
    }


if __name__ == "__main__":
    q = "¿Qué prompts recomienda el área comercial para ventas y servicio?"
    print(f"[RAG] Pregunta: {q}")
    result = answer_with_rag(q, top_k=5)
    print("\n=== RESPUESTA ===\n")
    print(result["answer"])
    print("\n=== FUENTES ===\n")
    for s in result["sources"]:
        print(s)
