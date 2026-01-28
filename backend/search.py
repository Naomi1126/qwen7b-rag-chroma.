import os
import sys
from typing import List, Dict, Any, Optional, Tuple

import chromadb
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
HF_HOME = os.getenv("HF_HOME", "/workspace/hf")

BASE_CHROMA_DIR = os.getenv("CHROMA_DIR", "/data/chroma")
BASE_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "docs")

DEFAULT_AREA = os.getenv("AREA", None)

print(f"[SEARCH] Usando embeddings: {EMBEDDING_MODEL_NAME}")
print(f"[SEARCH] Dispositivo embeddings: {EMBEDDING_DEVICE}")
print(f"[SEARCH] HF_HOME (cache): {HF_HOME}")
print(f"[SEARCH] Chroma base dir: {BASE_CHROMA_DIR}")
print(f"[SEARCH] Colección base: {BASE_COLLECTION_NAME}")
if DEFAULT_AREA:
    print(f"[SEARCH] Área por defecto (entorno): {DEFAULT_AREA}")
else:
    print("[SEARCH] Sin área por defecto (modo global).")

_embedder: Optional[SentenceTransformer] = None
_collection_cache: Dict[Tuple[str, str], Any] = {}


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        print(
            f"[SEARCH] Cargando modelo de embeddings '{EMBEDDING_MODEL_NAME}' "
            f"en dispositivo: {EMBEDDING_DEVICE}"
        )
        _embedder = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            device=EMBEDDING_DEVICE,
            cache_folder=HF_HOME,
        )
    return _embedder


def _get_collection(area: Optional[str] = None):
    """
    - Si area es None → modo global:
        path = BASE_CHROMA_DIR
        collection_name = BASE_COLLECTION_NAME
    - Si area tiene valor → subcarpeta y colección por área:
        path = BASE_CHROMA_DIR / area
        collection_name = BASE_COLLECTION_NAME + "_" + area
    """
    if area:
        chroma_dir = os.path.join(BASE_CHROMA_DIR, area)
        collection_name = f"{BASE_COLLECTION_NAME}_{area}"
    else:
        chroma_dir = BASE_CHROMA_DIR
        collection_name = BASE_COLLECTION_NAME

    key = (chroma_dir, collection_name)
    if key in _collection_cache:
        return _collection_cache[key]

    client = chromadb.PersistentClient(path=chroma_dir)
    coll = client.get_or_create_collection(name=collection_name)
    _collection_cache[key] = coll
    return coll


def list_indexed_areas() -> List[str]:
    """
    Devuelve las áreas detectadas por subcarpetas en BASE_CHROMA_DIR.
    Ej: /data/chroma/logistica, /data/chroma/sistemas, ...
    """
    try:
        if not os.path.isdir(BASE_CHROMA_DIR):
            return []
        out: List[str] = []
        for name in sorted(os.listdir(BASE_CHROMA_DIR)):
            p = os.path.join(BASE_CHROMA_DIR, name)
            if os.path.isdir(p) and not name.startswith("."):
                out.append(name)
        return out
    except Exception:
        return []


def search_docs(query: str, top_k: int = 5, area: Optional[str] = None) -> List[Dict[str, Any]]:
    if area is None:
        area = DEFAULT_AREA

    collection = _get_collection(area)

    print(f"[SEARCH] Consulta en área: {area if area else '(global)'}")
    embedder = _get_embedder()

    emb = embedder.encode([query], normalize_embeddings=True).tolist()

    res = collection.query(
        query_embeddings=emb,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    results: List[Dict[str, Any]] = []
    for doc, meta, dist in zip(docs, metas, dists):
        m = meta if isinstance(meta, dict) else {}
        # Asegura que el resultado tenga "area" si venía en metadata
        results.append(
            {
                "text": doc,
                "metadata": m,
                "distance": float(dist),
            }
        )
    return results


def search_docs_multi(query: str, top_k: int = 5, areas: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Busca en múltiples áreas y mezcla resultados ordenando por distancia.
    """
    if areas is None:
        areas = list_indexed_areas()

    if not areas:
        # fallback: intenta área por defecto, si existe
        return search_docs(query, top_k=top_k, area=DEFAULT_AREA)

    all_results: List[Dict[str, Any]] = []
    # Pedimos un poco más por área y luego recortamos
    per_area_k = max(top_k, 5)

    for a in areas:
        try:
            rs = search_docs(query, top_k=per_area_k, area=a)
            for r in rs:
                meta = r.get("metadata") or {}
                if "area" not in meta:
                    meta["area"] = a
                r["metadata"] = meta
            all_results.extend(rs)
        except Exception as e:
            print(f"[SEARCH] WARN: falló búsqueda en área '{a}': {e}", file=sys.stderr)

    # Ordena globalmente por distancia (menor = más cercano)
    all_results.sort(key=lambda x: x.get("distance", 1e9))
    return all_results[:top_k]


def pretty_print_results(results: List[Dict[str, Any]]) -> None:
    for i, r in enumerate(results, start=1):
        dist = r.get("distance", 0.0)
        meta = r.get("metadata", {}) or {}
        area = meta.get("area")
        print(f"\n=== Resultado #{i} (distancia: {dist:.4f}) area={area} ===")
        fuente = meta.get("source") or meta.get("path")
        if fuente:
            print(f"Fuente: {fuente}")
        print(r["text"][:1000])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python search.py "tu pregunta aquí" [area]')
        sys.exit(1)

    q = sys.argv[1]
    area_arg: Optional[str] = sys.argv[2] if len(sys.argv) >= 3 else None

    print(f"[SEARCH] Consulta: {q}")
    if area_arg:
        print(f"[SEARCH] Área CLI: {area_arg}")
        results = search_docs(q, top_k=5, area=area_arg)
    else:
        results = search_docs_multi(q, top_k=5)

    pretty_print_results(results)
