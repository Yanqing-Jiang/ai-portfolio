FROM python:3.12.8-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libjpeg62-turbo-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12.8-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libjpeg62-turbo curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --no-create-home appuser
COPY --from=builder /install /usr/local
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
ENV PYTHONPATH=/app
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
EXPOSE 8000
# PR-Infra (2026-05-10): scaled gunicorn workers 2 → 6 originally, but
# walked back to 1 (2026-05-10 PM) after the headed audit surfaced
# "Fortune session not found" 404s. Root cause: ``FortuneStore`` is an
# in-memory dict per worker process, so ``POST /create`` (Worker A's
# memory) and ``GET /stream`` (round-robined to Worker B) only hit the
# same worker ~16.7% of the time at 6 workers. Until a Redis-backed
# FortuneStore lands (PR-5 candidate), one worker is the only correct
# scheme — and demo-scale traffic doesn't need more. The 8-CPU/4G
# compose limit still applies (used by foundation calc + Python heap).
CMD ["gunicorn", "main:app", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--timeout", "120", "--graceful-timeout", "30", \
     "--keep-alive", "75"]
