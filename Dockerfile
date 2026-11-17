# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
# web/.env (checked in) sets VITE_KEYCLOAK_URL=http://127.0.0.1:8080 -- correct
# for local dev, but Vite bakes it into the static bundle at build time, so a
# deploy build must override it or every deployed environment ships a
# Keycloak URL that only resolves on a developer's own machine (ADP-cm9: this
# shipped to production for the whole ADP-fnv deployment before being caught
# here). Default matches web/.env's own local-dev value -- an empty-string
# default would instead be treated by Vite as an explicit (broken) override,
# since process.env presence wins over .env file values regardless of value.
# deploy.sh / the CI workflow always pass the real deployed URL explicitly.
ARG VITE_KEYCLOAK_URL="http://127.0.0.1:8080"
ENV VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL}
# Pin auth ON for every deploy build, deterministically (ADP-cm9 follow-up).
# web/.env.local sets VITE_AUTH_ENABLED=false for local no-auth dev; it's
# gitignored and now .dockerignore'd, but this ENV is the belt-and-suspenders:
# a process.env value wins over any .env* file in Vite, so even if a stray
# .env.local slipped into the context again, the deployed frontend stays
# auth-enabled (matching the backend's ADP_AUTH_ENABLED=true). Disabling auth
# in the frontend while the backend enforces it is what caused the black-screen
# bug: no token sent -> every API call 401s -> the SPA fails to render.
ARG VITE_AUTH_ENABLED="true"
ENV VITE_AUTH_ENABLED=${VITE_AUTH_ENABLED}
RUN npm run build

# Stage 2: build the Python environment (ADP-blp.8).
# The compiler and headers needed to build wheels stay in this stage; the runtime image below
# gets only the finished virtualenv. The install is editable, so the virtualenv points at
# /app/src -- the runtime stage copies the source to that same path.
FROM python:3.12-slim AS python-build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY pyproject.toml ./
COPY alembic.ini ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Stage 3: Python API + static files
FROM python:3.12-slim AS api
WORKDIR /app

# Runtime libraries only: libcairo2 for cairosvg (adp.diagrams.router imports it at module
# load, so without the shared library the whole app fails to start, not just PNG export) and
# libpq5 for PostgreSQL clients. No compiler in the image that serves requests.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# ADP-blp.8: run as an unprivileged user. A bug that lets an attacker run code (the app
# rasterises SVG and evaluates expressions with native libraries) then lands as this user, not
# root. It has a home directory because the embedding model is cached under ~/.cache.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin adp

COPY --from=python-build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY pyproject.toml alembic.ini ./
COPY src/ ./src/

# Mount static frontend files built in stage 1
COPY --from=frontend-build /app/web/dist /app/static

# Serve static files via FastAPI StaticFiles mount
# (see app.py — mounted at startup if /app/static exists)
ENV ADP_STATIC_DIR=/app/static

RUN chown -R adp:adp /app
USER adp

CMD ["sh", "-c", "uvicorn adp.api.app:app --host 0.0.0.0 --port ${ADP_PORT:-8001} --workers ${ADP_WORKERS:-2}"]
