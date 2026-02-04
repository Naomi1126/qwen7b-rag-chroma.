import os
import threading
from typing import Optional, List, Dict, Any
from pathlib import Path as FsPath
import unicodedata
import shutil

from fastapi import (
    FastAPI,
    Path,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Request,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rag_core import answer_with_rag

from auth import (
    get_db,
    get_current_user,
    verify_and_migrate_password,
    create_access_token,
    get_user_by_email,
)
from models import User, Area
from database import init_db

from ingest import ingest_file_for_area

# -----------------------------
# INIT
# -----------------------------
init_db()

app = FastAPI(title="Aria - Asistente Virtual")

# -----------------------------
# CONCURRENCY GUARD (evita saturación vLLM)
# -----------------------------
MAX_LLM_CONCURRENCY = int(os.getenv("MAX_LLM_CONCURRENCY", "1"))
LLM_SEMAPHORE = threading.Semaphore(MAX_LLM_CONCURRENCY)
LLM_ACQUIRE_TIMEOUT = float(os.getenv("LLM_ACQUIRE_TIMEOUT", "2.0"))

# Defaults y límites (para evitar prompts gigantes)
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "3"))
MAX_TOP_K = int(os.getenv("MAX_TOP_K", "6"))

DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "128"))
MAX_MAX_TOKENS = int(os.getenv("MAX_MAX_TOKENS", "256"))
MIN_MAX_TOKENS = int(os.getenv("MIN_MAX_TOKENS", "16"))


# -----------------------------
# ERROR HANDLER: 422 -> 400 (faltan campos)
# -----------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    missing_fields = []
    for err in exc.errors():
        if err.get("type") == "missing":
            loc = err.get("loc") or []
            if len(loc) >= 2 and loc[0] == "body":
                missing_fields.append(str(loc[1]))
    if missing_fields:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": f"Faltan campos: {', '.join(sorted(set(missing_fields)))}",
                "code": "MISSING_FIELDS",
                "fields": sorted(set(missing_fields)),
            },
        )
    # fallback genérico
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Solicitud inválida", "code": "BAD_REQUEST"},
    )


# -----------------------------
# HELPERS (áreas)
# -----------------------------
def normalize_area(area: Optional[str]) -> Optional[str]:
    if not area:
        return None
    a = area.strip().lower()
    a = unicodedata.normalize("NFKD", a).encode("ascii", "ignore").decode("ascii")
    a = a.replace(" ", "_")
    return a or None


def user_has_access_to_area(user: User, area_slug: str) -> bool:
    if not area_slug:
        return True
    return any(a.slug == area_slug for a in user.areas)


def area_exists(db: Session, area_slug: str) -> bool:
    return db.query(Area).filter(Area.slug == area_slug).first() is not None


def safe_filename(name: str) -> str:
    # evita path traversal (../../)
    return FsPath(name).name


def save_uploaded_file(area: str, file: UploadFile) -> FsPath:
    """
    Guarda el archivo subido en /data/docs/{area}/
    - streaming (no carga todo a RAM)
    - filename seguro
    """
    base_dir = FsPath("/data/docs")
    area_dir = base_dir / area
    area_dir.mkdir(parents=True, exist_ok=True)

    filename = safe_filename(file.filename or "uploaded.bin")
    dest_path = area_dir / filename

    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return dest_path


# -----------------------------
# PYDANTIC MODELS
# -----------------------------
class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    area: Optional[str] = None
    return_context: Optional[bool] = False
    return_sources: Optional[bool] = False

    # opcional: permite que el frontend sugiera max_tokens sin tocar rag_core.py
    max_tokens: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    area: Optional[str] = None
    context: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None


class MeResponse(BaseModel):
    name: str
    email: str
    areas: List[str]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: str
    areas: List[str]


# -----------------------------
# API ENDPOINTS (bajo /api/*)
# -----------------------------
@app.post("/api/login", response_model=LoginResponse)
def api_login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login para el frontend.
    Requisitos de mensajes:
    - Usuario no encontrado
    - Contraseña incorrecta
    - Faltan campos: ...
    """
    username = (data.username or "").strip()
    password = (data.password or "").strip()

    missing = []
    if not username:
        missing.append("username")
    if not password:
        missing.append("password")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faltan campos: {', '.join(missing)}",
        )

    user = get_user_by_email(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    if not verify_and_migrate_password(db, user, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña incorrecta",
        )

    access_token = create_access_token(data={"sub": user.email})
    areas = [area.slug for area in user.areas]

    return LoginResponse(
        token=access_token,
        user_id=str(user.id),
        areas=areas,
    )


@app.get("/api/me", response_model=MeResponse)
def api_me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        name=current_user.name,
        email=current_user.email,
        areas=[area.slug for area in current_user.areas],
    )


@app.get("/api/areas")
def api_areas(current_user: User = Depends(get_current_user)):
    """
    Para poblar dropdown (slug + name).
    """
    return [{"slug": a.slug, "name": a.name} for a in current_user.areas]


def _sanitize_top_k(val: Optional[int]) -> int:
    try:
        x = int(val) if val is not None else DEFAULT_TOP_K
    except Exception:
        x = DEFAULT_TOP_K
    x = max(1, min(x, MAX_TOP_K))
    return x


def _sanitize_max_tokens(val: Optional[int]) -> int:
    try:
        x = int(val) if val is not None else DEFAULT_MAX_TOKENS
    except Exception:
        x = DEFAULT_MAX_TOKENS
    x = max(MIN_MAX_TOKENS, min(x, MAX_MAX_TOKENS))
    return x


@app.post("/api/chat", response_model=ChatResponse)
def api_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Requisito:
    - si no se selecciona área -> general
    - backend valida que el área exista; si no, error claro
    Protecciones:
    - limitar top_k
    - limitar max_tokens
    - semáforo de concurrencia para evitar saturación del LLM
    """
    if not req.query or not req.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La pregunta (query) no puede estar vacía."
        )

    req_area = normalize_area(req.area) or "general"

    if not area_exists(db, req_area):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Área no existe: {req_area}"
        )

    if not user_has_access_to_area(current_user, req_area):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta área"
        )

    top_k = _sanitize_top_k(req.top_k)
    max_tokens = _sanitize_max_tokens(req.max_tokens)

    acquired = LLM_SEMAPHORE.acquire(timeout=LLM_ACQUIRE_TIMEOUT)
    if not acquired:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "BUSY",
                    "message": "El asistente está ocupado procesando otra solicitud. Intenta de nuevo en unos segundos."
                }
            },
        )

    try:
        # Controlar tokens sin tocar internamente rag_core: seteamos env para esta llamada
        os.environ["RAG_MAX_COMPLETION_TOKENS"] = str(max_tokens)

        result = answer_with_rag(
            user_query=req.query,
            top_k=top_k,
            area=req_area,
        )

        resp = ChatResponse(
            answer=result["answer"],
            area=result.get("area"),
        )

        if req.return_context:
            resp.context = result.get("context")

        if req.return_sources:
            resp.sources = result.get("sources")

        return resp

    except RuntimeError as e:
        msg = str(e)

        # Timeout controlado del LLM/RAG
        if "tardando" in msg.lower() or "timeout" in msg.lower() or "read timed out" in msg.lower():
            return JSONResponse(
                status_code=504,
                content={"error": {"code": "LLM_TIMEOUT", "message": msg}},
            )

        return JSONResponse(
            status_code=502,
            content={"error": {"code": "LLM_ERROR", "message": msg}},
        )

    except Exception:
        # No filtramos detalles internos aquí
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Error interno del servidor."}},
        )

    finally:
        try:
            LLM_SEMAPHORE.release()
        except Exception:
            pass


@app.post("/api/chat/{area}", response_model=ChatResponse)
def api_chat_by_area(
    area: str = Path(..., description="Área: logistica, ventas, sistemas, etc."),
    req: Optional[ChatRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    area_norm = normalize_area(area)
    if not area_norm:
        raise HTTPException(status_code=400, detail="Área inválida")

    if not area_exists(db, area_norm):
        raise HTTPException(status_code=400, detail=f"Área no existe: {area_norm}")

    if not user_has_access_to_area(current_user, area_norm):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta área")

    query = req.query if req else None
    top_k = _sanitize_top_k(req.top_k if req else None)
    max_tokens = _sanitize_max_tokens(req.max_tokens if req else None)

    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="La pregunta (query) no puede estar vacía.")

    acquired = LLM_SEMAPHORE.acquire(timeout=LLM_ACQUIRE_TIMEOUT)
    if not acquired:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "BUSY",
                    "message": "El asistente está ocupado procesando otra solicitud. Intenta de nuevo en unos segundos."
                }
            },
        )

    try:
        os.environ["RAG_MAX_COMPLETION_TOKENS"] = str(max_tokens)

        result = answer_with_rag(
            user_query=query,
            top_k=top_k,
            area=area_norm,
        )

        resp = ChatResponse(answer=result["answer"], area=result.get("area"))

        if req and req.return_context:
            resp.context = result.get("context")

        if req and req.return_sources:
            resp.sources = result.get("sources")

        return resp

    except RuntimeError as e:
        msg = str(e)
        if "tardando" in msg.lower() or "timeout" in msg.lower() or "read timed out" in msg.lower():
            return JSONResponse(
                status_code=504,
                content={"error": {"code": "LLM_TIMEOUT", "message": msg}},
            )
        return JSONResponse(
            status_code=502,
            content={"error": {"code": "LLM_ERROR", "message": msg}},
        )

    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Error interno del servidor."}},
        )

    finally:
        try:
            LLM_SEMAPHORE.release()
        except Exception:
            pass


@app.post("/api/upload/{area}")
def api_upload_file(
    area: str = Path(..., description="Área del documento"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    area_norm = normalize_area(area)
    if not area_norm:
        raise HTTPException(status_code=400, detail="Área inválida")

    if not area_exists(db, area_norm):
        raise HTTPException(status_code=400, detail=f"Área no existe: {area_norm}")

    if not user_has_access_to_area(current_user, area_norm):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta área")

    dest_path = save_uploaded_file(area_norm, file)

    try:
        ingest_file_for_area(dest_path, area=area_norm)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ingestar el archivo: {e}",
        )

    return {"status": "ok", "filename": safe_filename(file.filename or ""), "area": area_norm}


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "FastAPI + vLLM RAG (Aria)"}


# -----------------------------
# SERVIR FRONTEND (React/Vite)
# -----------------------------
DIST_DIR = FsPath("/workspace/dist")

if DIST_DIR.exists() and DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    print(f"[FastAPI] Frontend encontrado en {DIST_DIR}")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")

        index_path = DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))

        raise HTTPException(status_code=404, detail="Frontend not found")
else:
    print("[FastAPI]   Directorio /workspace/dist no encontrado.")
    print("[FastAPI] El frontend no se servirá. Solo API disponible en /api/*")

    @app.get("/")
    async def root():
        return {
            "message": "FastAPI RAG Backend (Aria)",
            "note": "Frontend no disponible. Build el frontend con 'npm run build' primero.",
            "api_docs": "/docs"
        }
