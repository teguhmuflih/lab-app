import pytest
from fastapi.testclient import TestClient

from app import rag
from app.main import app

client = TestClient(app)


# ---------- unit ----------
def test_chunk_text_gabung_paragraf_pendek():
    assert rag.chunk_text("satu\n\ndua\n\ntiga", size=50, overlap=10) == ["satu\n\ndua\n\ntiga"]


def test_chunk_text_potong_paragraf_panjang_dengan_overlap():
    chunks = rag.chunk_text("a" * 250, size=100, overlap=20)
    assert [len(c) for c in chunks] == [100, 100, 90]
    assert chunks[0][-20:] == chunks[1][:20]


def test_chunk_text_abaikan_kosong():
    assert rag.chunk_text("\n\n   \n\n") == []


def test_chunk_text_overlap_tidak_valid():
    with pytest.raises(ValueError):
        rag.chunk_text("x", size=10, overlap=10)


def test_to_vector():
    assert rag.to_vector([1, 0.5, -2]) == "[1.0,0.5,-2.0]"


def test_tanpa_konfigurasi_llm(monkeypatch):
    monkeypatch.delenv("LITELLM_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    with pytest.raises(rag.NotConfigured):
        rag.embed(["x"])


# ---------- endpoint (LLM & DB ditiru) ----------
@pytest.fixture
def fake_rag(monkeypatch):
    stored = {}
    monkeypatch.setattr(rag, "embed", lambda texts: [[0.1] * rag.EMBED_DIM for _ in texts])
    monkeypatch.setattr(rag, "store", lambda title, chunks, vectors: stored.update({title: chunks}))
    monkeypatch.setattr(
        rag,
        "search",
        lambda vector, k: [
            {"title": t, "chunk": i, "content": c, "score": 0.9}
            for t, cs in stored.items()
            for i, c in enumerate(cs)
        ][:k],
    )
    monkeypatch.setattr(rag, "chat", lambda q, ctx: f"jawaban dari {ctx[0]['title']}")
    return stored


def test_tambah_dokumen(fake_rag):
    r = client.post("/rag/documents", json={"title": "kebijakan", "text": "isi\n\nlain"})
    assert r.status_code == 201
    assert r.json() == {"title": "kebijakan", "chunks": 1}
    assert "kebijakan" in fake_rag


def test_tanya_dengan_sumber(fake_rag):
    client.post("/rag/documents", json={"title": "kebijakan", "text": "cuti 12 hari"})
    r = client.post("/rag/ask", json={"question": "berapa hari cuti?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "jawaban dari kebijakan"
    assert body["sources"] == [{"title": "kebijakan", "chunk": 0, "score": 0.9}]


def test_tanya_tanpa_dokumen(fake_rag):
    r = client.post("/rag/ask", json={"question": "apa saja?"})
    assert r.status_code == 200
    assert r.json()["sources"] == []


def test_validasi_input():
    assert client.post("/rag/documents", json={"title": "", "text": "x"}).status_code == 422
    assert client.post("/rag/ask", json={"question": "x", "k": 50}).status_code == 422


def test_rag_belum_dikonfigurasi_503(monkeypatch):
    monkeypatch.delenv("LITELLM_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    r = client.post("/rag/ask", json={"question": "x"})
    assert r.status_code == 503


def test_llm_gagal_502(monkeypatch):
    monkeypatch.setenv("LITELLM_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-uji")
    monkeypatch.setattr(rag, "LLM_TIMEOUT", 2)
    r = client.post("/rag/ask", json={"question": "x"})
    assert r.status_code == 502
