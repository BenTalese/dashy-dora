"""GET /api/health — readiness + compatibility probe.

Two callers in mind:
  - Container HEALTHCHECK / monitoring → cares about HTTP 200.
  - Mobile + desktop clients → reading the JSON body to decide
    whether the backend version is compatible with the client
    (`schema_version` lets a thin client refuse to talk to a
    backend that's been migrated past it) and whether features it
    relies on are enabled (e.g. money surfaces hide themselves when
    `features.money` is false).

Cheap by design: one AppSetting read, a Product count and the operational
config per probe, never an external service. The code-side schema head is
resolved at import; the DB's applied revision is cached once known.
"""
import logging
from pathlib import Path
from typing import Callable, TypeVar

from flask import jsonify

from dora_api.domain.stock_status import effective_expiring_soon_window
from dora_api.domain.entities.app_setting import (
    NUTRITION_MODE_OFF,
    RATING_SCHEME_NONE,
)
from dora_api.features.help.version_info import CURRENT_VERSION, build_id
from dora_api.features.routers import HEALTH_ROUTER
from dora_api.infrastructure.profile import current_profile

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


def _safe(block: str, build: Callable[[], _T], fallback: _T) -> _T:
    """Run one probe block. The probe must never fail, but a failure must not be
    silent either: it logs and reports that block's conservative defaults."""
    try:
        return build()
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("health: %s block failed, reporting defaults: %s", block, exc)
        return fallback


def _resolve_schema_head() -> str | None:
    """Read the alembic head revision from the migrations directory.
    Module-load only — schema versions don't change at runtime, and
    we don't want every health probe to hit alembic."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config()
        cfg.set_main_option(
            "script_location",
            str(Path(__file__).resolve().parents[2] / "persistence" / "migrations"),
        )
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception:
        # Best-effort: if alembic can't introspect (broken metadata,
        # missing script), prefer to keep the health endpoint up and
        # report null rather than failing the probe entirely.
        return None


_SCHEMA_HEAD = _resolve_schema_head()


def _resolve_db_schema_version() -> str | None:
    """Read the applied alembic revision from the *connected DB's*
    `alembic_version` table (FU-570). Returns None when the table is absent
    — e.g. a `create_all`-built dev DB that was never migration-stamped, or
    an unreadable DB. Reported alongside `schema_version` (the code-side
    head) so a diagnoser can tell code-expectation from DB-reality: a null
    here against a non-null `schema_version` means the DB isn't
    migration-managed, and a *different* value means it's behind/ahead. The
    old response reported only the code head, which actively misled when the
    connected DB was stale."""
    global _DB_SCHEMA_VERSION
    if _DB_SCHEMA_VERSION is not None:
        # Only a deploy changes it, and a deploy restarts the process.
        return _DB_SCHEMA_VERSION
    try:
        from sqlalchemy import text

        from dora_api.app import db
        with db.engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
            _DB_SCHEMA_VERSION = row[0] if row else None
            return _DB_SCHEMA_VERSION
    except Exception:
        # No alembic_version table, or a DB hiccup — keep the probe up and
        # report null rather than failing the health check.
        return None


_DB_SCHEMA_VERSION: str | None = None


def _feature_flags(setting) -> dict[str, bool]:
    """Surface what the backend can do, for client capability gating.
    Reads runtime state cheaply — DB-backed flags pull from the
    AppSettings singleton; env-driven flags read the env var directly.

    Key contract: keys never *removed*. New install-wide flags get
    added here whenever C-cross §2.6 grows its admin panel. Per ADR-002,
    every consumer reads the truth through this endpoint, not direct
    AppSetting access on the client.

    FU-388 — the AppSetting singleton is fetched once by ``health_check``
    and passed in (was re-fetched independently here + in the locale/image
    helpers, 3 SELECTs of the same one row per probe). ``setting`` is None
    only if that fetch failed, in which case the DB-backed flags keep their
    conservative defaults.
    """
    flags: dict[str, bool] = {
        "auth": True,           # always — session cookies + login flow
        "audit": True,          # always — audit_log + audit panel
        "scanning": False,      # resolved below — off by default
        # 2026-08-20 — install-wide stocktake master switch. Default TRUE:
        # the feature ships on, and an install has to switch it off. If the
        # AppSetting fetch failed we'd rather show the surface than silently
        # hide a feature the household uses.
        "stocktake": True,
        # `buy_verdict` was here until 2026-08-19 (D-12). It is a per-user
        # display preference now, on `/auth/me` — an install-wide flag would be
        # answering a personal question with a household answer.
        "multi_user": True,     # register + admin role
        # the install-wide `email` switch, and the two
        # `*_configured` R-014 signals (used by the SPA to reveal-and-disable
        # per-user channel toggles), now read through the operational-config
        # resolver so admin edits in Settings take effect without a restart.
        # Set conservatively here; resolved in the try block below alongside
        # the other AppSetting-driven flags.
        "email": False,
        "email_smtp_configured": False,
        "push_vapid_configured": False,
        # True iff `AppSetting.public_url` is set. Scheduled mail (the weekly
        # deals email) has no request to take an Origin from, so without it
        # every link would point at localhost and the job skips the send.
        # `email_smtp_configured and not public_url_configured` is the
        # "SMTP configured but public URL not set" warning for the admin
        # Email page. Resolved below.
        "public_url_configured": False,
        # NB: there is deliberately no `assistant` flag — AI mode has no
        # install-wide gate (it's a per-user opt-in), so the server has no
        # availability fact to publish. The old flag (formerly
        # `master_llm_enabled`) was dropped with the master switch.
        # True iff DORA_SECRET_ENCRYPTION_KEY is set + parses. Every client
        # reads it (not admin-only): the per-user Assistant page and the
        # admin Email/Push pages show a warning banner when it's unset, since
        # secrets (LLM API keys, SMTP password, VAPID key) can't be stored
        # encrypted without it. Resolved below.
        "secret_encryption_configured": False,
        # C-cross Chunk 1 — install-wide feature flags (proposal §2.6).
        # Each pairs with a per-user opt-in (where one exists) — install
        # off ⇒ feature hidden for everyone; install on ⇒ per-user opt-in
        # still applies. Resolved below from AppSetting.
        # `meal_planning` removed 2026-09-03 — meal planning is core and had
        # no real off switch; see migration a7c3e5d19f2b.
        "money": False,
        "nutrition": False,
        "deals_email": False,
        # Products is a data-presence overlay (PROPOSAL_PRODUCTS_AS_OVERLAY /
        # true iff product data has been ingested — not an admin/user
        # flag. Conservative default false; derived from Product rows below.
        "products": False,
        # Nutrition depth, install-wide. `nutrition` above stays the plain
        # "on at all" gate; `nutrition_mode` carries the depth; and
        # `nutrition_complex_usable` is derived from sources that are actually
        # installed (see features/nutrition/sources.py) — never from a config
        # string, which is what the retired `nutrition_complex_available` did.
        "nutrition_mode": NUTRITION_MODE_OFF,
        "nutrition_complex_usable": False,
    }
    # AppSettings drives every install-wide flag at runtime.
    def _resolve() -> dict[str, bool]:
        from dora_api.persistence.sqlalchemy_repository import \
            SqlAlchemyRepository
        repo = SqlAlchemyRepository()
        if setting is not None:
            flags["scanning"] = bool(setting.scanning_enabled)
            flags["stocktake"] = bool(setting.stocktake_enabled)
            # `buy_verdict` is no longer a health flag — it went per-user on
            # 2026-08-19 (D-12), so the SPA reads it off /auth/me with the rest
            # of the user's display preferences. An install-wide flag here would
            # have been answering for the wrong scope.
            # Owner ask 2026-08-27 — which front-of-pack rating recipes carry.
            # `none` everywhere by default; Settings' "Match this device"
            # offers the locally-recognised scheme, and the picker takes any of
            # them anywhere.
            #
            # Published as the scheme string rather than a bool because the
            # client has to render a different badge per scheme, not just
            # decide whether to render one (R-003 — the SPA must not re-derive
            # "which scheme" from anything else).
            flags["nutrition_rating_scheme"] = setting.nutrition_rating_scheme or RATING_SCHEME_NONE
            flags["money"] = bool(setting.money_enabled)
            # Nutrition is install-wide now (2026-08-14). `nutrition` keeps its
            # boolean meaning for the many gates that only ask "is it on at
            # all"; `nutrition_mode` carries the depth for the surfaces that
            # differ between simple and complex. `nutrition_complex_usable` is
            # derived from real installed sources, never from a config string.
            from dora_api.features.nutrition.sources import (
                complex_is_usable, nutrition_mode,
            )
            _Mode = nutrition_mode(setting)
            flags["nutrition"] = _Mode != NUTRITION_MODE_OFF
            flags["nutrition_mode"] = _Mode
            flags["nutrition_complex_usable"] = complex_is_usable(repo, setting)
        # products is on iff product data exists (data-presence gate),
        # not an AppSetting flag. R-003: one server-derived fact via /health.
        from dora_api.domain.entities.product import Product
        flags["products"] = repo.get(Product).count() > 0
        # email + push signals derive from the
        # operational-config resolver. Bucket-C secrets (SMTP password,
        # VAPID private key) live encrypted-at-rest on the AppSetting row;
        # the resolver decrypts on read, so a truthy value here means the
        # secret is both stored and decodable.
        from dora_api.features.app_settings.operational_config import \
            resolved_operational_config
        op_config = resolved_operational_config()
        flags["email"] = bool(op_config.email_enabled)
        flags["email_smtp_configured"] = bool(op_config.smtp_username)
        flags["public_url_configured"] = bool((op_config.public_url or "").strip())
        flags["push_vapid_configured"] = bool(
            op_config.vapid_public_key and op_config.vapid_private_key
        )
        # env-driven (not DB-backed) — reads the wrapping key straight from
        # the environment. Drives the "set DORA_SECRET_ENCRYPTION_KEY" banner
        # on the settings pages that store secrets.
        from dora_api.infrastructure.security.secret_encryption import \
            encryption_available
        flags["secret_encryption_configured"] = bool(encryption_available())
        return flags

    # A failure part-way keeps whatever resolved before it, as before.
    return _safe("features", _resolve, flags)


def _locale_policy(setting) -> dict[str, str]:
    """FU-043 (PROPOSAL_LOCALE_I18N Layer A) — install-wide currency + display
    locale, surfaced here (not on `/app-settings`) because every logged-in
    user's browser needs to render money in the household's chosen currency
    on boot, not just admins. Client wraps these in one
    `Intl.NumberFormat(locale, {style:'currency', currency})` and every
    money render routes through it (R-003). Falls back to Dora's AU shipping
    defaults.

    The measurement system rides along for the same reason (owner 2026-08-27):
    *every* user's unit dropdowns are built from it. The client filters its
    picker vocabulary by this and never re-derives which units belong to which
    system (R-003 — the mapping is `units.UNIT_SYSTEMS`, mirrored into the
    generated `units_table.ts`).

    `timezone` (the household's IANA zone, resolved exactly as
    `clock.household_timezone` resolves it, so an invalid stored value reads
    "UTC" here too) lets the client name "Today" / "Tomorrow" on the
    household's calendar rather than the device's (R-021). Additive."""
    fallback = {
        "currency": "AUD", "locale": "en-AU", "measurement_system": "metric",
        "timezone": "UTC",
    }
    if setting is None:
        return fallback
    from dora_api.features.app_settings.clock import resolve_timezone
    return _safe("locale_policy", lambda: {
        "currency": (setting.currency or "").strip() or fallback["currency"],
        "locale": (setting.locale or "").strip() or fallback["locale"],
        "measurement_system": (setting.measurement_system or "").strip() or fallback["measurement_system"],
        "timezone": resolve_timezone(setting.timezone).key,
    }, fallback)


def _image_policy(setting) -> dict[str, int]:
    """FU-345 — install-wide image compression knobs. Read on boot by
    the client-side `processImageFile` helper so every upload site
    (stock items, recipes, products, avatars, receipts, store logos)
    lands compressed to the admin's chosen quality + max dimension.
    Surfaced here (not on `/app-settings`) because it's a public
    policy every logged-in user's browser needs to apply, not admin-
    only configuration; the admin edit path is still the same
    admin-gated PATCH /app-settings."""
    fallback = {"quality": 85, "max_dimension": 1920}
    if setting is None:
        return fallback
    return _safe("image_policy", lambda: {
        "quality": int(setting.image_quality or fallback["quality"]),
        "max_dimension": int(setting.image_max_dimension or fallback["max_dimension"]),
    }, fallback)


def _cooking_policy(setting) -> dict:
    """FU-615 — install-wide household cooking config, surfaced here (not on
    `/app-settings`) because every logged-in user's client needs it, not just
    admins: cook mode seeds its per-session serving scaler from
    `household_headcount`, and the meal-planner reveals the cook-pool
    affordances when `batch_features_enabled` is on. Both moved off User to
    AppSetting (a household has one headcount + one cook-style). Unset
    defaults: no headcount ⇒ recipe servings; fresh cook-style."""
    fallback = {"household_headcount": None, "batch_features_enabled": False}
    if setting is None:
        return fallback
    return _safe("cooking_policy", lambda: {
        "household_headcount": (
            int(setting.household_headcount) if setting.household_headcount is not None else None
        ),
        "batch_features_enabled": bool(setting.batch_features_enabled),
    }, fallback)


def _budget_policy(setting) -> dict:
    """Install-wide household grocery budget, surfaced here (not on
    `/app-settings`) because every logged-in user's client reads it — the
    dashboard budget card + Settings → Money page — not just admins. Moved off
    User (spend is summed across shared shopping lists, so the target is shared
    too). `amount` None ⇒ no budget set (value-driven: no amount = off)."""
    fallback = {"amount": None, "period": "weekly"}
    if setting is None:
        return fallback
    raw = setting.budget_amount
    return _safe("budget_policy", lambda: {
        "amount": float(raw) if raw is not None and raw > 0 else None,
        "period": setting.budget_period or fallback["period"],
    }, fallback)


def _reconcile_policy(setting) -> dict:
    """Install-wide meal-reconcile posture, surfaced here (not on `/app-settings`,
    which is admin-gated) because every logged-in user's client needs it to pick
    the right `/meal-plans/reconcile` surface: **auto** ⇒ a read-only log of what
    Dora did; **manual** ⇒ the confirm-each runner (owner 2026-08-13). `auto_drain`
    defaults True (matches the sweep + AppSetting)."""
    if setting is None:
        return {"auto_drain": True}
    return {"auto_drain": bool(setting.auto_drain_past_meals)}


def _alerts_policy(setting) -> dict:
    """The household's expiring-soon window, for every client (`/app-settings`
    is admin-gated): Dora's Basic mode names "expiring soon" with the same
    window the alerts use (finalisation 11-R34; it hard-coded 7 days)."""
    return {"expiring_soon_window_days": effective_expiring_soon_window(setting)}


def _stocktake_policy(setting) -> dict:
    """Install-wide stocktake defaults, surfaced here (not on `/app-settings`,
    which is admin-gated) because every logged-in user's client needs one of
    them: the create-stock-item dialog seeds its Stocktake toggle from
    `new_items_opt_in` so the switch shows the position the item will actually
    be created in. Defaults True (matches `create_stock_item` + AppSetting)."""
    if setting is None:
        return {"new_items_opt_in": True}
    return {"new_items_opt_in": bool(setting.stocktake_new_items_opt_in)}


def _products_policy(setting) -> dict:
    """The admin-set Product Search (companion) URL, surfaced here (not on
    `/app-settings`, which is admin-gated) because every user's nav and the
    find-a-product buttons open it. Empty string ⇒ not set up."""
    if setting is None:
        return {"search_url": ""}
    return {"search_url": (setting.product_search_url or "").strip()}


def _support_channel() -> dict[str, str]:
    """FU-370 — install's support/report-an-issue channel, surfaced here (not
    on `/app-settings`) because every logged-in user's browser needs it to
    decide whether to render the "Report an issue" affordance, not just admins.
    Unlike the other blocks this is *not* DB-backed: it's a hardcoded
    commit-and-done switch (with env override) — see
    `features/support/support_channel.py`. Empty strings ⇒ dormant, no button."""
    from dora_api.features.support.support_channel import resolve_support_channel
    return resolve_support_channel()


@HEALTH_ROUTER.route("")
def health_check():
    """Single endpoint for both monitoring and client compatibility.
    Mobile/desktop clients can rely on the response shape never
    losing keys — we add, but don't remove."""
    _LOGGER.debug("API health check requested.")
    # FU-388 — fetch the AppSetting singleton ONCE and thread it through the
    # three DB-backed blocks below. They used to each call
    # get_or_create_app_setting independently → 3 SELECTs of the same one row
    # per probe (and /health is polled by every client). None on DB error, so
    # each block falls back to its conservative defaults exactly as before.
    from dora_api.features.app_settings.access import get_or_create_app_setting
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
    setting = _safe("app_settings", lambda: get_or_create_app_setting(SqlAlchemyRepository()), None)
    return jsonify({
        "ok": True,
        "version": CURRENT_VERSION,
        # FU-861 — which build of that version; None from a source checkout.
        "build": build_id(),
        "schema_version": _SCHEMA_HEAD,
        # FU-570 — the DB's actual applied revision (None if the DB was
        # built via create_all and never stamped, or on a read error). Lets
        # diagnosis distinguish code-expectation from DB-reality.
        "schema_version_db": _resolve_db_schema_version(),
        "profile": current_profile().value,
        "features": _feature_flags(setting),
        "image_policy": _image_policy(setting),
        "locale_policy": _locale_policy(setting),
        "cooking_policy": _cooking_policy(setting),
        "budget_policy": _budget_policy(setting),
        "reconcile_policy": _reconcile_policy(setting),
        "stocktake_policy": _stocktake_policy(setting),
        "alerts_policy": _alerts_policy(setting),
        "products_policy": _products_policy(setting),
        "support": _support_channel(),
    }), 200
