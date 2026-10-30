"""PATCH /api/app-settings — admin-only edit of install-wide settings.

Every install-wide switch the admin pages edit: region and money, alerts and
stock rules, email and push, image, voice and ingestion settings. Fields are
optional; only those present in the request body are changed, and each is
validated before any is written.
"""
import logging
import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.app_setting import (
    NUTRITION_MODE_VALUES,
    RATING_SCHEME_VALUES,
)
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.app_settings.clock import is_valid_timezone
from dora_api.features.app_settings.get_app_settings import AppSettingsDto, _to_dto
from dora_api.features.routers import APP_SETTINGS_ROUTER
from dora_api.features.auth.admin_gate import require_admin
from dora_api.infrastructure.api_response import bad_request, ok
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


class UpdateAppSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanning_enabled: bool | None = None
    registration_enabled: bool | None = None
    # Closed set; validated in the handler against RATING_SCHEME_VALUES so the
    # rejection message can name the options (R-010 carve-out, as per
    # nutrition_mode).
    nutrition_rating_scheme: str | None = None
    # `buy_verdict_enabled` left this request on 2026-08-19 (D-12) — it is a
    # per-user display preference now, patched via PATCH /auth/me. `extra=forbid`
    # means an old client still sending it here gets a 4xx rather than a silent
    # no-op, which is the honest failure.
    # C-cross Chunk 1 — install-wide feature flags (proposal §2.6).
    money_enabled: bool | None = None
    # Nutrition, install-wide. `nutrition_mode` is validated against
    # NUTRITION_MODE_VALUES below (R-010 carve-out — one boundary point).
    nutrition_mode: str | None = Field(default=None, max_length=10)
    nutrition_usda_api_key: str | None = Field(default=None, max_length=255)
    nutrition_off_lookup_enabled: bool | None = None
    # Meal Plans C-2.K — household IANA timezone (validated below).
    timezone: str | None = Field(default=None, max_length=64)
    # Alerts C-9.2 — household-wide expiring-soon window (bounds double as
    # R-010 validation: 1–365 days). The old
    # `default_days_until_stocktake_alert` field was retired in the
    # 2026-07-04 stocktake cleanup — the band system (below) owns cadence.
    expiring_soon_window_days: int | None = Field(default=None, ge=1, le=365)
    # Phase D / FU-186 — admin-set URL the Product Search nav opens.
    # Empty string ⇒ unset; the nav entry renders disabled with a hint.
    # We allow any http(s) URL or empty; deeper validation is the operator's
    # problem (the field never echoes back as a clickable link to other
    # users — it ALWAYS opens via target="_blank" rel="noopener").
    product_search_url: str | None = Field(default=None, max_length=500)
    # AU vs US per-unit display locale.
    measurement_system: str | None = Field(default=None, max_length=16)
    # install-wide currency (ISO 4217; 3 uppercase letters) and
    # display locale (BCP-47 tag; validated in the handler against Python's
    # Babel-style parse rather than a regex, since BCP-47 has more shapes
    # than a single pattern captures cleanly).
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    locale: str | None = Field(default=None, min_length=2, max_length=35)
    # backup library controls. Retention 1–100; storage_path
    # blank ⇒ default `<data-dir>/backups`. Non-blank path is validated
    # for writeability on save.
    backup_retention_count: int | None = Field(default=None, ge=1, le=100)
    backup_storage_path: str | None = Field(default=None, max_length=1024)
    # image compression knobs. Quality 30–100; max dimension
    # 512–8192 (below 512 → images legibly small; above 8192 → cap is
    # bigger than any realistic camera output and the byte cap on the
    # request schema kicks in first).
    image_quality: int | None = Field(default=None, ge=30, le=100)
    image_max_dimension: int | None = Field(default=None, ge=512, le=8192)
    # PROPOSAL_STOCKTAKE_MODE §4 + §8 — the two stocktake knobs.
    # Cadence band is one of {'weekly','fortnightly','monthly'}; the
    # handler validates against the enum below so a typo can't silently
    # degrade the queue.
    stocktake_default_cadence_band: str | None = Field(default=None, max_length=16)
    stocktake_auto_tuning_enabled: bool | None = None
    # 2026-08-20 — install-wide master switch + the opt-in default new items
    # are born with. Plain bools; no validation beyond pydantic.
    stocktake_enabled: bool | None = None
    stocktake_new_items_opt_in: bool | None = None
    # FU-511 — install-wide auto-add mode. Validated against
    # `_VALID_AUTO_ADD_MODES` in the handler so a typo can't silently
    # degrade behaviour to the seeded default.
    auto_add_mode: str | None = Field(default=None, max_length=16)
    # FU-615 — household cooking config (install-wide, moved off User).
    # `household_headcount`: 1–99, or null to clear back to "use each
    # recipe's servings". `batch_features_enabled`: plain cook-style bool.
    # Present-in-body semantics: headcount is set (incl. explicit null)
    # whenever the field is in the body; omit to leave unchanged.
    household_headcount: int | None = Field(default=None, ge=1, le=99)
    batch_features_enabled: bool | None = None
    # FU-317 — install-wide meal-plan reconcile posture. Plain bool;
    # the sweep reads it and picks a branch (see reconcile_consumed_meals).
    auto_drain_past_meals: bool | None = None
    # operational config previously carried as
    # `DORA_*` env vars. Bucket-C secrets (SMTP password, VAPID private
    # key) accept plaintext on the wire and are Fernet-encrypted before
    # they touch the DB; the response DTO returns only a `_configured`
    # bool. Empty string is the explicit "clear this secret" signal —
    # `None` (field omitted) leaves the stored value alone.
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = Field(default=None, max_length=512)
    smtp_from: str | None = Field(default=None, max_length=255)
    smtp_use_tls: bool | None = None
    vapid_public_key: str | None = Field(default=None, max_length=255)
    vapid_private_key: str | None = Field(default=None, max_length=4096)
    vapid_subject: str | None = Field(default=None, max_length=255)
    piper_bin: str | None = Field(default=None, max_length=1024)
    piper_bundled_voice_dir: str | None = Field(default=None, max_length=1024)
    email_enabled: bool | None = None
    # Retention bounds: 1 day floor (anything less is effectively "no
    # audit"), ~10-year ceiling on a small install DB.
    audit_retention_days: int | None = Field(default=None, ge=1, le=3650)
    public_url: str | None = Field(default=None, max_length=500)


@dataclass(slots=True)
class UpdateAppSettingsResponse:
    invalid_reason: str | None = None
    dto: AppSettingsDto | None = None


class UpdateAppSettingsHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateAppSettingsRequest) -> UpdateAppSettingsResponse:
        setting = get_or_create_app_setting(self.repository)
        set_fields = request.model_fields_set

        if "scanning_enabled" in set_fields and request.scanning_enabled is not None:
            setting.scanning_enabled = request.scanning_enabled
        if "registration_enabled" in set_fields and request.registration_enabled is not None:
            setting.registration_enabled = request.registration_enabled
        if ("nutrition_rating_scheme" in set_fields
                and request.nutrition_rating_scheme is not None):
            _Scheme = request.nutrition_rating_scheme.strip().lower()
            if _Scheme not in RATING_SCHEME_VALUES:
                return UpdateAppSettingsResponse(
                    invalid_reason=(
                        f"'{request.nutrition_rating_scheme}' is not a nutrition "
                        f"rating scheme. Supported: {sorted(RATING_SCHEME_VALUES)}."
                    ),
                )
            setting.nutrition_rating_scheme = _Scheme
        # C-cross Chunk 1 — install feature flags. Partial-update semantics
        # like every other field above: only fields present in the body
        # change; the rest are left alone.
        for _Attr in (
            "money_enabled",
            "nutrition_off_lookup_enabled",
        ):
            if _Attr in set_fields:
                value = getattr(request, _Attr)
                if value is not None:
                    setattr(setting, _Attr, value)

        # Nutrition depth. R-010 carve-out: the one place the closed set is
        # checked. Deliberately NOT gated on a source being available —
        # `complex` with nothing installed yet is a legitimate intermediate
        # state (you pick the mode, then the page offers you the download),
        # and the lookup/rollup degrade honestly when no source answers.
        if "nutrition_mode" in set_fields and request.nutrition_mode is not None:
            _Mode = request.nutrition_mode.strip()
            if _Mode not in NUTRITION_MODE_VALUES:
                # Was `return None, "..."` — a bare tuple the route then read
                # `.invalid_reason` off, so an invalid mode was a 500 instead
                # of the 400 every other field gets (finalisation 13-R1).
                return UpdateAppSettingsResponse(
                    invalid_reason=f"Invalid nutrition mode '{_Mode}'.",
                )
            setting.nutrition_mode = _Mode
        if "nutrition_usda_api_key" in set_fields:
            setting.nutrition_usda_api_key = (request.nutrition_usda_api_key or "").strip()

        # Meal Plans C-2.K — household timezone. Validate against the IANA
        # database so an unparseable zone can't silently degrade the "today"
        # boundary to UTC for the whole install.
        if "timezone" in set_fields and request.timezone is not None:
            _Tz = request.timezone.strip()
            if not is_valid_timezone(_Tz):
                return UpdateAppSettingsResponse(
                    invalid_reason=f"'{_Tz}' is not a recognised IANA timezone."
                )
            setting.timezone = _Tz

        # Alerts C-9.2 — household-wide alert thresholds. Bounds enforced by
        # the request model above (R-010).
        if "expiring_soon_window_days" in set_fields and request.expiring_soon_window_days is not None:
            setting.expiring_soon_window_days = request.expiring_soon_window_days

        # measurement_system. Validated against the supported set so a typo
        # can't silently empty every unit dropdown in the app.
        if "measurement_system" in set_fields and request.measurement_system is not None:
            from dora_api.domain.units import SUPPORTED_MEASUREMENT_SYSTEMS
            _System = request.measurement_system.strip().lower()
            if _System not in SUPPORTED_MEASUREMENT_SYSTEMS:
                return UpdateAppSettingsResponse(
                    invalid_reason=(
                        f"'{_System}' is not a supported measurement system. "
                        f"Supported: {sorted(SUPPORTED_MEASUREMENT_SYSTEMS)}."
                    ),
                )
            setting.measurement_system = _System

        # currency + locale. Currency is ISO 4217 (3 uppercase
        # letters, no digits — the validator here mirrors the client's
        # Intl.NumberFormat constraint). Locale is a BCP-47 tag validated
        # by asking Intl.Locale on the client and, server-side, by a
        # lightweight structural check (primary tag + optional subtags),
        # so a typo can't silently degrade every money render in the app.
        if "currency" in set_fields and request.currency is not None:
            _Code = request.currency.strip().upper()
            if len(_Code) != 3 or not _Code.isalpha():
                return UpdateAppSettingsResponse(
                    invalid_reason=(
                        f"'{request.currency}' is not a valid ISO 4217 currency "
                        f"code (must be 3 letters, e.g. 'USD', 'EUR', 'AUD')."
                    ),
                )
            setting.currency = _Code
        if "locale" in set_fields and request.locale is not None:
            _Tag = request.locale.strip()
            if not _is_valid_bcp47(_Tag):
                return UpdateAppSettingsResponse(
                    invalid_reason=(
                        f"'{request.locale}' is not a valid BCP-47 locale tag "
                        f"(e.g. 'en-AU', 'en-US', 'de-DE', 'fr-FR')."
                    ),
                )
            setting.locale = _Tag

        # Phase D / FU-186 — product_search_url. Strip; reject obviously
        # non-http schemes so a typo doesn't render a hostile link, but
        # otherwise leave validation to the operator.
        if "product_search_url" in set_fields:
            _Url = (request.product_search_url or "").strip()
            if _Url and not (_Url.startswith("http://") or _Url.startswith("https://")):
                return UpdateAppSettingsResponse(
                    invalid_reason="Product search URL must start with http:// or https://."
                )
            setting.product_search_url = _Url

        # backup library controls. Retention is a plain int
        # bounded by the request model; storage path is validated for
        # writeability (an admin pointing at a bad NAS mount finds out
        # here, not on the next backup attempt).
        if "backup_retention_count" in set_fields and request.backup_retention_count is not None:
            setting.backup_retention_count = request.backup_retention_count
        if "backup_storage_path" in set_fields:
            _Path = (request.backup_storage_path or "").strip()
            if _Path:
                invalid = _validate_backup_storage_path(_Path)
                if invalid is not None:
                    return UpdateAppSettingsResponse(invalid_reason=invalid)
            setting.backup_storage_path = _Path

        # image compression knobs. Bounds enforced by the
        # request model. Applies forward-only: existing images are not
        # re-encoded (out of scope; power users can log a follow-up if
        # they want a re-encode pass).
        if "image_quality" in set_fields and request.image_quality is not None:
            setting.image_quality = request.image_quality
        if "image_max_dimension" in set_fields and request.image_max_dimension is not None:
            setting.image_max_dimension = request.image_max_dimension

        # PROPOSAL_STOCKTAKE_MODE §4 + §8 — cadence band + Auto toggle.
        # Band is validated against the enum so a typo can't degrade
        # the queue to the fallback silently (R-010).
        if (
            "stocktake_default_cadence_band" in set_fields
            and request.stocktake_default_cadence_band is not None
        ):
            from dora_api.features.stocktake.cadence import CadenceBand
            _Band = request.stocktake_default_cadence_band.strip().lower()
            try:
                CadenceBand(_Band)
            except ValueError:
                return UpdateAppSettingsResponse(
                    invalid_reason=(
                        f"'{_Band}' is not a valid cadence band. "
                        f"Allowed: {[b.value for b in CadenceBand]}."
                    ),
                )
            setting.stocktake_default_cadence_band = _Band
        if (
            "stocktake_auto_tuning_enabled" in set_fields
            and request.stocktake_auto_tuning_enabled is not None
        ):
            setting.stocktake_auto_tuning_enabled = request.stocktake_auto_tuning_enabled
        if (
            "stocktake_enabled" in set_fields
            and request.stocktake_enabled is not None
        ):
            setting.stocktake_enabled = request.stocktake_enabled
        if (
            "stocktake_new_items_opt_in" in set_fields
            and request.stocktake_new_items_opt_in is not None
        ):
            setting.stocktake_new_items_opt_in = request.stocktake_new_items_opt_in

        # FU-317 — meal-plan reconcile posture. Plain bool; no validation
        # beyond pydantic. Flip takes effect on the next
        # `reconcile_consumed_meals` invocation (i.e. the next request to
        # a dashboard / meal-plan / recipe endpoint).
        if (
            "auto_drain_past_meals" in set_fields
            and request.auto_drain_past_meals is not None
        ):
            setting.auto_drain_past_meals = request.auto_drain_past_meals

        # FU-511 — auto-add mode. Enum-validated so a typo can't silently
        # degrade to the seeded default.
        if "auto_add_mode" in set_fields and request.auto_add_mode is not None:
            _Mode = request.auto_add_mode.strip().lower()
            if _Mode not in _VALID_AUTO_ADD_MODES:
                return UpdateAppSettingsResponse(
                    invalid_reason=(
                        f"'{_Mode}' is not a valid auto-add mode. "
                        f"Allowed: {sorted(_VALID_AUTO_ADD_MODES)}."
                    ),
                )
            setting.auto_add_mode = _Mode

        # FU-615 — household cooking config. Headcount uses present-in-body
        # semantics (an explicit null clears it back to "use recipe
        # servings"); the 1–99 bounds are enforced by the request model.
        # Batch cook-style is a plain bool.
        if "household_headcount" in set_fields:
            setting.household_headcount = request.household_headcount
        if "batch_features_enabled" in set_fields and request.batch_features_enabled is not None:
            setting.batch_features_enabled = request.batch_features_enabled

        # operational config. Strings strip on save; the
        # `public_url` scheme guard mirrors `product_search_url` above so a
        # typo can't produce a hostile link in outbound emails.
        if "public_url" in set_fields:
            _Url = (request.public_url or "").strip()
            if _Url and not (_Url.startswith("http://") or _Url.startswith("https://")):
                return UpdateAppSettingsResponse(
                    invalid_reason="Public URL must start with http:// or https://."
                )
            setting.public_url = _Url
        for _StrField in (
            "smtp_host", "smtp_username", "smtp_from",
            "vapid_public_key", "vapid_subject",
            "piper_bin", "piper_bundled_voice_dir",
        ):
            if _StrField in set_fields:
                _Value = getattr(request, _StrField)
                setattr(setting, _StrField, (_Value or "").strip())
        for _NumericOrBool in (
            "smtp_port", "smtp_use_tls",
            "email_enabled", "audit_retention_days",
        ):
            if _NumericOrBool in set_fields:
                _Value = getattr(request, _NumericOrBool)
                if _Value is not None:
                    setattr(setting, _NumericOrBool, _Value)

        # encrypt-and-store the two operational secrets.
        # Empty string is explicit "clear the stored value"; a non-empty
        # value replaces it. Encryption requires `DORA_SECRET_ENCRYPTION_KEY`;
        # if the wrapping key isn't configured we bail with a friendly
        # 400 rather than silently swallowing the write.
        for _SecretField, _ColumnField in (
            ("smtp_password", "smtp_password_encrypted"),
            ("vapid_private_key", "vapid_private_key_encrypted"),
        ):
            if _SecretField not in set_fields:
                continue
            _Plain = getattr(request, _SecretField)
            if _Plain is None or _Plain == "":
                setattr(setting, _ColumnField, "")
                continue
            from dora_api.infrastructure.security.secret_encryption import (
                EncryptionUnavailable,
                encrypt,
            )
            try:
                token = encrypt(_Plain)
            except EncryptionUnavailable:
                return UpdateAppSettingsResponse(
                    invalid_reason=(
                        f"Cannot save {_SecretField}: DORA_SECRET_ENCRYPTION_KEY "
                        f"isn't configured for this install. Configure the "
                        f"wrapping key before storing secrets in the database."
                    ),
                )
            setattr(setting, _ColumnField, token.decode("ascii"))

        self.repository.save_changes()
        return UpdateAppSettingsResponse(dto=_to_dto(setting))


_VALID_AUTO_ADD_MODES = frozenset({"off", "essential_only", "all"})

_BCP47_SUBTAG = re.compile(r"^[A-Za-z0-9]{1,8}$")


def _is_valid_bcp47(tag: str) -> bool:
    """FU-043 — lightweight BCP-47 tag check. Accepts the shapes that
    `Intl.NumberFormat` / `Intl.Locale` actually consume: a 2-3 letter
    primary language tag, optionally followed by hyphen-separated
    script/region/variant subtags of alphanumeric characters. Rejects
    empty, malformed, and obviously-wrong inputs. We don't try to
    reproduce full RFC 5646 grammar server-side — the client's own
    `new Intl.Locale(tag)` will catch anything exotic that slips
    through, and the admin sees the reason there. Belt-and-braces."""
    if not tag or " " in tag:
        return False
    parts = tag.split("-")
    if not parts[0] or not parts[0].isalpha() or not (2 <= len(parts[0]) <= 3):
        return False
    return all(_BCP47_SUBTAG.match(p) for p in parts[1:])


def _validate_backup_storage_path(path_str: str) -> str | None:
    """FU-342 — accept only absolute paths that we can actually write to.
    Returns None on success, a user-facing reason on failure. Skips any
    creation on the AppSetting save; the create endpoint's mkdir handles
    directory materialisation, so we only assert the operator's chosen
    location is reachable."""
    import os
    from pathlib import Path
    try:
        candidate = Path(path_str).expanduser().resolve()
    except (OSError, ValueError):
        return f"'{path_str}' is not a valid filesystem path."
    if not candidate.is_absolute():
        return "Backup storage path must be absolute."
    # If the directory already exists, it must be a directory + writeable.
    if candidate.exists():
        if not candidate.is_dir():
            return f"'{candidate}' exists but is not a directory."
        if not os.access(candidate, os.W_OK):
            return f"'{candidate}' is not writeable by the server process."
        return None
    # Doesn't exist — check the nearest existing parent is writeable so
    # the create-endpoint mkdir will succeed.
    parent = candidate.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    if not parent.exists():
        return f"No part of '{candidate}' exists. Check the path."
    if not os.access(parent, os.W_OK):
        return f"Cannot create '{candidate}': '{parent}' is not writeable."
    return None


@APP_SETTINGS_ROUTER.route("", methods=["PATCH"])
@has_request_body(UpdateAppSettingsRequest)
def update_app_settings():
    _, err = require_admin()
    if err is not None:
        return err
    _Request: UpdateAppSettingsRequest = get_request_body()
    _Response = UpdateAppSettingsHandler(SqlAlchemyRepository()).handle(_Request)
    if _Response.invalid_reason is not None:
        return bad_request("Invalid settings.", detail=_Response.invalid_reason)
    _LOGGER.info("Admin updated app settings (scanning_enabled=%s)", _Response.dto.scanning_enabled)
    return ok(_Response.dto)
