"""Structured logging configuration shared across every service.

Each service calls `configure_logging("dapi", ...)` exactly once at
startup. The function is idempotent: re-calls clear and rebuild the
handlers, which makes restart-during-tests safe.

Formatter:
    %(asctime)s %(levelname)s [%(name)s] [req=%(request_id)s] [user=%(user_id)s] %(message)s

Handlers:
    stdout         — for docker-style log aggregation.
    TimedRotatingFile — ${log_dir}/<service>.log, rotates at local midnight,
                        14 daily backups kept (<service>.log.YYYY-MM-DD).
                        One file per date — current file only holds today's
                        entries. (FU-027)

Level:
    INFO by default, DEBUG when `debug=True` is passed (typically when
    DORA_CONFIG.is_debug_mode_enabled() is true).

Noise control:
    sqlalchemy.engine is pinned to WARNING regardless of root — its
    INFO/DEBUG output is the raw SQL stream, which is overwhelming and
    only useful when actively debugging a query.
    werkzeug stays at WARNING in production runs (its INFO is one line
    per request, which we already log ourselves via the middleware).
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from dora_api.infrastructure.log_context import LogContextFilter


_FORMAT = (
    "%(asctime)s %(levelname)-7s [%(name)s] "
    "[req=%(request_id)s] [user=%(user_id)s] %(message)s"
)

# One file per day; keep ~2 weeks of history.
_FILE_BACKUP_COUNT = 14


def configure_logging(
    service_name: str,
    log_dir: Path | str,
    *,
    level: int | None = None,
    debug: bool = False,
    quiet_modules: tuple[str, ...] = ("sqlalchemy.engine",),
    werkzeug_level: int = logging.WARNING,
) -> None:
    """Wire stdout + rotating-file handlers on the root logger with the
    request-context filter. Safe to call more than once.

    Note on `log_dir` — the caller chooses, deliberately per runtime:
        - dev / hosted web run: `./data/logs/<service>/`, co-located with the
          data dir so `tail -f data/logs/dapi/dapi.log` just works.
        - desktop build: `platformdirs.user_log_dir(...)`, the OS-standard
          per-user log location (survives reinstall, no root needed). On
          Linux that's `~/.local/state/dashy-dora/logs`, on macOS
          `~/Library/Logs/dashy-dora`, on Windows `%LOCALAPPDATA%\\dashy-dora\\logs`.
        The split is intentional (FU-509): OS convention on packaged
        distributions, developer convenience on unpackaged runs. Both are
        correct for their runtime; this function doesn't care which.

    Args:
        service_name: Short identifier ("dapi"). Used for the log file name.
        log_dir: Directory the rotating log file goes in. Created if
            missing.
        level: The root level, already resolved (`DoraConfig.get_log_level`:
            env > JSON > profile default). None → DEBUG when `debug`, else
            INFO — the historical default for callers that pass no level.
        debug: Pull root + module loggers up to DEBUG. Off in production.
        quiet_modules: Loggers pinned to WARNING regardless of root. The
            default silences SQLAlchemy's raw-SQL echo.
        werkzeug_level: Override the Werkzeug request-log level. Defaults
            to WARNING because the request middleware already emits an
            equivalent line.
    """
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    # Replace existing handlers so re-invocation (tests, dev reloads)
    # doesn't accumulate duplicates.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # The level is independent of debug MODE so a runtime can stay in
    # debug/seed mode while logging quietly — the e2e backend needs debug
    # mode (create_all + seed) but the per-request DEBUG body-dumps + INFO
    # request lines, each written to the rotating FILE handler, dominate its
    # latency and degrade the long single-worker run (FU-591).
    root.setLevel(level if level is not None else (logging.DEBUG if debug else logging.INFO))

    formatter = logging.Formatter(_FORMAT)
    context_filter = LogContextFilter()

    # FU-569: Windows consoles default to a legacy code page (cp1252), which
    # can't encode the → / ← glyphs in the request-log lines — or any
    # non-ASCII user content that ends up in a log message — so every emit
    # printed a "--- Logging error ---" traceback to stderr, drowning real
    # errors on the exact platform the desktop bundle targets. Re-encode the
    # console stream as UTF-8 (errors='replace' so logging can never crash
    # on output again). The file handler below was already utf-8.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass  # detached/odd stream (e.g. some embedders) — leave as-is
    stream = logging.StreamHandler(stream=sys.stdout)
    stream.setFormatter(formatter)
    stream.addFilter(context_filter)
    root.addHandler(stream)

    rotating = TimedRotatingFileHandler(
        log_dir_path / f"{service_name}.log",
        when="midnight",
        backupCount=_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    # Rotated files become <service>.log.YYYY-MM-DD so the active file
    # only ever contains entries from the current date (FU-027).
    rotating.suffix = "%Y-%m-%d"
    rotating.setFormatter(formatter)
    rotating.addFilter(context_filter)
    root.addHandler(rotating)

    for name in quiet_modules:
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(werkzeug_level)
