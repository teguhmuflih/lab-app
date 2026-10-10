from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["app"] == "lab-app"


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_without_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert client.get("/readyz").json() == {"db": "not-configured"}


def test_readyz_db_unreachable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/z")
    r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json() == {"db": "error"}
