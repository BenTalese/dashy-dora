#!/usr/bin/env bash
# Build the Dashy Dora desktop bundle for Linux.
#
# Produces `dist/Dora/Dora` plus a sibling tree of shared libs +
# bundled data. Phase 4 (AppImage packaging) wraps that directory
# into a single `.AppImage` file.
#
# Prerequisites:
#   - Python 3.11 + a venv with `pip install -r requirements.txt`
#   - Node + npm
#
# Flags:
#   --skip-spa           reuse an existing `web_app/dist/spa/` build
#   --skip-pyinstaller   run only the SPA build (sanity check)
#   --appimage           after pyinstaller, wrap dist/Dora/ into a
#                        single .AppImage (Phase 4)
#   --clean              wipe dist/ + build/ before starting
#
# Designed to be re-runnable; partial output won't poison subsequent
# runs (PyInstaller's cache handles that).

set -euo pipefail
cd "$(dirname "$0")/.."

SKIP_SPA=0
SKIP_PYI=0
CLEAN=0
APPIMAGE=0
for arg in "$@"; do
    case "$arg" in
        --skip-spa)         SKIP_SPA=1 ;;
        --skip-pyinstaller) SKIP_PYI=1 ;;
        --clean)            CLEAN=1 ;;
        --appimage)         APPIMAGE=1 ;;
        -h|--help)
            sed -n '2,/^set -/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
            exit 0 ;;
        *)
            echo "Unknown flag: $arg" >&2
            exit 2 ;;
    esac
done

echo "[build] Dashy Dora — Linux desktop bundle"
echo "[build] cwd=$(pwd)"

# System deps (libpython*.so for PyInstaller) are apt-installed, not pip — documented in README. We
# don't preflight them: ldconfig-based detection is unreliable
# across distros, and PyInstaller's own "PythonLibraryNotFoundError"
# already points at the missing dev package clearly.

if [ "$CLEAN" = "1" ]; then
    echo "[build] Cleaning dist/ + build/"
    rm -rf dist build
fi

# ── 1. SPA build ─────────────────────────────────────────────────────
if [ "$SKIP_SPA" = "0" ]; then
    if [ ! -d "web_app/node_modules" ]; then
        echo "[build] web_app/node_modules missing — running npm install"
        (cd web_app && npm install)
    fi
    echo "[build] Building SPA (quasar build)"
    (cd web_app && npm run build)
else
    echo "[build] Skipping SPA build (--skip-spa)"
fi

if [ ! -f "web_app/dist/spa/index.html" ]; then
    echo "[build] ERROR: web_app/dist/spa/index.html missing. Did the SPA build succeed?" >&2
    exit 1
fi

# ── 2. PyInstaller bundle ───────────────────────────────────────────
if [ "$SKIP_PYI" = "1" ]; then
    echo "[build] Skipping PyInstaller (--skip-pyinstaller)"
    exit 0
fi

if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "[build] ERROR: pyinstaller not on PATH. Activate your venv and pip install pyinstaller." >&2
    exit 1
fi

# Fetch the Piper TTS binary so the bundle ships Dora's neural voice (R-018 /
# ADR-013). Idempotent; non-fatal — if it fails the bundle still builds and the
# desktop app falls back to the browser voice.
echo "[build] Fetching Piper binary (packaging/fetch_piper.py)"
python packaging/fetch_piper.py || echo "[build] WARN: Piper fetch failed; bundle will use browser-voice fallback"

# Prefetch the default Piper voice so the bundle ships a neural voice ready
# out of the box (R-018 / ADR-013). Idempotent + non-fatal: a network blip
# only costs the zero-friction first-run experience, not the build itself.
echo "[build] Fetching default Piper voice (packaging/fetch_default_voice.py)"
python packaging/fetch_default_voice.py \
    || echo "[build] WARN: default voice fetch failed; user will need to download one from Settings"

echo "[build] Running pyinstaller dora.spec"
pyinstaller --noconfirm dora.spec

# ── 3. Quick smoke check ────────────────────────────────────────────
BIN="dist/Dora/Dora"
if [ ! -x "$BIN" ]; then
    echo "[build] ERROR: PyInstaller didn't produce $BIN" >&2
    exit 1
fi
SIZE_MB=$(du -sm dist/Dora | cut -f1)
echo "[build] OK. Bundle at $BIN (${SIZE_MB} MB)"
echo "[build] Try it:  ./$BIN"

# ── 4. Optional AppImage wrap (Phase 4) ──────────────────────────────
if [ "$APPIMAGE" = "1" ]; then
    echo "[build] --appimage: wrapping into a single AppImage"
    ./packaging/appimage/build-appimage.sh
else
    echo "[build] (rerun with --appimage to wrap dist/Dora into a single .AppImage)"
fi
