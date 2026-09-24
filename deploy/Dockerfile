# One image for the web app and the worker. The frontend is built in a Node stage and served
# by the API, so there is a single origin and no CORS to configure.

FROM node:22-slim AS web
WORKDIR /build
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/.npmrc ./
RUN corepack enable \
 && corepack prepare pnpm@10.34.5 --activate \
 && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /uvx /bin/
# age encrypts backups (GW_BACKUP_AGE_RECIPIENTS)
RUN apt-get update && apt-get install -y --no-install-recommends age && rm -rf /var/lib/apt/lists/*
ARG WITH_WHISPER=false
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GW_DATA_DIR=/data \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH"
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN if [ "$WITH_WHISPER" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --extra whisper; \
    else \
      uv sync --frozen --no-dev --no-install-project; \
    fi
COPY backend/app ./app
COPY backend/ontology ./ontology
COPY --from=web /build/dist /app/frontend/dist
RUN useradd --system --uid 1001 groundwork && mkdir -p /data && chown groundwork /data
USER groundwork
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
