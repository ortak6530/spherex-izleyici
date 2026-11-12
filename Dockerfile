# Single image for Render: builds the frontend with Node, runs FastAPI with Python 3.13.

FROM node:24-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    PYTHONPATH=/app/backend/src
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY config/ config/
COPY --from=web /app/frontend/dist frontend/dist
RUN useradd --create-home app && mkdir -p data/cache && chown -R app:app data
USER app
EXPOSE 8000
# Render injects $PORT. Migrations run on every start (idempotent).
CMD ["sh", "-c", "cd backend && alembic upgrade head && cd /app && exec uvicorn skytracker.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
