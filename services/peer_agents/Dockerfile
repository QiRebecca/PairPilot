FROM python:3.12.6-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY packages/schemas/pairpilot_schemas ./pairpilot_schemas
COPY services/peer_agents/pyproject.toml ./
COPY services/peer_agents/pairpilot_peer_agents ./pairpilot_peer_agents

RUN python -m pip install --no-cache-dir --index-url https://pypi.org/simple \
      --upgrade pip==26.2.1 \
    && python -m pip install --no-cache-dir --index-url https://pypi.org/simple .

USER 65532:65532

CMD ["sh", "-c", "uvicorn pairpilot_peer_agents.main:app --host 0.0.0.0 --port ${PORT}"]
