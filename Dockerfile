FROM python:3.14-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini .
COPY static/ ./static/
COPY knowledge/ ./knowledge/
COPY ml/ ./ml/
RUN useradd --uid 10001 --create-home janamen && mkdir -p /data && chown -R janamen:janamen /app /data
ENV DATABASE_URL=sqlite:////data/janamen.db
USER janamen
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
