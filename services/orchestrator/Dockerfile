FROM node:24.16.0-slim AS web-build

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PAIRPILOT_WEB_DIST=/app/web/dist

WORKDIR /app
COPY packages/schemas /app/packages/schemas
COPY services/orchestrator /app/services/orchestrator
RUN pip install --no-cache-dir /app/packages/schemas /app/services/orchestrator

COPY infra /app/infra
COPY --from=web-build /build/web/dist /app/web/dist

RUN useradd --create-home --uid 10001 pairpilot \
    && chown -R pairpilot:pairpilot /app
USER pairpilot

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn pairpilot_orchestrator.web:app --host 0.0.0.0 --port ${PORT:-8080}"]
