import os
import sys
from typing import List, Dict, Any, Optional

import chromadb
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")

BASE_CHROMA_DIR = os.getenv("CHROMA_DIR", "/data/chroma")

BASE_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "docs")

DEFAULT_AREA = os.getenv("AREA", None)


print(f"[SEARCH] Usando embeddings: {EMBEDDING_MODEL_NAME}")
print(f"[SEARCH] Chroma base dir: {BASE_CHROMA_DIR}")
print(f"[SEARCH] Colección base: {BASE_COLLECTION_NAME}")
if DEFAULT_AREA:
    print(f"[SEARCH] Área por defecto (entorno): {DEFAULT_AREA}")
else:
    print("[SEARCH] Sin área por defecto (modo global).")


_embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)


def _get_collection(area: Optional[str] = None):
    """
    Devuelve la colección de Chroma para el área indicada.
    - Si area es None → usa modo 'global' (ruta base + colección base).
    - Si area tiene valor → usa subcarpeta y colección por área:
        path = BASE_CHROMA_DIR / area
        collection_name = BASE_COLLECTION_NAME + "_" + area
    """
    if area:
        chroma_dir = os.path.join(BASE_CHROMA_DIR, area)
        collection_name = f"{BASE_COLLECTION_NAME}_{area}"
    else:
        chroma_dir = BASE_CHROMA_DIR
        collection_name = BASE_COLLECTION_NAME

    client = chromadb.PersistentClient(path=chroma_dir)
    return client.get_or_create_collection(name=collection_name)


def search_docs(query: str, top_k: int = 5, area: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Hace búsqueda semántica en Chroma y regresa una lista de resultados:
    [
      {
        "text": <chunk>,
        "metadata": <dict>,
        "distance": <float>
      },
      ...
    ]

    :param query: texto de la pregunta
    :param top_k: número de resultados a devolver
    :param area: nombre del área (logistica, ventas, sistemas, etc.).
                 Si es None, se usa DEFAULT_AREA y si tampoco hay, se va al modo global.
    """
    if area is None:
        area = DEFAULT_AREA

    collection = _get_collection(area)

    print(f"[SEARCH] Consulta en área: {area if area else '(global)'}")
    emb = _embedder.encode([query]).tolist()

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
        results.append(
            {
                "text": doc,
                "metadata": meta if isinstance(meta, dict) else {},
                "distance": float(dist),
            }
        )
    return results


def pretty_print_results(results: List[Dict[str, Any]]) -> None:
    for i, r in enumerate(results, start=1):
        print(f"\n=== Resultado #{i} (distancia: {r['distance']:.4f}) ===")
        fuente = r["metadata"].get("source")
        if fuente:
            print(f"Fuente: {fuente}")
        print(r["text"][:1000])  # solo los primeros caracteres


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
    pretty_print_results(results)
