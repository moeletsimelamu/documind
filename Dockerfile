# DocuMind as one container: the FastAPI backend serving the production build of the Angular app.
#
#   docker build -t documind .
#   docker run --rm -p 127.0.0.1:8000:8000 -v documind-data:/data documind
#
# Uploaded documents and the database live in the /data volume, never in the image. No secrets are
# baked in: AI answers are configured at run time with DOCUMIND_LLM_* environment variables.

# --- 1. Build the frontend (same Node version as development and CI) ----------------------------
FROM node:22.14.0-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx ng build --configuration production

# --- 2. Runtime ---------------------------------------------------------------------------------
FROM python:3.14.9-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY backend/pyproject.toml backend/constraints.txt ./
COPY backend/src ./src
# Exact versions from constraints.txt; installed as a regular (non-editable) package.
RUN pip install -c constraints.txt . && rm -rf src

COPY --from=frontend /build/dist/documind-web/browser ./static

# An unprivileged user owns only the data directory.
RUN useradd --system --uid 10001 --no-create-home documind \
    && mkdir /data && chown documind:documind /data
USER documind

ENV DOCUMIND_DATA_DIR=/data \
    DOCUMIND_STATIC_DIR=/app/static \
    DOCUMIND_API_DOCS=false

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=4)"]

# Inside the container the server must listen on all interfaces; publish the port on the host's
# loopback only (-p 127.0.0.1:8000:8000) unless an authenticating proxy is in front of it.
CMD ["uvicorn", "documind.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
