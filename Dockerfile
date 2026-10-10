# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie AS build
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim-trixie
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /install /usr/local
COPY app/ /srv/app/
WORKDIR /srv
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
