"""lab-app — aplikasi contoh untuk pipeline GitOps lab Proxmox.

GET /         info aplikasi (versi = tag image dari CI)
GET /healthz  liveness: proses hidup
GET /readyz   readiness: koneksi PostgreSQL + versi pgvector (503 bila DB tidak terjangkau)
"""

import os

import psycopg
from fastapi import FastAPI, Response

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
