# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie AS build
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim-trixie
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /install /usr/local
# Trivy (2026-10-10) melaporkan msgpack 1.1.2, urllib3 2.7.0, setuptools 70.3.0 dari
# pip/_vendor/vendor.txt di base image. Versi vendor ini tidak bisa dinaikkan dari luar.
# Aplikasi tidak butuh pip saat runtime (dependency sudah disalin dari stage build),
# jadi pip dihapus dari image final.
RUN pip uninstall -y pip \
 && python -c "import importlib.util as u; assert u.find_spec('pip') is None, 'pip masih ada'"
COPY app/ /srv/app/
WORKDIR /srv
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
