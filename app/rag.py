"""RAG sederhana: potong teks → embedding (LiteLLM) → pgvector → cari → jawab (LiteLLM).

LiteLLM (namespace ai) meneruskan ke Ollama di 203 ai; setiap panggilan ter-trace di Phoenix.
HTTP memakai urllib (stdlib) supaya image tidak bertambah dependency.
"""

import json
import os
import urllib.error
import urllib.request

import psycopg

EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "lab-embed")
CHAT_MODEL = os.getenv("RAG_CHAT_MODEL", "lab-chat")
EMBED_DIM = int(os.getenv("RAG_EMBED_DIM", "1024"))  # qwen3-embedding:0.6b
LLM_TIMEOUT = float(os.getenv("RAG_LLM_TIMEOUT", "300"))  # CPU tanpa GPU: jawaban bisa > 1 menit

SYSTEM_PROMPT = (
    "Kamu asisten yang menjawab HANYA berdasarkan konteks yang diberikan. "
    "Jika jawabannya tidak ada di konteks, katakan bahwa kamu tidak tahu. "
    "Jawab ringkas dalam bahasa yang sama dengan pertanyaan, dan sebutkan judul sumber yang dipakai."
)


class NotConfigured(Exception):
    """LITELLM_URL / LITELLM_API_KEY / DATABASE_URL belum di-set."""


class LLMError(Exception):
    """LiteLLM/Ollama gagal atau tidak terjangkau."""


# ---------- teks ----------
def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Potong per paragraf; paragraf yang terlalu panjang dipotong per `size` karakter dengan overlap."""
    if overlap >= size:
        raise ValueError("overlap harus lebih kecil dari size")
    chunks: list[str] = []
    buf = ""
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        while len(para) > size:
            chunks.append(para[:size])
            para = para[size - overlap :]
        buf = para
    if buf:
        chunks.append(buf)
    return chunks


def to_vector(values: list[float]) -> str:
    """Literal pgvector: '[0.1,0.2,...]' (dipakai dengan ::vector, tanpa paket pgvector)."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


# ---------- LiteLLM ----------
def _llm_config() -> tuple[str, str]:
    url, key = os.getenv("LITELLM_URL"), os.getenv("LITELLM_API_KEY")
    if not url or not key:
        raise NotConfigured("LITELLM_URL / LITELLM_API_KEY belum di-set")
    return url.rstrip("/"), key


def _post(path: str, payload: dict) -> dict:
    url, key = _llm_config()
    req = urllib.request.Request(
        url + path,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise LLMError(f"{path}: {e}") from e


def embed(texts: list[str]) -> list[list[float]]:
    data = _post("/v1/embeddings", {"model": EMBED_MODEL, "input": texts})["data"]
    vectors = [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
    if any(len(v) != EMBED_DIM for v in vectors):
        raise LLMError(f"dimensi embedding {len(vectors[0])} ≠ {EMBED_DIM} (RAG_EMBED_DIM)")
    return vectors


def chat(question: str, contexts: list[dict]) -> str:
    context = "\n\n".join(f"[{c['title']} #{c['chunk']}]\n{c['content']}" for c in contexts)
    body = {
        "model": CHAT_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Konteks:\n{context}\n\nPertanyaan: {question}"},
        ],
    }
    return _post("/v1/chat/completions", body)["choices"][0]["message"]["content"].strip()


# ---------- PostgreSQL + pgvector ----------
def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise NotConfigured("DATABASE_URL belum di-set")
    return url


def ensure_schema(conn: psycopg.Connection) -> None:
    # 2 replika bisa membuat tabel bersamaan saat request pertama → kunci per transaksi
    conn.execute("select pg_advisory_xact_lock(hashtext('lab-app:rag_chunks'))")
    conn.execute(
        f"""
        create table if not exists rag_chunks (
            id          bigserial primary key,
            title       text not null,
            chunk_index int  not null,
            content     text not null,
            embedding   vector({EMBED_DIM}) not null,
            created_at  timestamptz not null default now(),
            unique (title, chunk_index)
        )"""
    )
    conn.execute(
        "create index if not exists rag_chunks_embedding_hnsw "
        "on rag_chunks using hnsw (embedding vector_cosine_ops)"
    )


def store(title: str, chunks: list[str], vectors: list[list[float]]) -> None:
    """Simpan dokumen; judul yang sama = dokumen diganti (chunk lama dihapus)."""
    with psycopg.connect(_db_url(), connect_timeout=5) as conn:
        ensure_schema(conn)
        conn.execute("delete from rag_chunks where title = %s", (title,))
        with conn.cursor() as cur:
            cur.executemany(
                "insert into rag_chunks (title, chunk_index, content, embedding) "
                "values (%s, %s, %s, %s::vector)",
                [(title, i, c, to_vector(v)) for i, (c, v) in enumerate(zip(chunks, vectors))],
            )


def search(vector: list[float], k: int) -> list[dict]:
    with psycopg.connect(_db_url(), connect_timeout=5) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            "select title, chunk_index, content, 1 - (embedding <=> %s::vector) as score "
            "from rag_chunks order by embedding <=> %s::vector limit %s",
            (to_vector(vector), to_vector(vector), k),
        ).fetchall()
    return [{"title": r[0], "chunk": r[1], "content": r[2], "score": round(float(r[3]), 4)} for r in rows]


def list_documents() -> list[dict]:
    with psycopg.connect(_db_url(), connect_timeout=5) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            "select title, count(*), max(created_at) from rag_chunks group by title order by 3 desc"
        ).fetchall()
    return [{"title": r[0], "chunks": r[1], "updated_at": r[2].isoformat()} for r in rows]
