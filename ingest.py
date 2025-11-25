import os, sys, hashlib, argparse
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

# Directorio base de documentos y Chroma
BASE_DATA_DIR = Path(os.getenv("DATA_DIR", "/data/docs"))
BASE_CHROMA_DIR = os.getenv("CHROMA_DIR", "/data/chroma")

# Nombre base de colección 
BASE_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "docs")

# Modelo de embeddings
EMBED_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")  # densa por defecto


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
                    "metadata": {"path": str(p), "type": "pdf", "page": i + 1, "chunk": j},
                })
    return out


def extract_docx(p: Path) -> List[Dict]:
    d = docx.Document(str(p))
    txt = "\n".join([para.text for para in d.paragraphs])
    return [{"text": ch, "metadata": {"path": str(p), "type": "docx"}} for ch in chunk_text(txt)]


def extract_xlsx(p: Path) -> List[Dict]:
    wb = openpyxl.load_workbook(str(p), data_only=True)
    out = []

    for ws in wb.worksheets:
        headers = []
        sheet_lines = []

        # Extraemos encabezados de la primera fila
        first_row = next(ws.iter_rows(values_only=True), None)
        if first_row is None:
            continue

        for cell in first_row:
            headers.append("" if cell is None else str(cell).strip())

        # Procesamos el resto de filas
        for r in ws.iter_rows(min_row=2, values_only=True):
            parts = []
            for col_name, value in zip(headers, r):
                if col_name.strip() == "":
                    continue  # ignorar columnas sin nombre
                val = "" if value is None else str(value).strip()
                parts.append(f"{col_name}: {val}")
            if parts:
                sheet_lines.append(" | ".join(parts))

        # Construimos todo el texto de la hoja
        text = f"=== Hoja: {ws.title} ===\n" + "\n".join(sheet_lines)

        # Chunking de ese texto
        for ch in chunk_text(text):
            out.append({
                "text": ch,
                "metadata": {"path": str(p), "type": "xlsx", "sheet": ws.title},
            })

    return out


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingesta de documentos a Chroma con soporte por área."
    )
    parser.add_argument(
        "--area",
        type=str,
        default=os.getenv("AREA"),
        help="Área a indexar (logistica, ventas, sistemas, etc.). "
             "Si se omite, se usa el modo 'global' sin área.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    area = args.area

    # Definimos rutas y nombre de colección según haya área o no
    if area:
        data_dir = BASE_DATA_DIR / area
        chroma_dir = os.path.join(BASE_CHROMA_DIR, area)
        collection_name = f"{BASE_COLLECTION_NAME}_{area}"
    else:
        data_dir = BASE_DATA_DIR
        chroma_dir = BASE_CHROMA_DIR
        collection_name = BASE_COLLECTION_NAME

    if not data_dir.exists():
        print(f"[ERROR] No existe {data_dir}. Crea la carpeta y coloca documentos.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Área: {area if area else '(global sin área)'}")
    print("[INFO] Cargando modelo de embeddings:", EMBED_MODEL_NAME)
    model = SentenceTransformer(EMBED_MODEL_NAME)

    print("[INFO] Inicializando Chroma en", chroma_dir)
    client = chromadb.PersistentClient(
        path=chroma_dir,
        settings=Settings(allow_reset=False),
    )
    coll = client.get_or_create_collection(collection_name)
    print(f"[INFO] Colección: {collection_name}")

    files = []
    for root, _, fs in os.walk(data_dir):
        for name in fs:
            p = Path(root) / name
            if p.suffix.lower() in (".pdf", ".docx", ".xlsx", ".xlsm", ".txt"):
                files.append(p)

    if not files:
        print(f"[WARN] No se encontraron archivos soportados en {data_dir}.", file=sys.stderr)
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
