FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY src ./src
ENV ENVIRONMENT=production
CMD ["sh", "-c", "exec .venv/bin/uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log"]
