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
| `POST /rag/documents` | `{title, text}` → potong, embed (`lab-embed`), simpan ke pgvector. Judul sama = diganti |
| `GET /rag/documents` | daftar dokumen + jumlah potongan |
| `POST /rag/ask` | `{question, k?}` → cari potongan terdekat (kosinus, HNSW), jawab dengan `lab-chat` + sumber |

RAG memanggil LiteLLM (`LITELLM_URL`, `LITELLM_API_KEY` dari secret `lab-app-llm`), yang meneruskan ke
Ollama di `203 ai`; setiap panggilan ter-trace di Phoenix. Tanpa konfigurasi LLM: 503; LLM gagal: 502.
Model jalan di CPU (tanpa GPU), jadi `/rag/ask` bisa butuh puluhan detik.

```bash
curl -k https://lab-app-dev.apps.lab.internal/rag/documents -H 'Content-Type: application/json' \
  -d '{"title":"cuti","text":"Karyawan mendapat cuti tahunan 12 hari kerja."}'
curl -k https://lab-app-dev.apps.lab.internal/rag/ask -H 'Content-Type: application/json' \
  -d '{"question":"Berapa hari cuti tahunan?"}'
```

Jalankan lokal: `pip install -r requirements-dev.txt && pytest -q && uvicorn app.main:app --reload`
