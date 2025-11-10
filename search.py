import sys
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

CHROMA_DIR = "/data/chroma"
COLLECTION_NAME = "docs"
EMBED_MODEL_NAME = "BAAI/bge-m3"

def search(query: str, top_k: int = 5):
    model = SentenceTransformer(EMBED_MODEL_NAME)
    emb = model.encode([query], normalize_embeddings=True).tolist()
    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(allow_reset=False))
    coll = client.get_or_create_collection(COLLECTION_NAME)
    res = coll.query(query_embeddings=emb, n_results=top_k, include=["documents", "metadatas", "distances", "ids"])
    return res

def pretty_print(res):
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    ids   = res.get("ids", [[]])[0]

    for i, (doc, meta, dist, _id) in enumerate(zip(docs, metas, dists, ids), 1):
        loc = meta.get("path", "?")
        p   = meta.get("page", None)
        t   = meta.get("type", "?")
        where = f"{loc}" + (f" [p.{p}]" if p else "")
        print(f"\n[{i}] score={1 - dist:.4f}  ({t})  {where}")
        print("-"*80)
        print(doc[:600] + ("..." if len(doc) > 600 else ""))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python search.py \"tu consulta\"", file=sys.stderr)
        sys.exit(1)
    q = " ".join(sys.argv[1:])
    res = search(q, top_k=5)
    pretty_print(res)
