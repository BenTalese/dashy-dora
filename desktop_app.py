"""Desktop A — entry point for the bundled native app.

Run directly (`python desktop_app.py`) from a dev checkout that has
already built the SPA via `quasar build`, or as the PyInstaller
target for the installer pipeline.

Boot sequence:
    1. Resolve per-user data / cache / log dirs via platformdirs and
       export them as DORA_* env vars BEFORE any dora_api module
       loads (the env-first config layer reads them at import time).
    2. Auto-generate the two remaining bootstrap keys
       (`DORA_SECRET_KEY`, `DORA_SECRET_ENCRYPTION_KEY`) into the
       per-user data dir if not already set — FU-333 Bucket D so a
       double-click end-user never sees an env var.
    3. Tell the production gate to stand down (DORA_SKIP_PROD_VALIDATION).
    4. Run the Flask app on a random localhost port in a daemon
       thread using werkzeug.serving.make_server, so we can shut it
       down cleanly when the window closes.
    5. Poll /api/health until it answers 200 (max 5s).
    6. Seed detected bundle paths (piper binary + voices dir) into the
       `AppSetting` row when they're empty — FU-333 Bucket B strict
       (no env fallback: the resolver reads only from the DB).
    7. Launch the SPA in the user's default browser.
    8. On shutdown signal, stop Flask and exit.

Nothing here is Docker-aware. Docker keeps using startup.sh.
"""
from __future__ import annotations

import logging
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from platformdirs import (user_cache_dir, user_data_dir, user_log_dir)


APP_NAME = "Dora"
APP_PUBLISHER = "BenTalese"


def _set_default_env(name: str, value: str) -> None:
    """Like os.environ.setdefault, but treats empty-string values as
    unset (matches the convention the config layer uses)."""
    if not os.environ.get(name):
        os.environ[name] = value


def _bootstrap_paths() -> None:
    """Wire the per-OS user data dirs into the DORA_* env vars the
    config layer reads. Must run BEFORE any `from dora_api...` import
    happens, since `configuration_manager.py` reads env at module
    import time."""
    data = Path(user_data_dir(APP_NAME, APP_PUBLISHER))
    cache = Path(user_cache_dir(APP_NAME, APP_PUBLISHER))
    logs = Path(user_log_dir(APP_NAME, APP_PUBLISHER))
    for path in (data, cache, logs):
        path.mkdir(parents=True, exist_ok=True)

    _set_default_env("DORA_DATA_DIR", str(data))
    _set_default_env("DORA_CACHE_DIR", str(cache))
    _set_default_env("DORA_LOG_DIR", str(logs))

    # FU-045: the bundled desktop install is the canonical lightweight
    # self-host — pin it to SQLite under the per-user data dir. The
    # config layer would otherwise default to Postgres (the standard
    # for dev/hosted), which obviously isn't available on a freshly
    # installed end-user machine. `DORA_DB_PATH` is the SQLite shortcut
    # (plain filesystem path; the config layer builds the URL).
    _set_default_env("DORA_DB_PATH", str(data / "dora.data.db"))

    # Production profile + skip the required-vars gate (no public
    # CORS host, no bootstrap-admin email needed on a single-user
    # desktop install).
    _set_default_env("DORA_ENV", "production")
    _set_default_env("DORA_SKIP_PROD_VALIDATION", "true")
    # CORS doesn't apply when the SPA is served from the same Flask
    # origin, but the prod validation still inspects the var. Empty
    # is fine because we set SKIP=true above.
    _set_default_env("DORA_CORS_ORIGINS", "")


def _bootstrap_keys() -> None:
    """FU-333 Bucket D — auto-generate the two remaining bootstrap env vars
    on desktop bundles.

    `DORA_SECRET_KEY` signs the session cookie; `DORA_SECRET_ENCRYPTION_KEY`
    is Dora's data-at-rest KEK — it wraps every secret persisted in the DB
    (SMTP password, VAPID private key, per-user paid-provider LLM API keys).
    On server self-host the operator sets both explicitly at deploy time. On
    a desktop bundle the user should never see an env var — so we persist a
    per-install key file under the user data dir and set the env from it
    before dora_api loads.

    Rotation: the operator can delete the key file to force a re-generate at
    the next launch. That invalidates every stored ciphertext (SMTP password,
    VAPID private key, LLM API keys) and every existing session — same
    trade-off documented in `secret_encryption.py`.
    """
    data = Path(os.environ["DORA_DATA_DIR"])
    data.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("DORA_SECRET_KEY"):
        secret_file = data / ".secret_key"
        if not secret_file.exists():
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            secret_file.touch(mode=0o600)  # owner-only before the key lands
            secret_file.write_text(secrets.token_hex(32))
        os.environ["DORA_SECRET_KEY"] = secret_file.read_text().strip()

    if not os.environ.get("DORA_SECRET_ENCRYPTION_KEY"):
        wrap_file = data / ".secret_encryption_key"
        if not wrap_file.exists():
            # Fernet.generate_key() returns 32-byte url-safe base64 — exactly
            # what `secret_encryption._fernet()` expects to read from env.
            from cryptography.fernet import Fernet
            wrap_file.touch(mode=0o600)
            wrap_file.write_bytes(Fernet.generate_key())
        os.environ["DORA_SECRET_ENCRYPTION_KEY"] = wrap_file.read_bytes().decode("ascii").strip()


def _bootstrap_spa_dir() -> None:
    """Tell Flask where the built SPA lives.

    PyInstaller's one-folder bundle extracts data files to a path
    accessible via `sys._MEIPASS` (one-file mode) OR alongside the
    binary (one-folder mode). We try both. Falls back to the dev
    checkout path so `python desktop_app.py` from a built repo works
    without bundling at all."""
    if os.environ.get("DORA_SPA_DIR"):
        return
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "web_app" / "dist" / "spa")
    here = Path(__file__).resolve().parent
    candidates.append(here / "web_app" / "dist" / "spa")
    for c in candidates:
        if (c / "index.html").is_file():
            os.environ["DORA_SPA_DIR"] = str(c)
            return


def _detect_bundled_piper_paths() -> tuple[str | None, str | None]:
    """Return `(piper_bin, bundled_voice_dir)` for whichever locations exist
    inside this bundle, or `(None, None)` when nothing is prefetched.

    `dora.spec` ships `packaging/piper/` and `packaging/voices/` alongside the
    binary (see `packaging/fetch_piper.py` + `packaging/fetch_default_voice.py`).
    One-folder + one-file PyInstaller expose them via `sys._MEIPASS`; the dev
    checkout layout also works so `python desktop_app.py` from a repo where
    the prefetch scripts have run behaves the same.

    FU-333 Bucket B is strict — the app resolves `piper_bin` /
    `piper_bundled_voice_dir` only through `AppSetting`. This detector runs
    at desktop boot; `_seed_desktop_paths` (post-init) writes what we find
    into the row when the row is empty. Server / Docker installs leave the
    row blank and use system-installed piper via PATH; the operator can
    override in Settings → Admin → System → Voice.
    """
    exe = "piper.exe" if sys.platform.startswith("win") else "piper"
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    here = Path(__file__).resolve().parent
    roots.append(here)                 # alongside the bundled executable
    roots.append(here / "packaging")   # dev checkout layout

    bin_path: str | None = None
    for root in roots:
        candidate = root / "piper" / exe
        if candidate.is_file():
            bin_path = str(candidate)
            break

    voice_dir: str | None = None
    for root in roots:
        candidate = root / "voices"
        if candidate.is_dir():
            voice_dir = str(candidate)
            break

    return bin_path, voice_dir


def _seed_desktop_paths(bin_path: str | None, voice_dir: str | None) -> None:
    """FU-333 Bucket B strict — populate `AppSetting.piper_bin` and
    `piper_bundled_voice_dir` with the bundle-detected paths if the row is
    empty *or* points at a path that no longer exists (moved bundle).

    Called after Flask + migrations are up but before we open the browser,
    so the first `/api/tts/voices` request finds the correct paths on the
    row. Wrapped in a broad except — a DB hiccup here shouldn't take the
    desktop launch down; the admin can always set the paths from Settings
    if the auto-seed fails."""
    log = logging.getLogger("dora.desktop")
    if not bin_path and not voice_dir:
        return
    try:
        from dora_api.app import app
        from dora_api.features.app_settings.access import \
            get_or_create_app_setting
        from dora_api.persistence.sqlalchemy_repository import \
            SqlAlchemyRepository
        with app.app_context():
            repo = SqlAlchemyRepository()
            setting = get_or_create_app_setting(repo)
            changed = False
            current_bin = (getattr(setting, "piper_bin", "") or "").strip()
            if bin_path and (not current_bin or not Path(current_bin).exists()):
                setting.piper_bin = bin_path
                changed = True
            current_voices = (getattr(setting, "piper_bundled_voice_dir", "") or "").strip()
            if voice_dir and (not current_voices or not Path(current_voices).is_dir()):
                setting.piper_bundled_voice_dir = voice_dir
                changed = True
            if changed:
                repo.save_changes()
                log.info(
                    "Seeded desktop piper paths: bin=%s bundle=%s",
                    bin_path or "<unchanged>", voice_dir or "<unchanged>",
                )
    except Exception as exc:  # noqa: BLE001
        log.warning("Piper path seed skipped: %s", exc)


def _pick_free_port() -> int:
    """Bind to port 0 to let the kernel pick, then release. Tiny
    race window between release and Flask binding — acceptable for a
    local single-user desktop app."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(url: str, timeout_seconds: float = 5.0) -> bool:
    """Poll /api/health until it returns 2xx or the deadline passes."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.1)
    return False


def main() -> int:
    _bootstrap_paths()
    _bootstrap_keys()
    _bootstrap_spa_dir()
    piper_bin_path, piper_voice_dir = _detect_bundled_piper_paths()

    # Set up file-based logging early so anything that goes wrong
    # below leaves a trail in user_log_dir. The desktop bundle has
    # no stdout the user can see.
    log_dir = Path(os.environ["DORA_LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "desktop.log", encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    log = logging.getLogger("dora.desktop")
    log.info("Booting Dora desktop")
    log.info("  data=%s", os.environ["DORA_DATA_DIR"])
    log.info("  cache=%s", os.environ["DORA_CACHE_DIR"])
    log.info("  logs=%s", os.environ["DORA_LOG_DIR"])
    log.info("  spa=%s", os.environ.get("DORA_SPA_DIR") or "<not found>")
    log.info("  piper_bin=%s", piper_bin_path or "<not bundled — using PATH>")
    log.info("  piper_voice_dir=%s", piper_voice_dir or "<not bundled>")

    # Import lazily so the env vars above are already set by the
    # time any `from dora_api...` module runs.
    from dora_api.app import app as dora_app
    from dora_api.startup import init_db, register_routers

    init_db(is_test_env=False)
    register_routers()
    _seed_desktop_paths(piper_bin_path, piper_voice_dir)

    from werkzeug.serving import make_server

    dora_port = _pick_free_port()
    dora_url = f"http://127.0.0.1:{dora_port}/"
    log.info("dora_api binding to %s", dora_url)

    dora_server = make_server("127.0.0.1", dora_port, dora_app, threaded=True)

    dora_thread = threading.Thread(
        target=dora_server.serve_forever, name="dora-flask", daemon=True,
    )
    dora_thread.start()

    if not _wait_for_health(f"{dora_url}api/health"):
        log.error("dora_api didn't answer /api/health within 5s; aborting")
        dora_server.shutdown()
        return 2

    spa_url = dora_url
    log.info("Flask ready; launching window at %s", spa_url)

    # pywebview/GTK turned out to be a deeper packaging fight than
    # was worth shipping for v1: PyGObject won't reliably install in
    # an isolated venv, and PyInstaller can't bundle the system `gi`
    # cleanly. The bundle opens the SPA in the user's default
    # browser instead and keeps the local Flask servers alive in the
    # foreground. Ctrl-C (or closing the launching terminal) shuts
    # everything down. Less native-feeling than a pywebview window
    # but reliable across Linux desktops. Revisit when there's time
    # to wrangle GTK bundling properly.
    import signal
    import webbrowser

    log.info("Opening %s in the default browser", spa_url)
    webbrowser.open(spa_url)

    stop = threading.Event()
    def _shutdown(*_: object) -> None:
        log.info("Shutdown signal received")
        stop.set()
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print("[dora] Browser launched. Press Ctrl-C to quit.", flush=True)
    try:
        stop.wait()
    finally:
        log.info("Shutting Flask server down")
        dora_server.shutdown()
        dora_thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
