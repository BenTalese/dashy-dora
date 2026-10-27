# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Discount Dora desktop bundle.

Targets one-folder mode (faster startup, friendlier to AV scanners
than one-file). Output: `dist/Dora/Dora` plus a sibling tree of
shared libraries + bundled data.

Build locally:
    cd web_app && npm run build && cd ..
    pyinstaller dora.spec
    ./dist/Dora/Dora

Or use the orchestration script: `packaging/build-linux.sh`.

Things this spec has to handle by hand because PyInstaller can't
infer them statically:

1. **Quasar SPA** lives under `web_app/dist/spa/` and is loaded by
   Flask's send_from_directory + caught by our SPA blueprint. Has to
   ship as data, not Python.

2. **Alembic migration scripts** are imported dynamically by
   alembic at runtime via filesystem scan. PyInstaller needs to
   know they're data, not Python source.

3. **Dynamic feature discovery** — `dora_api/startup.py` walks
   `dora_api/features/` with `importlib.import_module`. Static
   analysis misses these, so we `collect_submodules()` the package
   explicitly.

4. **Hidden imports** for runtime-discovered plugins/drivers:
   sqlite dialect, alembic runtime, apscheduler trigger types, the
   pywebview GTK backend on Linux.

5. **Email + onboarding seed templates** + bundled JSON seed data
   are read from disk at runtime — ship as data.
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Hidden imports ──────────────────────────────────────────────────
# Plus the dynamically-discovered feature modules (every file under
# */features/ that registers a blueprint or handler).
hiddenimports = [
    "sqlalchemy.dialects.sqlite",
    "alembic.runtime.migration",
    "alembic.script",
    "alembic.config",
    # Alembic's env.py is loaded dynamically and imports
    # `logging.config`, which PyInstaller doesn't pull in from
    # static analysis. Same story for `logging.handlers` — used by
    # logging_setup.py's TimedRotatingFileHandler.
    "logging.config",
    "logging.handlers",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.interval",
    "apscheduler.triggers.date",
    "apscheduler.schedulers.background",
    "apscheduler.jobstores.memory",
    "apscheduler.executors.pool",
    # dependency_injector occasionally loses its dynamic providers
    # to static analysis. `wiring` covers the common cases.
    "dependency_injector.wiring",
    "dependency_injector.providers",
]
hiddenimports += collect_submodules("dora_api.features")
# dependency_injector is a Cython package — PyInstaller's static
# analysis can't see its internal modules (`errors`, `containers`,
# `providers` subtypes etc.). Pull them all in explicitly.
hiddenimports += collect_submodules("dependency_injector")

# ── Data files ──────────────────────────────────────────────────────
# `(source, dest_inside_bundle)` tuples. Paths are relative to the
# spec file (repo root); destinations mirror the on-disk layout the
# code expects.
datas = [
    # The built SPA. `desktop_app.py` resolves this to set
    # DORA_SPA_DIR so the SPA blueprint serves files from it.
    ("web_app/dist/spa", "web_app/dist/spa"),
    # Alembic uses Path-based discovery; the migrations folder must
    # be present at the expected relative path.
    ("dora_api/persistence/migrations", "dora_api/persistence/migrations"),
    # Onboarding seed data the API reads from disk.
    ("dora_api/features/onboarding/default_stock_groups.json",
     "dora_api/features/onboarding"),
    ("dora_api/features/onboarding/default_locations.json",
     "dora_api/features/onboarding"),
    # Email templates — Jinja templates rendered at send time.
    ("dora_api/email_templates", "dora_api/email_templates"),
]
datas += collect_data_files("alembic", subdir="templates")

# Piper neural-TTS engine — bundled when `packaging/fetch_piper.py` has
# populated `packaging/piper/` (build-linux.sh / the Windows build run it
# before pyinstaller). Lands at `<bundle>/piper/`; `desktop_app.py` points
# DORA_PIPER_BIN there at runtime. Optional: if the folder is absent the build
# still succeeds and the desktop app falls back to the browser voice (or a
# DORA_PIPER_BIN the user sets).
if os.path.isdir("packaging/piper"):
    datas += [("packaging/piper", "piper")]

# Piper default voice model — bundled when `packaging/fetch_default_voice.py`
# has populated `packaging/voices/`. Lands at `<bundle>/voices/`;
# `voice_provision.bundled_voices_dir()` picks it up at runtime so a fresh
# desktop install can speak Dora's neural voice immediately without the user
# having to click Download. Additional voices the user chooses in Settings →
# Voice still land in the writable data dir (downloaded on demand).
if os.path.isdir("packaging/voices"):
    datas += [("packaging/voices", "voices")]

# ── Analysis / build ────────────────────────────────────────────────
a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Big stdlib modules we don't use; trimming saves ~30 MB.
        "tkinter",
        "test",
        "unittest",
        "pydoc_data",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Dora",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,        # UPX-compressed binaries trip AV; not worth it
    console=False,    # GUI app — no console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["packaging/icons/dora.png"],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Dora",
)
