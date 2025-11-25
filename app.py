from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Path
from pydantic import BaseModel

from rag_core import answer_with_rag

app = FastAPI(title="Comarket/AS2 Qwen RAG API por Áreas")



#  Pydantic Models


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


#   ENDPOINT GENERAL
#   /chat   (área opcional)

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Endpoint general.
    Permite área opcional.
    Si req.area no viene, rag_core usará DEFAULT_AREA o modo global.
    """
    result = answer_with_rag(
        user_query=req.query,
        top_k=req.top_k or 5,
        area=req.area,
    )

    resp = ChatResponse(
        answer=result["answer"],
        area=result["area"],
    )

    if req.return_context:
        resp.context = result["context"]

    if req.return_sources:
        resp.sources = result["sources"]

    return resp



#   ENDPOINT POR ÁREA
#   /chat/{area}

@app.post("/chat/{area}", response_model=ChatResponse)
def chat_by_area(
    area: str = Path(..., description="Área solicitada: logistica, ventas, sistemas, etc."),
    req: ChatRequest = None,
):
    """
    Endpoint pensado para workspaces del WebUI.
    """
    query = req.query if req else None
    top_k = req.top_k if req else 5

    result = answer_with_rag(
        user_query=query,
        top_k=top_k,
        area=area,
    )

    resp = ChatResponse(
        answer=result["answer"],
        area=result["area"],
    )

    if req and req.return_context:
        resp.context = result["context"]

    if req and req.return_sources:
        resp.sources = result["sources"]

    return resp



#   Healthcheck

@app.get("/health")
def health():
    return {"status": "ok"}
