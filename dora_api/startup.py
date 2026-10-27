import logging
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

_LOGGER = logging.getLogger(__name__)

# Load repo-root .env before any dora_api import — configuration_manager reads
# os.environ at import time. Real shell/Docker env vars still win (override=False).
load_dotenv(find_dotenv(), override=False)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from flask_cors import CORS
from flask_migrate import upgrade
from werkzeug.exceptions import HTTPException

from dora_api.app import app, db
from dora_api.infrastructure.api_response import internal_server_error
from dora_api.infrastructure.audit_retention import prune_audit_events
from dora_api.infrastructure.configuration_manager import DORA_CONFIG
from dora_api.infrastructure.logging_setup import configure_logging
from dora_api.infrastructure.middleware import MIDDLEWARE
from dora_api.infrastructure.profile import is_test
from dora_api.infrastructure.utils import get_attributes_ending_with
from dora_api.persistence.seed import seed_dev_data
from dora_api.persistence.seed_dense import seed_dense_data
from dora_api.persistence.seed_showcase import reset_showcase


def bootstrap(is_test_env: bool = False):
    """Wire the app up to the point of serving — everything `startup()`
    used to do *except* the blocking `app.run()`.

    FU-397: split out so a production WSGI server (gunicorn) can import a
    fully-configured `app` via `dora_api.wsgi` without going through Flask's
    dev server. `startup()` (dev / desktop-adjacent path) calls this and then
    blocks on `app.run()`; the WSGI entry point calls this at import time and
    hands `app` to gunicorn. The e2e suite calls it via `startup(is_test_env
    =True)`, exercising the same setup path.

    Runs CORS wiring, legacy-path migrations, DB init/upgrade, logging,
    router registration, and — outside tests — the background scheduler.
    """
    # D3: refuse to boot in production when required env vars are
    # missing. No-op in dev/test. Runs before *anything* else so the
    # friendly error fires before we read appsettings, wire routes, etc.
    from dora_api.infrastructure.profile import (
        validate_production_requirements,
        warn_if_insecure_cookies_in_production,
    )
    validate_production_requirements()
    warn_if_insecure_cookies_in_production()

    # D3: profile-aware CORS pinning. Dev = open localhost list, prod
    # = whatever DORA_CORS_ORIGINS contains (validated to be non-empty
    # by validate_production_requirements() above).
    # supports_credentials must be True for the browser to send the
    # `dora_session` cookie cross-origin. Origins must be an explicit
    # list (never '*') when credentials are enabled — the browser
    # refuses the wildcard in that case.
    CORS(
        app,
        resources={r'/api/*': {
            'origins': DORA_CONFIG.get_cors_origins(),
            'allow_headers': ['Content-Type', 'X-Request-Id', 'X-CSRF-Token'],
            'supports_credentials': True,
        }},
    )

    # D2: legacy-path migrations run *before* init_db so a relocated
    # DB file is in its new home by the time SQLAlchemy opens it.
    # the legacy-DB migration is a SQLite-only file move; skip it
    # when running on Postgres (no file to relocate).
    from dora_api.infrastructure.path_migration import (
        migrate_legacy_db, migrate_legacy_uploads,
    )
    _db_url = DORA_CONFIG.get_db_connection_string()
    if _db_url.startswith("sqlite:///"):
        migrate_legacy_db(Path(_db_url.removeprefix("sqlite:///")))
    migrate_legacy_uploads(DORA_CONFIG.get_uploads_dir())

    init_db(is_test_env)
    _warn_on_schema_drift()
    configure_logging(
        "dapi",
        DORA_CONFIG.get_log_dir(),
        debug=DORA_CONFIG.is_debug_mode_enabled(),
    )
    register_routers()

    # Skip the scheduler in tests (the `is_test_env` flag) AND whenever the
    # profile is `test` — the latter guards the WSGI import path (FU-397): a
    # test that imports `dora_api.wsgi` under DORA_ENV=test must not spawn a
    # real background thread. In a single-worker gunicorn (the default, see
    # gunicorn.conf.py) this scheduler runs in exactly one process, so the
    # daily/hourly jobs fire once. Running >1 worker would duplicate them —
    # that needs the worker-split / externalised-scheduler work parked in
    # OPTIONAL_SAAS_AND_MANAGED_DEPLOYMENT.md.
    if not is_test_env and not is_test():
        # Nightly audit-log retention sweep. Hour 3 local time keeps it
        # well clear of the 07:00 deals-email send. Tests skip the
        # scheduler entirely — they don't run long enough to trip it,
        # and we don't want a background thread surviving the test
        # session.
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            prune_audit_events,
            CronTrigger(hour=3, minute=0),
            id="audit_retention",
            replace_existing=True,
        )
        # (No alerts email digest — cut at Step-0 Q4,
        # `IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`. Web push already delivers
        # the same set instantly and needs no SMTP, and the 19:00 daily brief
        # covers the "what's coming" digest shape that was actually asked for.)

        # Daily prune of elapsed suggestion snoozes. Moved off the
        # GET /api/suggestions read path per FU-513 (2026-07-08); the
        # read filter already ignores expired snoozes for correctness,
        # this just keeps the table from accreting stale rows. 03:30
        # staggers cleanly from the 03:00 audit sweep.
        from dora_api.features.suggestions.prune_expired_snoozes import \
            prune_expired_snoozes
        scheduler.add_job(
            prune_expired_snoozes,
            CronTrigger(hour=3, minute=30),
            id="suggestions_snooze_cleanup",
            replace_existing=True,
        )
        # alerts web-push. Hourly at :30 so it staggers from the
        # email digest's 07:00 fire. The job self-gates when VAPID isn't
        # configured (returns 0 without mutating the ledger) so an
        # unconfigured install spends nothing.
        from dora_api.features.alerts.send_alerts_push import \
            send_alerts_push
        scheduler.add_job(
            send_alerts_push,
            CronTrigger(minute=30),
            id="alerts_push",
            replace_existing=True,
        )
        # Daily brief push. Registered **hourly** rather than pinned to the
        # send hour: this cron fires in the *server's* timezone, while the
        # brief must land at 19:00 **household** time (R-021), and the
        # household timezone is a runtime AppSetting. The job gates on the
        # household clock internally, so changing the timezone in Settings
        # takes effect that same evening instead of at the next restart.
        # Minute 45 staggers it off the :30 alerts push. Self-gates when
        # VAPID isn't configured, same as its sibling.
        from dora_api.features.alerts.send_daily_brief import send_daily_brief
        scheduler.add_job(
            send_daily_brief,
            CronTrigger(minute=45),
            id="daily_brief",
            replace_existing=True,
        )
        # Weekly deals email (FU-789). Hourly for the same reason the brief is:
        # the send hour is household-local (R-021) and each subscriber picks
        # their own weekday, both of which are runtime settings the startup-time
        # cron can't see. The job gates on all of it internally and self-gates
        # when SMTP or the install-wide flag is off, so an install that never
        # configured email spends one cheap check an hour. Minute 15 staggers it
        # off the :30 alerts push and the :45 brief.
        from dora_api.features.deals.send_deals_email import send_deals_email
        scheduler.add_job(
            send_deals_email,
            CronTrigger(minute=15),
            id="deals_email",
            replace_existing=True,
        )
        # Demo / sellable-showcase auto-reset (FU-392). When the install is
        # booted in demo mode, wipe + re-seed the curated showcase dataset on
        # a fixed interval so anyone poking at the demo starts from a clean,
        # coherent state. DORA_DEMO_RESET_MINUTES=0 disables the reset (the
        # boot-time seed still runs), leaving a static demo.
        if DORA_CONFIG.is_demo_mode_enabled():
            _reset_minutes = DORA_CONFIG.get_demo_reset_minutes()
            if _reset_minutes > 0:
                scheduler.add_job(
                    reset_showcase,
                    IntervalTrigger(minutes=_reset_minutes),
                    id="demo_reset",
                    replace_existing=True,
                )
        scheduler.start()


def startup(is_test_env: bool = False):
    """Dev / local entry point: wire everything up, then block on Flask's
    dev server. Production uses a real WSGI server instead (gunicorn →
    `dora_api.wsgi:app`); see startup.sh + gunicorn.conf.py (FU-397). Tests
    call this with `is_test_env=True` to run the setup without blocking.
    """
    bootstrap(is_test_env)

    if not is_test_env:  # app.run blocks the thread where tests are ran from
        app.run(
            DORA_CONFIG.get_api_host(),
            DORA_CONFIG.get_api_port(),
            DORA_CONFIG.is_debug_mode_enabled(),
            use_reloader = DORA_CONFIG.is_reloader_enabled()
        )


def _seed_local_product_search_url():
    """Dev-only: point Product Search at a companion on this workstation.

    Writes the AppSetting directly rather than going through
    `UpdateAppSettingsHandler` — this runs mid-`init_db`, before the routers
    and their DI are wired, and the handler adds nothing here beyond a scheme
    check on a constant. `scripts/set_product_search_url.py` (the deploy path,
    which takes operator input) does go through the handler.
    """
    from dora_api.features.app_settings.access import get_or_create_app_setting
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    repository = SqlAlchemyRepository()
    get_or_create_app_setting(repository).product_search_url = "http://localhost:5175"
    repository.save_changes()


def init_db(is_test_env: bool):
    # Demo / sellable-showcase mode (FU-392) takes precedence over the
    # normal seed/upgrade decision. It seeds the curated showcase dataset
    # destructively in ANY profile (dev or prod) — the demo install is
    # disposable by design and re-seeds on a schedule (see the reset job
    # in startup()). It deliberately bypasses is_seed_allowed()'s
    # production guard because the operator opted in via DORA_DEMO_MODE.
    if DORA_CONFIG.is_demo_mode_enabled():
        reset_showcase()
        return

    with app.app_context():
        # D3: is_seed_allowed() refuses in production regardless of
        # DORA_ALLOW_DESTRUCTIVE, so a misconfigured prod deploy can't
        # accidentally wipe its own database on boot.
        if is_test_env or (DORA_CONFIG.is_debug_mode_enabled() and DORA_CONFIG.is_seed_allowed()):
            db.drop_all()
            db.create_all()

            # Point Product Search at a companion running on this workstation.
            # The nav entry stays hidden while `product_search_url` is empty,
            # and a dev boot wipes the DB — so without this the companion is a
            # port you have to remember and re-type on the admin page after
            # every restart. Set here rather than inside a seed function
            # because the two datasets diverge below (dense returns early), and
            # this should hold for both. Excluded from `is_test_env`: the e2e
            # suite asserts against a blank default, and a dev convenience has
            # no business moving that baseline. The deployed install gets its
            # own value from the deploy script; a real install has an admin
            # type one in.
            if not is_test_env:
                _seed_local_product_search_url()

            _qa_fixtures = (
                not is_test_env and DORA_CONFIG.is_qa_fixture_seed_enabled()
            )
            # Two dev datasets (owner call, 2026-08-31) — see
            # DoraConfig.get_seed_dataset() for which answers what. `dense` is
            # the default for an interactive boot: hand-placed depth, no filler.
            #
            # The e2e suite is pinned to `bulk` regardless of the env var: it
            # asserts against that dataset's specific fixtures, so letting a
            # shell variable swap its data out would break ~2200 tests for a
            # reason unrelated to the code under test.
            if not is_test_env and DORA_CONFIG.get_seed_dataset() == "dense":
                # `money_on=True` is stated here rather than left to the
                # parameter default: the dense dataset deliberately does NOT
                # consult DORA_SEED_MONEY_ON (which defaults to false), and a
                # silent default would make that env var look like it applies
                # when it doesn't. Dense boots every optional install surface on
                # — a gated-off feature renders nothing, and this dataset exists
                # to show every path. See seed_dense_data's docstring.
                seed_dense_data(qa_fixtures=_qa_fixtures, money_on=True)
                return
            # FU-388 — the bulk dataset seeds under load (default 500 extra
            # items); the e2e suite passes 0 so its boot stays fast.
            seed_dev_data(
                bulk_stock_items=(
                    0 if is_test_env
                    else DORA_CONFIG.get_seed_bulk_stock_item_count()
                ),
                qa_fixtures=_qa_fixtures,
                money_on=(
                    not is_test_env and DORA_CONFIG.is_seed_money_on()
                ),
            )
            return

        if DORA_CONFIG.is_debug_mode_enabled():
            # Create any missing tables for local dev, but never drop existing data.
            # Set DORA_ALLOW_DESTRUCTIVE=true to wipe and re-seed (dev only).
            db.create_all()
            return

        upgrade()


def _warn_on_schema_drift() -> None:
    """FU-570 — after DB init, compare the live schema against the models the
    code expects and log a loud banner on drift (missing tables or columns).

    This is the guard the pilot lacked: it booted clean against a stale,
    `create_all`-built `dora.data.db` (old columns, no `alembic_version`) and
    then 500'd request-by-request on the missing columns, with no boot-time
    complaint. A names-only comparison (not types) keeps it portable across
    SQLite/Postgres and avoids false positives.

    Warn, don't refuse: a dev boot against a freshly `create_all`-built DB is
    always current and sees nothing; we'd rather serve with a loud warning
    than block a boot on a spurious mismatch. A genuinely stale DB now
    announces itself at boot instead of failing silently per request.
    """
    try:
        with app.app_context():
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            missing_tables: list[str] = []
            missing_columns: list[str] = []
            for table_name, table in db.metadata.tables.items():
                if table_name not in existing_tables:
                    missing_tables.append(table_name)
                    continue
                actual_cols = {c["name"] for c in inspector.get_columns(table_name)}
                for column in table.columns:
                    if column.name not in actual_cols:
                        missing_columns.append(f"{table_name}.{column.name}")
            if missing_tables or missing_columns:
                _LOGGER.error(
                    "SCHEMA DRIFT DETECTED — the connected database is behind "
                    "the code's models; requests touching the missing schema "
                    "will 500. Missing tables: %s. Missing columns: %s. Fix: run "
                    "migrations (`flask db upgrade`) against this DB, or recreate "
                    "it (dev: DORA_ALLOW_DESTRUCTIVE=true to wipe + reseed). "
                    "See FU-570.",
                    sorted(missing_tables) or "none",
                    sorted(missing_columns) or "none",
                )
    except Exception as exc:  # noqa: BLE001
        # Best-effort diagnostics — never block boot on the guard itself.
        _LOGGER.warning("schema-drift check failed: %s", exc)


def register_routers():
    # Lazy meal-plan reconciliation. Any read against recipes or meal
    # plans triggers the past-day consumption sweep first, so the pool
    # counts displayed to the user are always current. Idempotent via
    # conditional UPDATE in the helper. Must be attached *before*
    # register_blueprint — Flask freezes blueprint setup at registration.
    from dora_api.features.meal_plans.reconcile_consumed_meals import \
        reconcile_consumed_meals
    from dora_api.features.routers import (DASHBOARD_ROUTER, MEAL_PLAN_ROUTER,
                                           RECIPE_ROUTER)

    @DASHBOARD_ROUTER.before_request
    @MEAL_PLAN_ROUTER.before_request
    @RECIPE_ROUTER.before_request
    def _reconcile():
        # Swallow + log failures so a broken reconciliation can't 500
        # every recipe / meal-plan / dashboard read. Stale pool counts
        # are recoverable; total page failure isn't.
        try:
            reconcile_consumed_meals()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "reconcile_consumed_meals failed; serving stale pool counts"
            )

    for _Router in get_attributes_ending_with('router', Path() / 'dora_api' / 'features'):
        app.register_blueprint(_Router)
    app.register_blueprint(MIDDLEWARE)


@app.errorhandler(Exception)
def handle_global_exception(error: Exception):
    # Deliberate HTTP errors (abort(404), abort(503), …) must pass through
    # with their intended status — before this guard, EVERY abort() in the
    # app was being rewritten into an opaque 500 "unexpected error" (found
    # via the SPA catch-all's 404/503 during the UX-v2 endpoint removals).
    # Only genuinely unhandled exceptions become 500s.
    if isinstance(error, HTTPException):
        return error
    # a handler that raises after add()/flush() but
    # before commit leaves dirty state on the request-scoped session.
    # Flask-SQLAlchemy's teardown does eventually `session.remove()`
    # (which rolls back), but doing it explicitly here removes the
    # window where a later teardown-time SQL error could obscure the
    # original one, and makes the "500 means clean" contract obvious to
    # anyone reading the handler. Full unit-of-work refactor of the
    # multi-commit `create_recipe.py` path stays as its own FU.
    try:
        db.session.rollback()
    except Exception:  # noqa: BLE001
        logging.getLogger().exception("rollback in global handler failed")
    logging.getLogger().exception("Unhandled exception", exc_info=error)
    return internal_server_error("An unexpected error occurred.")


if __name__ == '__main__':
    startup()
