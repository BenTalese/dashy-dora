#!/usr/bin/env bash
# Wrap dist/Dora/ (PyInstaller's one-folder output) into a single
# `Dora-vX.Y.Z-x86_64.AppImage` distributable.
#
# Prerequisites:
#   - packaging/build-linux.sh has been run successfully so
#     `dist/Dora/Dora` exists
#   - fuse / fuse2 installed at runtime (AppImages need it to mount)
#
# AppDir layout this script builds:
#
#   Dora.AppDir/
#       AppRun                  # entry point (copied from packaging/appimage/)
#       dora.desktop            # .desktop entry
#       dora.png                # 256x256 app icon
#       usr/
#           bin/
#               Dora            # PyInstaller binary
#               _internal/      # PyInstaller's shared libs + data
#               *.so            # pulled up alongside the binary
#
# appimagetool turns that directory into a runnable single-file
# AppImage by squashing it + prepending its runtime stub.

set -euo pipefail
cd "$(dirname "$0")/../.."

# ── Inputs ────────────────────────────────────────────────────────────
BIN="dist/Dora/Dora"
if [ ! -x "$BIN" ]; then
    echo "[appimage] ERROR: $BIN not found. Run packaging/build-linux.sh first." >&2
    exit 1
fi

VERSION=$(python3 -c "from dora_api.features.help.version_info import CURRENT_VERSION; print(CURRENT_VERSION)")
ARCH=$(uname -m)
OUT="dist/Dora-v${VERSION}-${ARCH}.AppImage"
APPDIR="dist/Dora.AppDir"

echo "[appimage] Dashy Dora — packaging v${VERSION} for ${ARCH}"

# ── 1. Build the AppDir tree ─────────────────────────────────────────
echo "[appimage] Building AppDir at $APPDIR"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

# Copy the PyInstaller one-folder output into usr/bin. cp -a preserves
# permissions + symlinks (PyInstaller uses both for the bundled libs).
cp -a dist/Dora/. "$APPDIR/usr/bin/"

# Top-level AppDir files required by appimagetool.
install -Dm755 packaging/appimage/AppRun "$APPDIR/AppRun"
install -Dm644 packaging/appimage/dora.desktop "$APPDIR/dora.desktop"
install -Dm644 packaging/icons/dora.png "$APPDIR/dora.png"

# Icon at the standard hicolor path too — file managers and KDE/GNOME
# session menus look here when the AppImage is integrated.
install -Dm644 packaging/icons/dora.png \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps/dora.png"
install -Dm644 packaging/appimage/dora.desktop \
    "$APPDIR/usr/share/applications/dora.desktop"

# ── 2. Fetch appimagetool if not cached ───────────────────────────────
# appimagetool is distributed as an AppImage itself. We cache it under
# packaging/.cache/ so repeat builds skip the download.
TOOL_DIR="packaging/.cache"
TOOL="$TOOL_DIR/appimagetool-${ARCH}.AppImage"
mkdir -p "$TOOL_DIR"
if [ ! -x "$TOOL" ]; then
    echo "[appimage] Downloading appimagetool"
    URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$URL" -o "$TOOL"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$URL" -O "$TOOL"
    else
        echo "[appimage] ERROR: neither curl nor wget on PATH" >&2
        exit 1
    fi
    chmod +x "$TOOL"
fi

# ── 3. Pack ───────────────────────────────────────────────────────────
echo "[appimage] Running appimagetool"
# ARCH must be exported for appimagetool to embed the right magic.
# `--no-appstream` skips appstreamcli validation (not bundled by
# default on minimal CI runners); fine for self-distribution.
ARCH="$ARCH" "$TOOL" --no-appstream "$APPDIR" "$OUT"

# ── 4. Done ───────────────────────────────────────────────────────────
SIZE_MB=$(du -sm "$OUT" | cut -f1)
echo "[appimage] OK. $OUT (${SIZE_MB} MB)"
echo "[appimage] Run it:  chmod +x $OUT && ./$OUT"
echo "[appimage] Test elsewhere by copying that single file."
