# lab-app

Aplikasi contoh (FastAPI) untuk pipeline GitOps di homelab Proxmox.

```
git push ─► GitHub Actions: pytest → build → Trivy → push ghcr.io/teguhmuflih/lab-app:sha-xxxxxxx
                                                     └─► commit tag baru ke lab-gitops (overlay dev)
                                                           └─► Argo CD di K3s menarik & deploy (dev otomatis, prod manual)
```

| Endpoint | Fungsi |
|---|---|
| `/` | nama, versi (tag image), lingkungan |
| `/healthz` | liveness |
| `/readyz` | koneksi PostgreSQL + versi pgvector |

Jalankan lokal: `pip install -r requirements-dev.txt && pytest -q && uvicorn app.main:app --reload`
