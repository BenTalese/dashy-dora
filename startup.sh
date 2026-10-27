#!/bin/bash
# Dashy Dora monolithic-container entrypoint.
#
# Phase D / FU-186: starts dora_api in the background and finishes with
# nginx in the foreground so the container's lifecycle matches nginx's
# (when nginx dies, the container exits — Docker's expected behaviour).
# The retailer-scraping `merchant_api` + the deals `emailer` live in the
# sibling **dora-companion** repo now.
#
# Env vars consumed (all optional, sensible defaults baked in):
#   DORA_DATA_DIR       — sqlite + uploads dir (default /app/data)
#   DORA_CACHE_DIR      — image cache (default /app/cache)
#   DORA_LOG_DIR        — log directory (default /app/logs, as compose + the Dockerfile set)
#   DORA_DB_PATH        — explicit db file location (overrides DATA_DIR)
#   DORA_ENV            — development|production|test (compose defaults to
#                         production; drives the API server choice below)
#   DORA_API_SERVER     — auto|gunicorn|flask. `auto` (default) → gunicorn in
#                         production, Flask dev server otherwise. FU-397.
# See `.env.example` at the repo root for the full env catalogue.

set -e

echo "[startup] Dashy Dora — booting monolithic container"
echo "[startup] DATA_DIR=${DORA_DATA_DIR:-/app/data} CACHE_DIR=${DORA_CACHE_DIR:-/app/cache} LOG_DIR=${DORA_LOG_DIR:-/app/logs}"

# Pre-create the standard data directories so the Python processes
# don't race each other on first boot.
mkdir -p \
    "${DORA_DATA_DIR:-/app/data}" \
    "${DORA_CACHE_DIR:-/app/cache}" \
    "${DORA_LOG_DIR:-/app/logs}"

# ── Python service (background) ──────────────────────────────────────
# FU-397: production runs a real WSGI server (gunicorn → dora_api.wsgi:app)
# instead of Flask's dev server. `DORA_API_SERVER=auto` (default) picks
# gunicorn when DORA_ENV is production, else the dev server; force either with
# DORA_API_SERVER=gunicorn|flask. gunicorn is configured in gunicorn.conf.py
# (single threaded worker so the in-process scheduler stays singular).
DORA_ENV_LC="$(echo "${DORA_ENV:-production}" | tr '[:upper:]' '[:lower:]')"
DORA_API_SERVER_LC="$(echo "${DORA_API_SERVER:-auto}" | tr '[:upper:]' '[:lower:]')"

case "$DORA_API_SERVER_LC" in
    gunicorn) use_gunicorn=1 ;;
    flask)    use_gunicorn=0 ;;
    *)  # auto — gunicorn for production-ish profiles, dev server otherwise
        case "$DORA_ENV_LC" in
            prod|production) use_gunicorn=1 ;;
            *)               use_gunicorn=0 ;;
        esac ;;
esac

if [ "$use_gunicorn" = "1" ]; then
    echo "[startup] dora_api via gunicorn (production WSGI, gunicorn.conf.py)"
    gunicorn -c /app/gunicorn.conf.py dora_api.wsgi:app &
else
    echo "[startup] dora_api via Flask dev server (DORA_ENV=$DORA_ENV_LC)"
    python -m dora_api.startup &
fi
DAPI_PID=$!
echo "[startup] dora_api pid=$DAPI_PID"

# ── nginx in foreground ──────────────────────────────────────────────
# `daemon off;` keeps nginx attached to PID 1's stdout/stderr so
# `docker logs` works without extra plumbing.
echo "[startup] nginx (foreground) serving SPA on :5174"
exec nginx -g "daemon off;"
