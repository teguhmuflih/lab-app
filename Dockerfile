# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie AS build
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim-trixie
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /install /usr/local
# Paket bawaan base image yang punya CVE HIGH dengan perbaikan (Trivy, 2026-10-10).
# Trivy masih melihat versi lama walau pip sudah mengupgrade: metadata lama tertinggal di
# image. Metadata itu dihapus di sini, lalu semua instalasi yang tersisa dicek versinya.
RUN pip install --no-cache-dir --upgrade "setuptools>=78.1.1" "urllib3>=2.8.0" "msgpack>=1.2.1" \
 && python - <<'EOF'
import importlib.metadata as m, shutil
mins = {"setuptools": (78, 1, 1), "urllib3": (2, 8, 0), "msgpack": (1, 2, 1)}
def nama(d): return (d.metadata["Name"] or "").lower()
def ver(d): return tuple(int(x) for x in d.version.split(".")[:3])
for d in list(m.distributions()):
    if nama(d) in mins and ver(d) < mins[nama(d)]:
        shutil.rmtree(d._path)
for name, low in mins.items():
    sisa = [d for d in m.distributions() if nama(d) == name]
    assert sisa and all(ver(d) >= low for d in sisa), (name, [d.version for d in sisa])
    print(name, [d.version for d in sisa])
EOF
COPY app/ /srv/app/
WORKDIR /srv
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
