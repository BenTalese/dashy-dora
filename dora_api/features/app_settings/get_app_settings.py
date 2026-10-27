"""GET /api/app-settings — install-wide settings for the admin Settings UI.

Admin-only. The assistant reads these values server-side (see access.py); this
endpoint exists so the admin page can show and edit them.
"""
import logging
from dataclasses import dataclass

from dora_api.domain.entities.app_setting import (
    NUTRITION_MODE_OFF,
    RATING_SCHEME_NONE,
)
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.routers import APP_SETTINGS_ROUTER
from dora_api.features.auth.admin_gate import require_admin
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AppSettingsDto:
    scanning_enabled: bool
    nutrition_rating_scheme: str
    # buy-verdict oracle toggle.
    # C-cross Chunk 1 — install-wide feature flags (proposal §2.6).
    money_enabled: bool
    # Nutrition, install-wide: `off` | `simple` | `complex`, plus complex-mode
    # source config. Replaced `nutrition_enabled` + the per-user mode + the
    # dead `nutrition_db_source` seam (2026-08-14).
    nutrition_mode: str
    nutrition_usda_api_key: str
    nutrition_off_lookup_enabled: bool
    # Meal Plans C-2.K — household IANA timezone for the "today" boundary.
    timezone: str
    # Alerts C-9.2 — household-wide expiring-soon window (PROPOSAL_ALERTS §3.3).
    expiring_soon_window_days: int
    # Phase D / FU-186 — admin-set URL the Product Search nav opens.
    product_search_url: str
    # Which units the install measures in: "metric" | "imperial" | "us".
    # Drives both the unit pickers and the per-unit price denominator.
    measurement_system: str
    # install-wide currency (ISO 4217) + display locale (BCP-47).
    # Layer A of PROPOSAL_LOCALE_I18N; also mirrored on /api/health so
    # every client session (not just admin) reads them.
    currency: str
    locale: str
    # backup library controls. See AppSetting entity.
    backup_retention_count: int
    backup_storage_path: str
    # image compression knobs. See AppSetting entity.
    image_quality: int
    image_max_dimension: int
    # PROPOSAL_STOCKTAKE_MODE §4 + §8 — global cadence band + Auto toggle.
    stocktake_default_cadence_band: str
    stocktake_auto_tuning_enabled: bool
    # 2026-08-20 — install-wide stocktake master switch + the opt-in default
    # handed to new items.
    stocktake_enabled: bool
    stocktake_new_items_opt_in: bool
    # FU-511 — install-wide auto-add mode. 'off' | 'essential_only' | 'all'.
    auto_add_mode: str
    # FU-615 — household cooking config, install-wide (moved off User).
    # `household_headcount` None = not set (cook mode uses recipe servings).
    # `batch_features_enabled` = cook-style ("batch" reveals the cook pool).
    # Also mirrored on /api/health.cooking_policy so every client reads them.
    household_headcount: int | None
    batch_features_enabled: bool
    # FU-317 — install-wide meal-plan reconcile posture (D5 install-wide,
    # FU-517). True keeps today's silent auto-drain; False flips the daily
    # sweep to write `unresolved_manual` receipts and leave the pool +
    # entries untouched (see reconcile_consumed_meals.py).
    auto_drain_past_meals: bool
    # operational config (was `DORA_*` env vars).
    # Bucket-C secrets (SMTP password, VAPID private key) are stored
    # encrypted-at-rest on the row; the DTO exposes a `<field>_configured`
    # bool instead of the ciphertext so the admin UI can show Set / Change
    # / Clear without ever transporting the secret.
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password_configured: bool
    smtp_from: str
    smtp_use_tls: bool
    vapid_public_key: str
    vapid_private_key_configured: bool
    vapid_subject: str
    piper_bin: str
    piper_bundled_voice_dir: str
    email_enabled: bool
    audit_retention_days: int
    public_url: str


def _to_dto(setting) -> AppSettingsDto:  # noqa: ANN001 — duck-typed AppSetting
    return AppSettingsDto(
        scanning_enabled=bool(setting.scanning_enabled),
        nutrition_rating_scheme=str(
            setting.nutrition_rating_scheme
            or RATING_SCHEME_NONE),
        money_enabled=bool(setting.money_enabled),
        nutrition_mode=setting.nutrition_mode or NUTRITION_MODE_OFF,
        nutrition_usda_api_key=setting.nutrition_usda_api_key or "",
        nutrition_off_lookup_enabled=bool(setting.nutrition_off_lookup_enabled),
        timezone=setting.timezone or "UTC",
        expiring_soon_window_days=int(setting.expiring_soon_window_days),
        product_search_url=setting.product_search_url or "",
        measurement_system=setting.measurement_system or "metric",
        currency=setting.currency or "AUD",
        locale=setting.locale or "en-AU",
        backup_retention_count=int(setting.backup_retention_count or 5),
        backup_storage_path=setting.backup_storage_path or "",
        image_quality=int(setting.image_quality or 85),
        image_max_dimension=int(setting.image_max_dimension or 1920),
        stocktake_default_cadence_band=(
            setting.stocktake_default_cadence_band or "fortnightly"
        ),
        stocktake_auto_tuning_enabled=bool(
            setting.stocktake_auto_tuning_enabled
        ),
        stocktake_enabled=bool(setting.stocktake_enabled),
        stocktake_new_items_opt_in=bool(
            setting.stocktake_new_items_opt_in
        ),
        auto_add_mode=(setting.auto_add_mode or "essential_only"),
        household_headcount=(
            int(setting.household_headcount)
            if setting.household_headcount is not None else None
        ),
        batch_features_enabled=bool(setting.batch_features_enabled),
        auto_drain_past_meals=bool(setting.auto_drain_past_meals),
        smtp_host=setting.smtp_host or "",
        smtp_port=int(setting.smtp_port or 587),
        smtp_username=setting.smtp_username or "",
        smtp_password_configured=bool((setting.smtp_password_encrypted or "").strip()),
        smtp_from=setting.smtp_from or "",
        smtp_use_tls=bool(setting.smtp_use_tls),
        vapid_public_key=setting.vapid_public_key or "",
        vapid_private_key_configured=bool((setting.vapid_private_key_encrypted or "").strip()),
        vapid_subject=setting.vapid_subject or "mailto:admin@dora.local",
        piper_bin=setting.piper_bin or "",
        piper_bundled_voice_dir=setting.piper_bundled_voice_dir or "",
        email_enabled=bool(setting.email_enabled),
        audit_retention_days=int(setting.audit_retention_days or 365),
        public_url=setting.public_url or "",
    )


@APP_SETTINGS_ROUTER.route("", methods=["GET"])
def get_app_settings():
    _, err = require_admin()
    if err is not None:
        return err
    setting = get_or_create_app_setting(SqlAlchemyRepository())
    _LOGGER.debug("Served app settings (scanning_enabled=%s)", setting.scanning_enabled)
    return ok(_to_dto(setting))
