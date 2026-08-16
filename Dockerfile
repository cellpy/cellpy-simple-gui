# syntax=docker/dockerfile:1.7
#
# cellpy simple GUI — server image (#121)
#
# The web deployment target is *one instance per user*: a container per person,
# or one spawned on demand. The app's process-global state (the cell library,
# the job manager, cellpy's own config session) is single-tenant by design, so
# this is packaging, not architecture. Do not put two users behind one container.
#
# Read docs/deployment.md before exposing this to a network. In short: the
# per-launch token is not an authentication system.

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.10.2

# --------------------------------------------------------------------------- #
# Stage 1 — build the virtualenv
# --------------------------------------------------------------------------- #
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# No `export` extra, and the reason is not size. The pinned kaleido resolves to
# 1.x, which does not bundle a renderer — it drives a *separate* Chrome through
# choreographer, so installing the wheel alone changes nothing at runtime except
# the error you get. Measured in this base image: `plotly_get_chrome` exits 0,
# and `to_image` then dies with BrowserFailedError because slim lacks the shared
# libraries Chrome needs. Making that work is its own piece of work
# (cellpy-simple-gui#135), not a build flag to leave half-finished.
#
# Without it, Export ▾ → Figure returns a clean 503 naming the real cause. CSV,
# Excel, Parquet and JSON export are unaffected, and the Plotly toolbar's camera
# button still saves a PNG client-side.

# Dependencies first, without the project: this layer is invalidated only by the
# lockfile, so editing app source does not re-resolve ~160 packages.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app

# --no-editable installs a real wheel into the venv, so the runtime stage needs
# the venv alone — no source tree, no /app on sys.path.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# --------------------------------------------------------------------------- #
# Stage 2 — runtime
# --------------------------------------------------------------------------- #
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="cellpy simple GUI" \
      org.opencontainers.image.description="Explore battery cell data with cellpy — single-tenant web server" \
      org.opencontainers.image.source="https://github.com/cellpy/cellpy-simple-gui" \
      org.opencontainers.image.licenses="MIT"

# Two instrument loaders are Python wheels wrapping system libraries that
# python:slim does not carry, and both fail *quietly enough to miss*:
#
#   mdbtools  — on posix, cellpy reads Arbin `.res` by shelling out to
#               `mdb-export`. Without it the import job still reports "done";
#               only its result payload says nothing was added. Measured, not
#               assumed: the first build of this image imported zero Arbin
#               files while the smoke test said PASS.
#   unixodbc  — provides libodbc.so.2, which pyodbc links against. Without it
#               `arbin_sql` and `arbin_sql_7` raise ImportError during
#               discovery and simply never appear in the instrument list.
#
# ~10 MB together. Note that *connecting* to an Arbin SQL Server additionally
# needs a vendor ODBC driver, which is not shipped here.
RUN apt-get update \
 && apt-get install -y --no-install-recommends mdbtools unixodbc \
 && rm -rf /var/lib/apt/lists/*

# A fixed uid keeps bind-mounted host directories predictable to chown.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app

# CSG_HOST is off loopback on purpose: that is what puts the app in "served"
# mode, where every client-supplied path is confined to CSG_DATA_DIR (#120).
#
# CELLPY_PATHS__EXAMPLESDIR is not decoration. cellpy resolves it at *import*
# time and, when the directory is missing, silently falls back to one inside
# site-packages — root-owned here, so a non-root process cannot download the
# demo cells into it and the zero-setup demo fails. It is created below.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    CSG_HOST=0.0.0.0 \
    CSG_PORT=8577 \
    CSG_DATA_DIR=/data \
    CELLPY_PATHS__EXAMPLESDIR=/home/app/cellpy_data/examples \
    CELLPY_PATHS__OUTDATADIR=/data

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app packaging/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
 && mkdir -p /home/app/cellpy_data/examples/data /data \
 && chown -R app:app /home/app /data

USER app

# Bake the demo cells in (~27 MB) so the zero-setup demo works offline and on
# the first click. cellpy otherwise fetches them on demand, which needs egress
# from wherever this ends up running — and writes them as a side effect of the
# first user action, which is a poor place to discover there is no network.
ARG WITH_DEMO_DATA=1
RUN if [ "$WITH_DEMO_DATA" = "1" ]; then \
      python -c "from cellpy.utils import example_data as e; \
[getattr(e, n)() for n in ('cellpy_file', 'rate_file', 'old_cellpy_file_path', \
'arbin_file_path', 'maccor_file_path_type_three', 'neware_file_path', \
'pec_file_path')]" \
   && python -c "import os, pathlib; \
p = pathlib.Path(os.environ['CELLPY_PATHS__EXAMPLESDIR']) / 'data'; \
print('baked demo data:', sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) >> 20, 'MiB')"; \
    fi

# Deliberately no VOLUME instruction: it would make every `docker run` without
# -v create an anonymous volume that outlives the container and is never
# reclaimed. Mount it explicitly instead (see docker-compose.yml).
WORKDIR /data
EXPOSE 8577

# /healthz is the one route outside the token guard, which is what makes it
# usable here. Python rather than curl — this base image ships neither curl nor
# wget. The start period is generous because importing cellpy is not quick.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; \
urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('CSG_PORT', '8577') + '/healthz', timeout=4)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["cellpy-simple-gui", "--server", "--no-open"]
