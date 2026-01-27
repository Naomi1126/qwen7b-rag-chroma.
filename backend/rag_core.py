import os
import sys
import re
import unicodedata
from typing import List, Dict, Any, Optional

import requests
from requests import RequestException

from search import search_docs, search_exact

VLLM_API_URL = os.getenv("VLLM_API_URL", "http://127.0.0.1:8000/v1/chat/completions")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "dummy-key")

DEFAULT_AREA = (os.getenv("AREA", "general") or "general").strip()

MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000"))
MAX_COMPLETION_TOKENS = int(os.getenv("RAG_MAX_COMPLETION_TOKENS", "512"))

ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Aria")

_SMALLTALK_PATTERNS = [
    r"^hola$",
    r"^buenas$",
    r"^hey$",
    r"^hello$",
    r"^hi$",
    r"^buenos dias$",
    r"^buenos días$",
    r"^buenas tardes$",
    r"^buenas noches$",
    r"^holi$",
]

# Detecta contenedores comunes. Agrega prefijos si tu operación usa otros.
CONTAINER_RE = re.compile(r"\b(?:MSMU|BMOU|TGHU|CAIU|MSCU|OOLU|TEMU)[A-Z0-9]{6,}\b", re.I)


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_area(area: Optional[str]) -> Optional[str]:
    if not area:
        return None
    a = area.strip().lower()
    a = unicodedata.normalize("NFKD", a).encode("ascii", "ignore").decode("ascii")
    a = a.replace(" ", "_")
    return a or None


def is_greeting(query: str) -> bool:
    q = _normalize(query)
    return any(re.match(p, q) for p in _SMALLTALK_PATTERNS)


def detect_exact_lookup(query: str) -> Optional[Dict[str, str]]:
    """
    Si hay un ID claro (contenedor), hacemos lookup exacto por metadata.
    Puedes extender luego a factura/remisión/pi si quieres.
    """
    m = CONTAINER_RE.search(query)
    if m:
        return {"field": "contenedor", "value": m.group(0).upper()}
    return None


def build_context(query: str, top_k: int = 5, area: Optional[str] = None) -> Dict[str, Any]:
    area_norm = normalize_area(area) or normalize_area(DEFAULT_AREA) or "general"

    print(f"[RAG] build_context() → área usada: {area_norm}")
    print(f"[RAG] top_k = {top_k}")

    exact = detect_exact_lookup(query)
    if exact:
        print(f"[RAG] Detectado ID exacto → {exact['field']}={exact['value']}")
        results = search_exact(exact["field"], exact["value"], top_k=max(top_k, 50), area=area_norm)
        if not results:
            print("[RAG] Exact lookup sin resultados → fallback a embeddings")
            results = search_docs(query, top_k=top_k, area=area_norm)
    else:
        results = search_docs(query, top_k=top_k, area=area_norm)

    chunks: List[str] = []
    sources: List[Dict[str, Any]] = []

    for r in results:
        text = r["text"]
        meta = r.get("metadata", {}) or {}
        distance = r.get("distance")

        chunks.append(text)

        sources.append(
            {
                "path": meta.get("path"),
                "type": meta.get("type"),
                "sheet": meta.get("sheet"),
                "row": meta.get("row"),
                "page": meta.get("page"),
                "distance": float(distance) if distance is not None else None,
                "preview": text[:200],
            }
        )

    sep = "\n\n---\n\n"
    context_parts: List[str] = []
    current_len = 0

    for chunk in chunks:
        extra_len = len(chunk) + (len(sep) if context_parts else 0)

        if current_len + extra_len > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - current_len
            if remaining > 0:
                context_parts.append(chunk[:remaining])
                current_len += remaining
            print(f"[RAG] Contexto truncado a {MAX_CONTEXT_CHARS} caracteres.")
            break

        context_parts.append(chunk)
        current_len += extra_len

    context = sep.join(context_parts)

    return {"context": context, "sources": sources, "area": area_norm}


def call_model_with_context(user_query: str, context: str, area: Optional[str] = None) -> str:
    if is_greeting(user_query):
        return f"¡Hola! Soy {ASSISTANT_NAME}. ¿En qué puedo ayudarte hoy?"

    if not context.strip():
        area_hint = f" del área **{area}**" if area else ""
        return (
            f"No encontré información{area_hint} en los documentos para responder eso todavía.\n\n"
            "Para ayudarte mejor, dime una de estas opciones:\n"
            "• ¿Qué documento o dato necesitas?\n"
        )

    system_prompt = (
        f"Eres {ASSISTANT_NAME}, un asistente virtual corporativo amable, claro y profesional.\n"
        "Reglas:\n"
        "1) Responde SOLO con base en el CONTEXTO proporcionado.\n"
        "2) Si la respuesta NO está en el contexto, dilo con tacto y pide UN solo dato faltante.\n"
        "3) Si el contexto incluye datos de Excel, NO combines datos de filas diferentes como si fueran el mismo registro.\n"
        "4) Si el contexto incluye datos de Excel, cita hoja y fila para cada dato clave.\n"
        "5) Mantén un tono cordial; evita sonar seco."
    )

    area_text = f"(Área: {area})\n\n" if area else ""

    user_content = (
        f"{area_text}"
        f"Contexto de soporte (extraído de documentos internos):\n\n"
        f"{context}\n\n"
        f"Pregunta del usuario:\n{user_query}\n\n"
        "Instrucciones:\n"
        "- Si hay varias filas, lista cada fila por separado (no combines campos entre filas).\n"
        "- Si no hay información suficiente, indícalo y pide UN solo dato faltante.\n"
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

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    print(f"[RAG] Llamando a vLLM en: {VLLM_API_URL}")
    print(f"[RAG] Modelo: {VLLM_MODEL_NAME}")
    print(f"[RAG] max_tokens: {MAX_COMPLETION_TOKENS}")
    print(f"[RAG] Longitud de contexto: {len(context)} caracteres")

    try:
        resp = requests.post(VLLM_API_URL, json=payload, headers=headers, timeout=120)
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


def answer_with_rag(user_query: str, top_k: int = 5, area: Optional[str] = None) -> Dict[str, Any]:
    print(f"[RAG] answer_with_rag() → query: {user_query}")
    print(f"[RAG] Área solicitada: {area if area else '(sin especificar)'}")

    ctx = build_context(user_query, top_k=top_k, area=area)
    context = ctx["context"]
    sources = ctx["sources"]
    used_area = ctx["area"]

    answer = call_model_with_context(user_query, context, area=used_area)

    return {"answer": answer, "context": context, "sources": sources, "area": used_area}
