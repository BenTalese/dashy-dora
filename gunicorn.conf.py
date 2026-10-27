# Gunicorn config for the Dashy Dora self-host container (FU-397).
#
# Loaded via `gunicorn -c gunicorn.conf.py dora_api.wsgi:app` from startup.sh
# when the container runs in production. Every knob is env-driven per the
# distribution-posture checklist (RECONCILED_FINISHING_PLAN §7.5 #3) so the
# same image tunes without an edit.
#
# ── Single worker on purpose ──────────────────────────────────────────────
# The app runs an in-process APScheduler (audit-log prune, alerts digest/push,
# demo reset, snooze cleanup — see dora_api/startup.py). Those jobs must fire
# exactly once, so the default is ONE worker: one process, one scheduler, no
# duplicate emails/pushes. Concurrency comes from threads (gthread worker),
# which is the right shape for this I/O-bound Flask app in a single-instance
# self-host. Raising the worker count would duplicate the scheduled jobs — the
# fix for real horizontal scale (externalise the scheduler + split web/worker
# tiers) is parked in OPTIONAL_SAAS_AND_MANAGED_DEPLOYMENT.md, deliberately out
# of scope for the self-host release. If you set DORA_WEB_CONCURRENCY>1 anyway,
# the warning below fires at boot.
import os
import sys


def _int(name: str, default: int) -> int:
    # Mirrors `configuration_manager._env_int` on purpose: this file must stay
    # import-light (gunicorn loads it before the app exists), so it cannot
    # import dora_api (finalisation 19-R8, R-003 carve-out).
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Bind mirrors the API host/port the Flask dev server used (DORA_API_HOST /
# DORA_API_PORT), so nginx's upstream (:5170) is unchanged whichever server
# runs. `DORA_BIND` overrides the whole "host:port" string if needed.
_host = os.environ.get("DORA_API_HOST") or "0.0.0.0"
_port = _int("DORA_API_PORT", 5170)
bind = os.environ.get("DORA_BIND") or f"{_host}:{_port}"

# Threaded single worker (see the header note). Both tunable via env.
workers = max(1, _int("DORA_WEB_CONCURRENCY", 1))
threads = max(1, _int("DORA_WEB_THREADS", 4))
worker_class = "gthread"

# A slow request (large import, PDF render, TTS synth) shouldn't get the
# worker killed at gunicorn's 30s default. Tunable; 0 disables the timeout.
timeout = _int("DORA_WEB_TIMEOUT", 120)
graceful_timeout = _int("DORA_WEB_GRACEFUL_TIMEOUT", 30)
keepalive = _int("DORA_WEB_KEEPALIVE", 5)

# Logs → stdout/stderr so `docker logs` captures them (the app's own file
# logging via logging_setup keeps writing to the log dir alongside this).
accesslog = "-"
errorlog = "-"
loglevel = (os.environ.get("DORA_GUNICORN_LOG_LEVEL") or "info").lower()

# Identify the process in `ps` / logs.
proc_name = "dora_api"


def on_starting(server):
    """Loud, one-time warning if the operator scaled past a single worker —
    the in-process scheduler would then run once per worker and duplicate
    every scheduled job (digests, pushes, demo resets)."""
    if workers > 1:
        server.log.warning(
            "DORA_WEB_CONCURRENCY=%s (>1): the in-process scheduler will run "
            "in EVERY worker, so scheduled jobs (alerts digest/push, audit "
            "prune, demo reset) will fire once PER worker. Run a single worker "
            "for a self-host instance; horizontal scale needs the worker-split "
            "work in OPTIONAL_SAAS_AND_MANAGED_DEPLOYMENT.md.",
        )
        print(
            "[gunicorn] WARNING: DORA_WEB_CONCURRENCY>1 duplicates scheduled "
            "jobs; see gunicorn.conf.py.",
            file=sys.stderr,
            flush=True,
        )
