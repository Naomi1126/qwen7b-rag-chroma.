from typing import Optional, List, Dict, Any
from pathlib import Path as FsPath

from fastapi import (
    FastAPI,
    Path,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Lógica de RAG
from rag_core import answer_with_rag

# Autenticación y DB
from auth import (
    get_db,
    get_current_user,
    verify_and_migrate_password,
    create_access_token,
    get_user_by_email,
)
from models import User
from database import init_db

# Ingesta de documentos
from ingest import ingest_file_for_area

# Inicializa la base de datos (crea tablas si no existen)
init_db()

# ✅ Cambiado: título “Aria”
app = FastAPI(title="Aria - Asistente Virtual")


# ---------------------------
# PYDANTIC MODELS
# ---------------------------

class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    area: Optional[str] = None
    return_context: Optional[bool] = False
    return_sources: Optional[bool] = False


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


# ---------------------------
# HELPERS
# ---------------------------

def user_has_access_to_area(user: User, area_slug: str) -> bool:
    """Verifica si el usuario tiene acceso a un área."""
    if not area_slug:
        return True
    return any(a.slug == area_slug for a in user.areas)


def save_uploaded_file(area: str, file: UploadFile) -> FsPath:
    """Guarda el archivo subido en /data/docs/{area}/"""
    base_dir = FsPath("/data/docs")
    area_dir = base_dir / area
    area_dir.mkdir(parents=True, exist_ok=True)

    dest_path = area_dir / file.filename
    with dest_path.open("wb") as f:
        f.write(file.file.read())

    return dest_path


# ---------------------------
# API ENDPOINTS (bajo /api/*)
# ---------------------------

@app.post("/api/login", response_model=LoginResponse)
def api_login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login para el frontend.
    Recibe JSON: {"username": "...", "password": "..."}
    Devuelve: {"token": "...", "user_id": "...", "areas": [...]}
    """
    user = get_user_by_email(db, data.username)
    if not user or not verify_and_migrate_password(db, user, data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
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
    """Devuelve datos del usuario actual."""
    return MeResponse(
        name=current_user.name,
        email=current_user.email,
        areas=[area.slug for area in current_user.areas],
    )


@app.post("/api/chat", response_model=ChatResponse)
def api_chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint general de chat.
    Permite área opcional en el body (req.area).
    """
    if not req.query or not req.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La pregunta (query) no puede estar vacía."
        )

    if req.area and not user_has_access_to_area(current_user, req.area):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta área"
        )

    result = answer_with_rag(
        user_query=req.query,
        top_k=req.top_k or 5,
        area=req.area,
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


@app.post("/api/chat/{area}", response_model=ChatResponse)
def api_chat_by_area(
    area: str = Path(..., description="Área: logistica, ventas, sistemas, etc."),
    req: Optional[ChatRequest] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint de chat por área específica.
    El área viene en la ruta.
    """
    if not user_has_access_to_area(current_user, area):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta área"
        )

    query = req.query if req else None
    top_k = req.top_k if req and req.top_k is not None else 5

    if not query or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La pregunta (query) no puede estar vacía."
        )

    result = answer_with_rag(
        user_query=query,
        top_k=top_k,
        area=area,
    )

    resp = ChatResponse(
        answer=result["answer"],
        area=result.get("area"),
    )

    if req and req.return_context:
        resp.context = result.get("context")

    if req and req.return_sources:
        resp.sources = result.get("sources")

    return resp


@app.post("/api/upload/{area}")
def api_upload_file(
    area: str = Path(..., description="Área del documento"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Sube un archivo para un área.
    Requiere autenticación y acceso al área.
    """
    if not user_has_access_to_area(current_user, area):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta área"
        )

    dest_path = save_uploaded_file(area, file)

    try:
        ingest_file_for_area(dest_path, area=area)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ingestar el archivo: {e}",
        )

    return {"status": "ok", "filename": file.filename, "area": area}


@app.get("/api/health")
def api_health():
    """Health check del backend."""
    return {"status": "ok", "service": "FastAPI + vLLM RAG (Aria)"}


# ---------------------------
# SERVIR FRONTEND (React/Vite)
# ---------------------------

DIST_DIR = FsPath("/workspace/dist")

if DIST_DIR.exists() and DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    print(f"[FastAPI] Frontend encontrado en {DIST_DIR}")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """
        Sirve el frontend React.
        - Si la ruta empieza con 'api/', retorna 404 (ya se manejó arriba)
        - Para cualquier otra ruta, sirve index.html (SPA routing)
        """
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
