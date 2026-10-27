import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

from dora_api.infrastructure.profile import (Profile, current_profile,
                                             env_flag, is_production)


class Config(BaseModel):
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 5170
    LOG_LEVEL: str = "ERROR"


# D3: per-profile defaults for things that meaningfully differ between
# dev and prod. The JSON appsettings still wins when an operator pins
# a value there, and env vars still win over JSON — these are just the
# "what should it be when nothing's pinned" fallbacks.
_PROFILE_DEFAULTS = {
    Profile.DEVELOPMENT: {
        "log_level": "DEBUG",
        "debug": True,
        # Dev SPA runs on localhost ports; permissive list to cover
        # `quasar dev` (5174) and the various ways a browser might
        # reach it on a dev machine. The `capacitor://localhost` /
        # `http://localhost` origins are for the Capacitor mobile
        # client (Quasar `-m capacitor`) talking to a dev backend on
        # the same machine; iOS uses `capacitor://`, Android uses
        # `http://localhost`. Pin via DORA_CORS_ORIGINS in prod.
        "cors_origins": [
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://172.17.0.1:5174",
            "capacitor://localhost",
            "ionic://localhost",
            "http://localhost",
        ],
    },
    Profile.PRODUCTION: {
        "log_level": "INFO",
        "debug": False,
        # No safe default for prod CORS — has to be pinned via
        # DORA_CORS_ORIGINS (the production-requirements check refuses
        # to boot without it).
        "cors_origins": [],
    },
    Profile.TEST: {
        "log_level": "WARNING",
        "debug": True,
        "cors_origins": ["http://localhost:5174"],
    },
}


def _env(name: str, default: str | None = None) -> str | None:
    """Resolve an env var, treating empty strings as unset so an
    accidental `DORA_API_PORT=` in .env doesn't blow up int parsing."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _default_postgres_url() -> str:
    """Default Postgres URL matches the bundled docker-compose service.
    Override every component (or the whole URL) via env vars for any
    other deployment."""
    host = _env("DORA_DB_HOST", "localhost") or "localhost"
    port = _env("DORA_DB_PORT", "5432") or "5432"
    name = _env("DORA_DB_NAME", "dora") or "dora"
    user = _env("DORA_DB_USER", "dora") or "dora"
    password = _env("DORA_DB_PASSWORD", "dora") or "dora"
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


def _sqlite_url_from_path(raw: str) -> str:
    """Build a SQLAlchemy SQLite URL from a plain filesystem path.

    Friendlier than asking the user to remember that `sqlite:///` takes
    three slashes for a relative path and four for an absolute one. We
    resolve to an absolute path and always emit the four-slash form so
    Flask doesn't reinterpret it against its instance dir.
    `Path.as_posix()` normalises Windows backslashes so the URL parses
    on every platform."""
    return f"sqlite:///{Path(raw).expanduser().resolve().as_posix()}"


def _resolve_config_path() -> Path:
    """D3: appsettings.json lives under <DATA_DIR>/config/ so the
    operator's persistent overrides ride the data volume. The legacy
    `./config/dapi.appsettings.json` location is migrated by
    path_migration.migrate_legacy_appsettings() on startup."""
    data_dir = _env("DORA_DATA_DIR", "data")
    return (Path(data_dir).expanduser().resolve()) / "config" / "dapi.appsettings.json"


class DoraConfig:
    _config: Config
    _config_path: Path

    def __init__(self):
        self._config_path = _resolve_config_path()
        # D3: relocated to <DATA_DIR>/config/. Attempt to move a
        # legacy ./config/dapi.appsettings.json into the new home so
        # operators that customised it don't silently lose their
        # tweaks. Must happen before the file-exists check so the
        # generated-defaults branch doesn't overwrite the moved file.
        try:
            from dora_api.infrastructure.path_migration import \
                migrate_legacy_appsettings
            migrate_legacy_appsettings(self._config_path)
        except Exception:
            # Migration is best-effort — never block startup over it.
            pass

        if not Path.exists(self._config_path):
            # D3: generate sensible defaults on first boot. Operators
            # can edit afterwards; env vars still win.
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, 'w') as _AppSettings:
                _AppSettings.write(Config().model_dump_json(indent = 4))

        with open(self._config_path, 'r') as _AppSettings:
            self._config = Config(**json.load(_AppSettings))

    def get_profile(self) -> Profile:
        return current_profile()

    # ── Env-var-first getters ─────────────────────────────────────────
    # Every getter reads the relevant env var first and falls back to
    # the JSON appsettings value. The JSON file is still the source of
    # truth for un-overridden values + dev defaults, but containerised
    # deployments can override any of these via .env without editing
    # files in the image.

    def get_api_host(self) -> str:
        return _env("DORA_API_HOST", self._config.API_HOST) or self._config.API_HOST

    def get_api_port(self) -> int:
        return _env_int("DORA_API_PORT", self._config.API_PORT)

    def get_db_connection_string(self) -> str:
        # Postgres is the standard datastore (Decision 5,
        # RECONCILED_FINISHING_PLAN.md §7.5). Resolution order:
        #   1. `DORA_DB_URL` if set — full override, any SQLAlchemy URL.
        #      Use this when pointing at a remote Postgres, a custom
        #      driver, an in-memory SQLite, anything non-standard.
        #   2. `DORA_DB_PATH` if set — SQLite shortcut. Just a filesystem
        #      path (e.g. `./data/dora.data.db` or `/var/lib/dora/db`);
        #      the app builds the correct `sqlite:///<abs>` URL so the
        #      user doesn't have to remember the slash-count quirk. This
        #      is the simplest way to run on SQLite for lightweight
        #      self-host.
        #   3. Per-component Postgres env vars (`DORA_DB_HOST`, `_PORT`,
        #      `_NAME`, `_USER`, `_PASSWORD`) — useful when secrets come
        #      from the environment but the shape is fixed.
        #   4. Default: localhost:5432 / user `dora` / db `dora` — matches
        #      the bundled `compose.dev.yml` Postgres service.
        explicit_url = _env("DORA_DB_URL")
        if explicit_url:
            if explicit_url.startswith("sqlite:///"):
                # Ensure the parent directory exists for file-backed SQLite,
                # mirroring the legacy behaviour.
                path = Path(explicit_url.removeprefix("sqlite:///")).expanduser().resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
            return explicit_url
        sqlite_path = _env("DORA_DB_PATH")
        if sqlite_path:
            url = _sqlite_url_from_path(sqlite_path)
            # Ensure the parent dir exists so a fresh install can write.
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
            return url
        return _default_postgres_url()

    def get_log_level(self) -> int:
        """Root log level: `DORA_LOG_LEVEL` > JSON `LOG_LEVEL` > the profile
        default. The JSON default is "ERROR" (legacy); that value means "use
        the profile default" so dev gets DEBUG without an explicit override.
        An unknown name is warned about once and falls back to the profile
        default rather than silently resolving to NOTSET. This is the one
        resolver — `configure_logging` takes its result (finalisation 19-R5;
        it used to re-read the env var itself and ignore the JSON layer)."""
        env_value = _env("DORA_LOG_LEVEL")
        json_value = self._config.LOG_LEVEL
        profile_default = _PROFILE_DEFAULTS[current_profile()]["log_level"]
        if env_value:
            name = env_value.strip().upper()
        elif json_value and json_value.upper() != "ERROR":
            name = json_value.strip().upper()
        else:
            name = profile_default

        level = logging.getLevelNamesMapping().get(name)
        if level is None:
            logging.getLogger(__name__).warning(
                "Unknown log level %r; using the %s profile default %s",
                name, current_profile().value, profile_default,
            )
            level = logging.getLevelNamesMapping()[profile_default]
        return level

    def get_cors_origins(self) -> list[str]:
        """Comma-separated list from DORA_CORS_ORIGINS; falls back to
        the profile default. Production has no fallback — the env var
        must be set (validated by validate_production_requirements())."""
        raw = _env("DORA_CORS_ORIGINS")
        if raw:
            return [o.strip() for o in raw.split(",") if o.strip()]
        return list(_PROFILE_DEFAULTS[current_profile()]["cors_origins"])

    def get_trusted_proxy_hops(self) -> int:
        """How many reverse proxies sit in front of the API, i.e. how many
        `X-Forwarded-For` entries to trust (`DORA_TRUSTED_PROXY_HOPS`).

        0 (the default) = no proxy: `request.remote_addr` is the client. Set
        to 1 behind one proxy (nginx / Caddy / Traefik / a Cloudflare tunnel)
        so the login rate limit and the audit log see the real client address
        instead of the proxy's. Never set it higher than the proxies you
        actually control — each hop you trust is an address a direct client
        can forge. Negative or unparseable values are treated as 0."""
        return max(0, _env_int("DORA_TRUSTED_PROXY_HOPS", 0))

    def is_seed_allowed(self) -> bool:
        """Dev seed only runs in development; production refuses
        regardless of DORA_ALLOW_DESTRUCTIVE."""
        if is_production():
            return False
        return env_flag("DORA_ALLOW_DESTRUCTIVE")

    def is_demo_mode_enabled(self) -> bool:
        """Demo / sellable-showcase mode (FU-392). When on, the install
        serves a curated showcase dataset, shows a persistent demo banner,
        and periodically resets itself back to the baseline so a prospect
        clicking around can't permanently alter it.

        Operator/deployment decision, set via env — deliberately NOT an
        admin AppSetting, so a prospect exploring the (admin) demo user
        can't switch it off from Settings. Off by default. Unlike the dev
        seed this is allowed to (re)seed destructively in ANY profile,
        including production-like ones a public demo would run under for
        HTTPS/secure-cookie reasons — the dataset is disposable by design."""
        return env_flag("DORA_DEMO_MODE")

    def get_demo_reset_minutes(self) -> int:
        """How often the demo dataset is reset back to the curated showcase
        baseline, in minutes. Default 60. 0 disables the scheduled reset
        (the boot seed still runs; the instance just isn't auto-refreshed).
        Only consulted when is_demo_mode_enabled()."""
        return _env_int("DORA_DEMO_RESET_MINUTES", 60)

    def get_seed_dataset(self) -> str:
        """Which dev dataset an interactive boot seeds: `dense` (default) or
        `bulk`.

        Two datasets answer two different questions and neither replaces the
        other (owner call, 2026-08-31):

        * **dense** (`seed_dense.py`) — no generated filler. Every row is
          hand-placed to put some surface into a state worth walking: a recipe
          with ten structured steps and sub-steps, a stock item with nothing
          on it at all next to one with everything, all three step modes, a
          three-week meal plan, a believable three months of shopping history.
          This is what you want when you're *looking at* the app.
        * **bulk** (`seed.py`) — the curated set plus `DORA_SEED_BULK_ITEMS`
          generated items, so N+1s and slow queries surface at volume. This is
          what you want when you're *load-testing* the app.

        Only consulted for interactive dev boots. The backend e2e suite always
        seeds `bulk` regardless of this setting: ~2200 tests assert against
        that dataset's specific fixtures, so making the suite's data depend on
        an env var would make it fail for a reason that has nothing to do with
        the code under test. See `startup.init_db`.
        """
        value = _env("DORA_SEED_DATASET", "dense").strip().lower()
        return value if value in {"dense", "bulk"} else "dense"

    def get_seed_bulk_stock_item_count(self) -> int:
        """FU-388 — how many extra 'load' stock items the dev seed generates
        on top of the curated fixture set, so an interactive dev session
        always runs against a realistic pantry (default 500) and N+1s /
        slow queries surface naturally rather than only under a paying
        user's data. Tune via DORA_SEED_BULK_ITEMS; set 0 to disable the
        load (back to the small curated set). Only consulted for the *dev*
        seed — the e2e test suite passes 0 explicitly (see startup.init_db)
        so its boot stays fast."""
        return max(0, _env_int("DORA_SEED_BULK_ITEMS", 500))

    def is_qa_fixture_seed_enabled(self) -> bool:
        """Whether the dev seed also creates the deterministic QA fixtures
        the browser-E2E suite (FU-540 layer) asserts against — e.g. the
        buy-verdict "skip + mark_stocked" item, which needs backdated
        purchase/waste history no API can create. Off by default so an
        interactive dev pantry isn't cluttered; the Playwright webServer
        sets DORA_SEED_QA_FIXTURES=true."""
        return env_flag("DORA_SEED_QA_FIXTURES")

    def is_seed_money_on(self) -> bool:
        """FU-592 — whether the dev seed boots with money + nutrition features
        already enabled at both gating layers (the install flags AND the dev
        user's per-user opt-ins), so the flag-gated UI (cost/kcal cards,
        buy-verdict, budget) is verifiable in a cold-mount browser pane where
        mid-session flips don't re-render. Off by default; the
        dora-verify-backend-money launch profile sets DORA_SEED_MONEY_ON=true.

        **Applies to the `bulk` dataset only.** The `dense` dataset boots money
        on unconditionally (see `seed_dense_data`), so this flag is not read on
        that path — don't reach for it expecting to turn money off there."""
        return env_flag("DORA_SEED_MONEY_ON")

    def get_data_dir(self) -> Path:
        """Persistent runtime data — sqlite db, secret_key, staged
        uploads. Defaults to `./data` for dev; `/app/data` in container."""
        path = _env("DORA_DATA_DIR", "data")
        resolved = Path(path).expanduser().resolve()  # type: ignore[arg-type]
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def get_uploads_dir(self) -> Path:
        """Chunked uploads staged here before being inspected /
        committed. Lives under the data dir so backups capture
        in-flight uploads too. Stale entries swept by the uploads
        feature."""
        path = self.get_data_dir() / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_backups_dir(self, override: str | None = None) -> Path:
        """Where the backup library persists its files. Default:
        `<DATA_DIR>/backups`. An admin can override via
        `AppSetting.backup_storage_path` (validated on save) to point
        at an external mount / NAS. Empty override falls back to the
        default. The caller (backup_library.py) passes the AppSetting
        value; we own path resolution + dir creation."""
        if override:
            path = Path(override).expanduser().resolve()
        else:
            path = self.get_data_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_voices_dir(self) -> Path:
        """Where Piper TTS voice models (`.onnx` + `.onnx.json`) are stored.
        Downloaded on demand from the catalog (see features/tts) into the data
        dir so they persist across restarts (captured by backups, ride a
        mounted volume) and never bloat the repo. `DORA_PIPER_VOICE_DIR`
        overrides the location for operators who stage models elsewhere."""
        override = _env("DORA_PIPER_VOICE_DIR")
        if override:
            path = Path(override).expanduser().resolve()
        else:
            path = self.get_data_dir() / "voices"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_log_dir(self) -> Path:
        """Where logging_setup.py drops rotated log files. Defaults to
        `<DATA_DIR>/logs/dapi` so logs sit next to other runtime
        state."""
        path = _env("DORA_LOG_DIR")
        if path:
            resolved = Path(path).expanduser().resolve()
        else:
            resolved = self.get_data_dir() / "logs" / "dapi"
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def get_cache_dir(self) -> Path:
        """Image / scraped-data cache dir. Defaults to `./cache` for
        dev; `/app/cache` in container."""
        path = _env("DORA_CACHE_DIR", "cache")
        resolved = Path(path).expanduser().resolve()  # type: ignore[arg-type]
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def is_debug_mode_enabled(self) -> bool:
        # D3: explicit env wins; otherwise pick the profile default.
        if _env("DORA_DEBUG") is None:
            return bool(_PROFILE_DEFAULTS[current_profile()]["debug"])
        return env_flag("DORA_DEBUG")


DORA_CONFIG = DoraConfig()
