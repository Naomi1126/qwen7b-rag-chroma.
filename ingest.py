import os, sys, hashlib
from pathlib import Path
from typing import List, Dict

# Extracción
import fitz  # PyMuPDF
import docx
import openpyxl

# Embeddings y vector DB
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

DATA_DIR = Path("/data/docs")
CHROMA_DIR = "/data/chroma"
COLLECTION_NAME = "docs"
EMBED_MODEL_NAME = "BAAI/bge-m3"  # densa por defecto

def file_sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> List[str]:
    text = text.strip().replace("\r", "")
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        cut = text.rfind("\n", start, end)
        if cut == -1 or cut <= start + 200:
            cut = end
        seg = text[start:cut].strip()
        if seg:
            chunks.append(seg)
        if cut >= n:
            break
        start = max(cut - overlap, 0)
        if start == cut:
            start += 1
    return chunks

def extract_pdf(p: Path) -> List[Dict]:
    out = []
    with fitz.open(p) as doc:
        for i, page in enumerate(doc):
            txt = page.get_text("text")
            for j, ch in enumerate(chunk_text(txt)):
                out.append({
                    "text": ch,
                    "metadata": {"path": str(p), "type": "pdf", "page": i+1, "chunk": j}
                })
    return out

def extract_docx(p: Path) -> List[Dict]:
    d = docx.Document(str(p))
    txt = "\n".join([para.text for para in d.paragraphs])
    return [{"text": ch, "metadata": {"path": str(p), "type": "docx"}} for ch in chunk_text(txt)]

def extract_xlsx(p: Path) -> List[Dict]:
    wb = openpyxl.load_workbook(str(p), data_only=True)
    texts = []
    for ws in wb.worksheets:
        rows = []
        for r in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in r]
            rows.append("\t".join(vals))
        sheet_txt = (f"# Hoja: {ws.title}\n" + "\n".join(rows)).strip()
        if sheet_txt:
            texts.extend(chunk_text(sheet_txt))
    return [{"text": t, "metadata": {"path": str(p), "type": "xlsx"}} for t in texts]

def extract_txt(p: Path) -> List[Dict]:
    txt = Path(p).read_text(encoding="utf-8", errors="ignore")
    return [{"text": ch, "metadata": {"path": str(p), "type": "txt"}} for ch in chunk_text(txt)]

def extract_any(p: Path) -> List[Dict]:
    ext = p.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(p)
    if ext in (".docx",):
        return extract_docx(p)
    if ext in (".xlsx", ".xlsm"):
        return extract_xlsx(p)
    if ext in (".txt",):
        return extract_txt(p)
    return []

def main():
    if not DATA_DIR.exists():
        print(f"[ERROR] No existe {DATA_DIR}. Crea la carpeta y coloca documentos.", file=sys.stderr)
        sys.exit(1)

    print("[INFO] Cargando modelo de embeddings:", EMBED_MODEL_NAME)
    model = SentenceTransformer(EMBED_MODEL_NAME)

    print("[INFO] Inicializando Chroma en", CHROMA_DIR)
    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(allow_reset=False))
    coll = client.get_or_create_collection(COLLECTION_NAME)

    files = []
    for root, _, fs in os.walk(DATA_DIR):
        for name in fs:
            p = Path(root) / name
            if p.suffix.lower() in (".pdf", ".docx", ".xlsx", ".xlsm", ".txt"):
                files.append(p)

    if not files:
        print(f"[WARN] No se encontraron archivos soportados en {DATA_DIR}.", file=sys.stderr)
        sys.exit(0)

    added = 0
    for p in sorted(files):
        print(f"[INGEST] {p}")
        docs = extract_any(p)
        if not docs:
            print(f"[SKIP] {p} (no se pudo extraer texto)")
            continue

        base_id = file_sha1(p)[:12]
        ids, metadatas, texts = [], [], []

        for k, d in enumerate(docs):
            ids.append(f"{base_id}-{k}")
            metadatas.append(d["metadata"])
            texts.append(d["text"])

        if ids:
            try:
                coll.delete(ids=ids)
            except Exception:
                pass

        embs = model.encode(texts, normalize_embeddings=True).tolist()
        coll.add(ids=ids, documents=texts, embeddings=embs, metadatas=metadatas)
        added += len(ids)
        print(f"[OK] {p} → {len(ids)} chunks indexados")

    print(f"[DONE] Total chunks indexados: {added}")

if __name__ == "__main__":
    main()
