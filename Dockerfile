# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python API + static files
FROM python:3.12-slim AS api
WORKDIR /app

# System dependencies for asyncpg (PostgreSQL client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Mount static frontend files built in stage 1
COPY --from=frontend-build /app/web/dist /app/static

# Serve static files via FastAPI StaticFiles mount
# (see app.py — mounted at startup if /app/static exists)
ENV ADP_STATIC_DIR=/app/static

CMD ["sh", "-c", "uvicorn adp.api.app:app --host 0.0.0.0 --port ${ADP_PORT:-8001} --workers ${ADP_WORKERS:-2}"]
