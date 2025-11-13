import os
import sys
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer

# Debe ser el MISMO modelo que usaste en ingest.py
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")

# Ruta donde ingest.py guarda la BD Chroma
CHROMA_DIR = os.getenv("CHROMA_DIR", "/data/chroma")

# IMPORTANTE: debe ser el mismo nombre de colección que uses en ingest.py
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "docs")


# ===========================
# 1. Inicialización global
# ===========================

print(f"[SEARCH] Usando embeddings: {EMBEDDING_MODEL_NAME}")
print(f"[SEARCH] Usando Chroma en: {CHROMA_DIR}")
print(f"[SEARCH] Colección: {COLLECTION_NAME}")

_embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
_client = chromadb.PersistentClient(path=CHROMA_DIR)
_collection = _client.get_or_create_collection(name=COLLECTION_NAME)


# ===========================
# 2. Función principal de búsqueda
# ===========================

def search_docs(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
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
    """
    emb = _embedder.encode([query]).tolist()

    res = _collection.query(
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


# ===========================
# 3. Modo consola (para pruebas)
# ===========================

def pretty_print_results(results: List[Dict[str, Any]]) -> None:
    for i, r in enumerate(results, start=1):
        print(f"\n=== Resultado #{i} (distancia: {r['distance']:.4f}) ===")
        fuente = r["metadata"].get("source")
        if fuente:
            print(f"Fuente: {fuente}")
        print(r["text"][:1000])  # solo los primeros caracteres


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python search.py "tu pregunta aquí"')
        sys.exit(1)

    q = sys.argv[1]
    print(f"[SEARCH] Consulta: {q}")
    results = search_docs(q, top_k=5)
    pretty_print_results(results)
