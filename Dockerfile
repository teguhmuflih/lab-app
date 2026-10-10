# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie AS build
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim-trixie
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /install /usr/local
# Paket bawaan base image yang punya CVE HIGH dengan perbaikan (Trivy, 2026-10-10).
# Versi dicek di langkah ini juga: kalau masih lama, build gagal di sini, bukan di Trivy.
RUN pip install --no-cache-dir --upgrade "setuptools>=78.1.1" "urllib3>=2.8.0" "msgpack>=1.2.1" \
 && python -c "import importlib.metadata as m; t = lambda p: tuple(int(x) for x in m.version(p).split('.')[:3]); \
assert t('setuptools') >= (78, 1, 1), t('setuptools'); \
assert t('urllib3') >= (2, 8, 0), t('urllib3'); \
assert t('msgpack') >= (1, 2, 1), t('msgpack'); \
print('paket bawaan OK')"
COPY app/ /srv/app/
WORKDIR /srv
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
