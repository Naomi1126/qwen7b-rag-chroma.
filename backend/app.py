from typing import Optional, List, Dict, Any

from fastapi import (
    FastAPI,
    Path,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pathlib import Path as FsPath

# lógica de RAG
from rag_core import answer_with_rag

# Autenticación y DB
from auth import (
    get_db,
    get_current_user,
    verify_and_migrate_password,  
    create_access_token,
    get_user_by_email,
)
from models import User  # Modelo User con relación a áreas
from database import init_db

# Ingesta de documentos (PDF, Excel, etc.)
from ingest import ingest_file_for_area

# Inicializa la base de datos (crea tablas si no existen)
init_db()

app = FastAPI(title="Comarket/AS2 Qwen RAG API por Áreas")


# Pydantic Models

class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    area: Optional[str] = None        # Para /chat general
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


# Modelos para /auth/login (JSON)
class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthLoginResponse(BaseModel):
    token: str
    user_id: str
    areas: List[str]


# Helpers

def user_has_access_to_area(user: User, area_slug: str) -> bool:
    """
    Verifica si el usuario tiene acceso a un área dada (slug: 'logistica', 'ventas', etc.).
    """
    if not area_slug:
        return True
    return any(a.slug == area_slug for a in user.areas)


def save_uploaded_file(area: str, file: UploadFile) -> FsPath:
    """
    Guarda el archivo subido en /data/docs/{area}/
    """
    base_dir = FsPath("/data/docs")
    area_dir = base_dir / area
    area_dir.mkdir(parents=True, exist_ok=True)

    dest_path = area_dir / file.filename
    with dest_path.open("wb") as f:
        f.write(file.file.read())

    return dest_path


# AUTH

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login clásico con email (username) y password.
    Devuelve un access_token (JWT) que se usará en Authorization: Bearer <token>

    CAMBIO: usa verify_and_migrate_password() para soportar bcrypt legacy y migrar a PBKDF2.
    """
    user = get_user_by_email(db, form_data.username)
    if not user or not verify_and_migrate_password(db, user, form_data.password):
        raise HTTPException(status_code=400, detail="Credenciales incorrectas")

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/login", response_model=AuthLoginResponse)
def auth_login(
    data: AuthLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login pensado para el frontend (Gradio).
    Recibe JSON:
    {
      "username": "...",
      "password": "..."
    }

    Devuelve:
    - token (JWT)
    - user_id
    - areas (lista de slugs a las que tiene acceso)

     CAMBIO: usa verify_and_migrate_password() para soportar bcrypt legacy y migrar a PBKDF2.
    """
    user = get_user_by_email(db, data.username)
    if not user or not verify_and_migrate_password(db, user, data.password):
        raise HTTPException(status_code=400, detail="Credenciales incorrectas")

    access_token = create_access_token(data={"sub": user.email})
    areas = [area.slug for area in user.areas]

    return AuthLoginResponse(
        token=access_token,
        user_id=str(user.id),
        areas=areas,
    )


@app.get("/me", response_model=MeResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Devuelve datos básicos del usuario actual y la lista de áreas (slug) a las que tiene acceso.
    """
    return MeResponse(
        name=current_user.name,
        email=current_user.email,
        areas=[area.slug for area in current_user.areas],
    )


# ENDPOINT GENERAL /chat 

@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint general.
    Permite área opcional en el body (req.area).

    Si req.area viene:
      - Valida que el usuario tenga acceso a esa área
      - Pasa esa área a answer_with_rag

    Si req.area NO viene:
      - Se usa global o default según tu rag_core
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="La pregunta (query) no puede estar vacía.")

    if req.area and not user_has_access_to_area(current_user, req.area):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta área")

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


# ENDPOINT POR ÁREA /chat/{area}

@app.post("/chat/{area}", response_model=ChatResponse)
def chat_by_area(
    area: str = Path(..., description="Área solicitada: logistica, ventas, sistemas, etc."),
    req: Optional[ChatRequest] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint por área:
    - El área viene en la ruta
    - Se valida acceso del usuario
    - La pregunta viene en el body (req.query)
    """
    if not user_has_access_to_area(current_user, area):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta área")

    query = req.query if req else None
    top_k = req.top_k if req and req.top_k is not None else 5

    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="La pregunta (query) no puede estar vacía.")

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

# ENDPOINT DE SUBIDA DE DOCUMENTOS POR ÁREA
@app.post("/upload/{area}")
def upload_file_for_area(
    area: str = Path(..., description="Área a la que pertenece el documento"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Sube un archivo para un área:
    - Valida acceso
    - Guarda en /data/docs/{area}/
    - Ingesta a Chroma de esa área
    """
    if not user_has_access_to_area(current_user, area):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta área")

    dest_path = save_uploaded_file(area, file)

    try:
        ingest_file_for_area(dest_path, area=area)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ingestar el archivo: {e}",
        )

    return {"status": "ok", "filename": file.filename, "area": area}

# Healthcheck

@app.get("/health")
def health():
    return {"status": "ok"}
