#!/usr/bin/env bash
# Build the Dashy Dora desktop bundle for macOS.
#
# Produces `dist/Dora/Dora` plus a sibling tree of dylibs + bundled
# data. The app opens the SPA in the default browser.
#
# Prerequisites:
#   - Python 3.11 + a venv with `pip install -r requirements.txt`
#   - Node + npm
#   - Xcode command-line tools (`xcode-select --install`) — PyInstaller
#     shells out to `codesign` / `lipo` on macOS bundles.
#
# Flags:
#   --skip-spa           reuse an existing `web_app/dist/spa/` build
#   --skip-pyinstaller   run only the SPA build (sanity check)
#   --clean              wipe dist/ + build/ before starting
#   --dmg                after pyinstaller, pack dist/Dora.app into
#                        dist/Dora-vX.Y.Z-macos-<arch>.dmg
#   --version <X.Y.Z>    version in the .dmg name. Default:
#                        CURRENT_VERSION from version_info.py
#   --arch <ARCH>        force macos_aarch64 (Apple Silicon) or
#                        macos_x64 (Intel). Default: auto-detect via
#                        `uname -m` so an Apple Silicon Mac produces
#                        an arm64 bundle and an Intel Mac produces
#                        x86_64. Cross-arch builds work in principle
#                        (Rosetta-run Python + fetch_piper.py --platform)
#                        but the pyinstaller output binaries match the
#                        interpreter arch — build in the matching
#                        Python venv for the target arch.
#
# Designed to be re-runnable; partial output won't poison subsequent
# runs (PyInstaller's cache handles that). Mirrors `build-linux.sh`
# step-for-step so a build-log diff between platforms stays readable.

set -euo pipefail
cd "$(dirname "$0")/.."

SKIP_SPA=0
SKIP_PYI=0
CLEAN=0
ARCH_OVERRIDE=""
DMG=0
VERSION=""
while [ $# -gt 0 ]; do
    case "$1" in
        --skip-spa)         SKIP_SPA=1; shift ;;
        --skip-pyinstaller) SKIP_PYI=1; shift ;;
        --clean)            CLEAN=1; shift ;;
        --dmg)              DMG=1; shift ;;
        --version)
            VERSION="${2:-}"
            if [ -z "$VERSION" ]; then
                echo "--version needs a value (e.g. 1.0.1)" >&2
                exit 2
            fi
            shift 2 ;;
        --arch)
            ARCH_OVERRIDE="${2:-}"
            if [ -z "$ARCH_OVERRIDE" ]; then
                echo "--arch needs a value (macos_aarch64 or macos_x64)" >&2
                exit 2
            fi
            shift 2 ;;
        -h|--help)
            sed -n '2,/^set -/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
            exit 0 ;;
        *)
            echo "Unknown flag: $1" >&2
            exit 2 ;;
    esac
done

# Auto-detect target platform key for fetch_piper.py.
if [ -n "$ARCH_OVERRIDE" ]; then
    PIPER_PLATFORM="$ARCH_OVERRIDE"
else
    UNAME_M="$(uname -m)"
    case "$UNAME_M" in
        arm64|aarch64) PIPER_PLATFORM="macos_aarch64" ;;
        x86_64)        PIPER_PLATFORM="macos_x64" ;;
        *)
            echo "[build] ERROR: unrecognised uname -m: $UNAME_M" >&2
            exit 1 ;;
    esac
fi

echo "[build] Dashy Dora — macOS desktop bundle"
echo "[build] cwd=$(pwd)"
echo "[build] target Piper platform: $PIPER_PLATFORM"

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

# Fetch the Piper TTS binary matching the target arch (R-018 /
# ADR-013). Explicit --platform because fetch_piper.py's auto-detect
# only picks the *runtime* arch — with --arch cross-arch builds
# would otherwise grab the wrong tarball. Idempotent; non-fatal.
echo "[build] Fetching Piper binary (--platform $PIPER_PLATFORM)"
python packaging/fetch_piper.py --platform "$PIPER_PLATFORM" \
    || echo "[build] WARN: Piper fetch failed; bundle will use browser-voice fallback"

# Prefetch the default Piper voice so the bundle ships a neural
# voice ready out of the box. Idempotent + non-fatal.
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
echo "[build] Try it:  ./$BIN  (or open dist/Dora.app)"

# ── 4. Optional .dmg (drag Dora.app onto Applications) ───────────────
if [ "$DMG" = "0" ]; then
    echo "[build] (rerun with --dmg to pack dist/Dora.app into a .dmg)"
    exit 0
fi

if [ ! -d "dist/Dora.app" ]; then
    echo "[build] ERROR: dist/Dora.app missing — dora.spec's BUNDLE step didn't run" >&2
    exit 1
fi
if [ -z "$VERSION" ]; then
    VERSION=$(python -c "from dora_api.features.help.version_info import CURRENT_VERSION; print(CURRENT_VERSION)")
fi
VERSION="${VERSION#v}"
case "$PIPER_PLATFORM" in
    macos_aarch64) DMG_ARCH="arm64" ;;
    *)             DMG_ARCH="x64" ;;
esac
DMG_OUT="dist/Dora-v${VERSION}-macos-${DMG_ARCH}.dmg"
STAGE="build/dmg"

echo "[build] Packing $DMG_OUT"
rm -rf "$STAGE" "$DMG_OUT"
mkdir -p "$STAGE"
# ditto keeps the bundle's symlinks, permissions and ad-hoc signature intact.
ditto dist/Dora.app "$STAGE/Dora.app"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Dashy Dora" -srcfolder "$STAGE" -ov -format UDZO "$DMG_OUT"
SIZE_MB=$(du -sm "$DMG_OUT" | cut -f1)
echo "[build] OK. Disk image at $DMG_OUT (${SIZE_MB} MB)"
