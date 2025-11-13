from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel

from rag_core import answer_with_rag

app = FastAPI(title="Comarket/AS2 Qwen RAG API")


class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    return_context: Optional[bool] = False
    return_sources: Optional[bool] = False


class ChatResponse(BaseModel):
    answer: str
    context: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    result = answer_with_rag(req.query, top_k=req.top_k or 5)

    resp = ChatResponse(answer=result["answer"])

    if req.return_context:
        resp.context = result["context"]

    if req.return_sources:
        resp.sources = result["sources"]

    return resp


@app.get("/health")
def health():
    return {"status": "ok"}