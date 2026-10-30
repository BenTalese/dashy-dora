# Monolithic dev/prod image. Phase D / FU-186: dora_api runs alongside
# nginx serving the built SPA. The retailer-scraping `merchant_api` +
# the deals `emailer` live in the sibling **dora-companion** repo now.
# See compose.yml for the runtime story + nginx.conf for the SPA host
# config.
FROM python:3.11-slim AS develop-stage

# System packages:
#   nodejs (NodeSource 22) — frontend build (Quasar/Vite). Debian Bookworm's
#                   apt only ships Node 20, but @quasar/app-vite 2.6+ requires
#                   Node 22.22+, so we pull Node 22 from NodeSource instead.
#                   Bump the setup_NN.x line when Quasar next raises the floor.
#   nginx         — D1: replaces `quasar serve` for serving the static
#                   SPA in the runtime container.
#   curl          — used by the HEALTHCHECK directive below (+ fetching the
#                   NodeSource setup script).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg nginx \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @quasar/cli \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Python deps (kept in their own layer so source changes don't bust them) ──
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Piper neural-TTS engine for Dora's voice. Installed here, NOT pinned in
# requirements.txt (R-018 / ADR-013): piper-tts can't install on the Windows
# desktop build, so it would break `pip install -r requirements.txt` there —
# but the Linux container ships it so the neural voice works out of the box.
# Voice models are downloaded on demand into the data volume via Settings →
# Voice (features/tts/voice_provision); if this install ever fails the app
# still runs and falls back to the browser voice.
RUN pip install --no-cache-dir piper-tts==1.2.0

# ── Frontend deps. Critical: install inside /app/web_app so `quasar build`
#    can find node_modules there. We copy the WHOLE frontend project (not just
#    package*.json) before `npm install` because @quasar/app-vite runs
#    `quasar prepare` as an npm `postinstall` hook, which aborts unless the
#    Quasar project files (quasar.config.js, src/) are already present. Trade-
#    off: editing any frontend file now busts the npm-install cache layer —
#    acceptable for a self-host image built infrequently. `.dockerignore`
#    excludes node_modules/dist so the host's aren't dragged in. ─────────────
WORKDIR /app/web_app
COPY web_app/ ./
RUN npm install

# ── Rest of the source (backend etc.). `.dockerignore` excludes node_modules
#    so this COPY doesn't wipe the install above. ──────────────────────────
WORKDIR /app
COPY . .

# Prefetch the default Piper voice into `packaging/voices/` so the image
# ships with Dora's neural voice ready out of the box (R-018 / ADR-013).
# Reads the catalog from the source we just copied, so build + runtime stay
# in sync on URL / SHA. Non-fatal: a network blip during build still produces
# a working image — the SPA falls back to the browser voice and the user can
# still pick + download a voice from Settings → Voice later.
RUN python packaging/fetch_default_voice.py \
    || echo "[build] WARN: default voice fetch failed; image will use browser-voice fallback until a user downloads one"

# ── Frontend build ─────────────────────────────────────────────────────────
# `npm run build` is the one place the build mode lives (`quasar build -m pwa`,
# web_app/package.json). This used to call `quasar build` directly, which is
# SPA mode: the self-host image shipped without the service worker, manifest,
# install prompt or offline cache that FU-336 added — the mode flip never
# reached the Dockerfile (finalisation 19-R1). The `test -f` lines make the
# image fail to build, loudly, if that ever regresses.
#
# FU-861 — the build id (git short sha) is passed in, because `.git` isn't in
# the build context (see compose.yml `args`). It is stamped into the SPA bundle
# here and kept as a runtime env var, so About and `/api/health` name the same
# build. Empty is fine: About then says it's a local build.
ARG DORA_BUILD_ID=""
ENV DORA_BUILD_ID=${DORA_BUILD_ID}
WORKDIR /app/web_app
RUN npm run build \
    && test -f dist/spa/sw.js \
    && test -f dist/spa/manifest.json

# ── nginx site config + drop the stock default ─────────────────────────────
RUN rm -f /etc/nginx/sites-enabled/default \
    && rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/dora.conf

# ── Runtime ────────────────────────────────────────────────────────────────
WORKDIR /app
EXPOSE 5170 5174

# D1: container-level healthcheck. Hits nginx's lightweight /healthz
# (doesn't exercise the Python APIs, so a wedged API doesn't fail the
# whole container — the SPA still serves while you debug). Tweak with
# `compose.yml > healthcheck:` for stricter probes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://localhost:5174/healthz || exit 1

COPY startup.sh /usr/local/bin/startup.sh
RUN chmod +x /usr/local/bin/startup.sh
CMD ["bash", "/usr/local/bin/startup.sh"]
