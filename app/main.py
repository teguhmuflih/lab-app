"""lab-app — aplikasi contoh untuk pipeline GitOps lab Proxmox.

GET /         info aplikasi (versi = tag image dari CI)
GET /healthz  liveness: proses hidup
GET /readyz   readiness: koneksi PostgreSQL + versi pgvector (503 bila DB tidak terjangkau)

RAG (fase 7, lewat LiteLLM → Ollama di 203 ai):
POST /rag/documents  {title, text}     potong, embed, simpan ke pgvector (judul sama = diganti)
GET  /rag/documents                    daftar dokumen
POST /rag/ask        {question, k?}    cari potongan terdekat lalu jawab dengan model chat
"""

import os

import psycopg
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from app import rag

APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_ENV = os.getenv("APP_ENV", "local")

app = FastAPI(title="lab-app", version=APP_VERSION)


@app.get("/")
def root() -> dict:
    return {"app": "lab-app", "version": APP_VERSION, "env": APP_ENV}


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz(response: Response) -> dict:
    url = os.getenv("DATABASE_URL")
    if not url:
        return {"db": "not-configured"}
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            row = conn.execute(
                "select extversion from pg_extension where extname = 'vector'"
            ).fetchone()
    except psycopg.Error:
        response.status_code = 503
        return {"db": "error"}
    return {"db": "ok", "pgvector": row[0] if row else None}


# ---------- RAG ----------
class Document(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=200_000)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    k: int = Field(default=4, ge=1, le=10)


def _rag_error(e: Exception) -> HTTPException:
    if isinstance(e, rag.NotConfigured):
        return HTTPException(503, detail=f"RAG belum dikonfigurasi: {e}")
    if isinstance(e, rag.LLMError):
        return HTTPException(502, detail=f"LLM gagal: {e}")
    return HTTPException(503, detail="database tidak terjangkau")


@app.post("/rag/documents", status_code=201)
def add_document(doc: Document) -> dict:
    chunks = rag.chunk_text(doc.text)
    try:
        vectors = rag.embed(chunks)
        rag.store(doc.title, chunks, vectors)
    except (rag.NotConfigured, rag.LLMError, psycopg.Error) as e:
        raise _rag_error(e) from e
    return {"title": doc.title, "chunks": len(chunks)}


@app.get("/rag/documents")
def documents() -> list[dict]:
    try:
        return rag.list_documents()
    except (rag.NotConfigured, psycopg.Error) as e:
        raise _rag_error(e) from e


@app.post("/rag/ask")
def ask(q: Question) -> dict:
    try:
        sources = rag.search(rag.embed([q.question])[0], q.k)
        if not sources:
            return {"answer": "Belum ada dokumen. Tambahkan lewat POST /rag/documents.", "sources": []}
        answer = rag.chat(q.question, sources)
    except (rag.NotConfigured, rag.LLMError, psycopg.Error) as e:
        raise _rag_error(e) from e
    return {
        "answer": answer,
        "sources": [{f: s[f] for f in ("title", "chunk", "score")} for s in sources],
    }
