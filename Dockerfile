FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /src/frontend

RUN corepack enable \
    && corepack prepare pnpm@11.0.0 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm run build


FROM python:3.12-slim-bookworm AS python-dependencies

WORKDIR /src

COPY backend/requirements-lock.txt ./backend/requirements-lock.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir --prefix=/install \
       -r backend/requirements-lock.txt


FROM debian:bookworm-slim AS native-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpng-dev \
       pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY third_party/ipol/ third_party/ipol/
COPY scripts/build_ipol.sh scripts/build_ipol.sh

RUN rm -f third_party/ipol/*.o \
          third_party/ipol/lens_distortion_correction_2p_iterative_optimization \
    && bash scripts/build_ipol.sh \
    && strip third_party/ipol/lens_distortion_correction_2p_iterative_optimization


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONPATH=/app/backend \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STRAIGHTLENS_DATA=/app/.runtime/jobs

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpng16-16 \
       libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 straightlens \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app \
       --shell /usr/sbin/nologin straightlens

WORKDIR /app

COPY --from=python-dependencies /install/ /usr/local/
COPY backend/ backend/
COPY --from=frontend-builder /src/frontend/dist/ frontend/dist/
COPY LICENSE LICENSE
COPY third_party/ipol/README.txt third_party/ipol/UPSTREAM.md third_party/ipol/changelog.txt third_party/ipol/
COPY --from=native-builder \
     /src/third_party/ipol/lens_distortion_correction_2p_iterative_optimization \
     third_party/ipol/lens_distortion_correction_2p_iterative_optimization

RUN mkdir -p /app/.runtime/jobs \
    && chown -R straightlens:straightlens /app

USER straightlens

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import json,urllib.request; response=urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3); assert json.load(response)['algorithm_ready']"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
