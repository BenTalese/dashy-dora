import logging
from uuid import UUID

from flask import session
from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.user import (ALERT_DISCARD_DAY_OPTIONS,
                                           ALLOWED_FONT_FAMILIES,
                                           ALLOWED_FONT_SIZES,
                                           ALLOWED_LLM_PROVIDERS,
                                           ALLOWED_THEMES,
                                           ALLOWED_VOICE_ENGINES, User)
from dora_api.features.assistant.providers import get_provider_config
from dora_api.features.tts.voice_catalog import VOICE_IDS
from dora_api.features.auth.register_user import (AuthenticatedUserDto,
                                                  SESSION_USER_ID_KEY)
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import (business_rule_violation, ok,
                                                  unauthorized)
from dora_api.infrastructure.auth_helpers import is_valid_email, normalise_email
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.data_url import image_field

_LOGGER = logging.getLogger(__name__)


class UpdateMeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Day of the week (0 = Mon … 6 = Sun) the weekly deals email should be sent.
    send_deals_on_day: int | None = Field(default=None, ge=0, le=6)
    # Direct email edit. The old verified change-email flow (password proof +
    # confirmation link + old-address notice) was retired as overengineered
    # for this app — the owner edits their address inline and it's trusted.
    # Empty string clears the address; a non-empty value is validated +
    # deduped in the handler. Omit the field to leave it untouched.
    email: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=255)
    deals_email_enabled: bool | None = None
    deals_email_compact: bool | None = None
    theme: str | None = None
    font_family: str | None = None
    font_size: str | None = None
    # grocery budget moved to AppSetting (install-wide household budget);
    # edited via PATCH /api/budget/settings, not this endpoint.
    # voice opt-in toggles. Booleans only (no clear variant);
    # the feature is two-state per setting.
    voice_input_enabled: bool | None = None
    voice_output_enabled: bool | None = None
    # Voice engine + Piper voice. Closed-set sentinels validated below
    # (R-010 carve-out): engine ∈ ALLOWED_VOICE_ENGINES, voice_id ∈ the TTS
    # catalog's VOICE_IDS.
    voice_engine: str | None = None
    voice_id: str | None = None
    # money opt-in removed — money is one install-wide flag now.
    # FU-615 — `batch_features_enabled` moved to AppSetting (install-wide);
    # edited via PATCH /app-settings, not here.
    # Zero-Input Pantry opt-out (default True on the entity).
    inferred_pantry_enabled: bool | None = None
    buy_verdict_enabled: bool | None = None
    # FU-653 — per-surface belief overlays. Same shape as the toggle above.
    inference_recipes_enabled: bool | None = None
    inference_shopping_enabled: bool | None = None
    inference_meal_plan_enabled: bool | None = None
    # `nutrition_mode` removed — nutrition is install-wide (2026-08-14);
    # edited via PATCH /app-settings, not here.
    # FU-615 — `household_headcount` moved to AppSetting (install-wide);
    # edited via PATCH /app-settings, not here.
    # alerts email digest prefs (PROPOSAL_ALERTS §3.5 / §4.4).
    # Cadence is a closed-set sentinel validated at this boundary (R-010
    # carve-out, same shape as `nutrition_mode`). Day is Mon=0 … Sun=6
    # and only consulted on the weekly cadence; saved either way so a
    # cadence flip back to weekly remembers the picked day.
    # Settings rebuild Phase 4 (§2.9) — profile picture. Data-URL string to
    # set, `clear_image: true` to remove. Mirrors the Store image contract:
    # `image=None` without the clear flag means "leave untouched". Cap mirrors
    # the StockItem ceiling (~4.5 MB of base64).
    image: str | None = image_field()
    clear_image: bool = False
    # Dashboard rebuild Phase 2 — per-user dashboard layout JSON (card order +
    # hidden set). Present-in-body sets it; sending `null` clears it back to
    # the default layout. Opaque to the backend (client view-state); the cap is
    # generous for the small JSON but bounds abuse.
    dashboard_layout: str | None = Field(default=None, max_length=20_000)
    # per-user assistant Mode. `llm_enabled` is the AI-mode opt-in and
    # `llm_provider` the active provider (closed-set sentinel, R-010,
    # validated below against ALLOWED_LLM_PROVIDERS). The per-provider
    # details (base URL / model / API key) are edited via the
    # `/assistant/providers` endpoints, not here. Enabling AI mode requires
    # the active provider to already be verified (see the guard below).
    llm_enabled: bool | None = None
    llm_provider: str | None = Field(default=None, max_length=16)
    # FU-360.6 — per-user "show the Dora helper bubble" opt-out. Plain bool;
    # null is ignored (leave untouched). Independent of `llm_enabled`.
    show_assistant: bool | None = None
    daily_brief_enabled: bool | None = None
    # Days after which this user's alerts are discarded; null turns it off.
    # Validated against ALERT_DISCARD_DAY_OPTIONS in the handler.
    alert_discard_after_days: int | None = None


class UpdateMeHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(
        self,
        request: UpdateMeRequest,
        user_id: UUID,
    ) -> tuple[AuthenticatedUserDto | None, str | None]:
        """Returns (dto, error_message). Error is set when the change is
        rejected (e.g. username collision or invalid enum value)."""
        _User: User | None = self.repository.get(User).by_id(user_id)
        if not _User:
            return None, None

        _SetFields = request.model_fields_set

        if "username" in _SetFields and request.username is not None:
            _UsernameField = EntityField(User, User.Fields.USERNAME)
            _SameName: User | None = (
                self.repository.get(User).one(_UsernameField.eq(request.username))
            )
            if _SameName and _SameName.id != user_id:
                return None, f"Username '{request.username}' is already taken."
            _User.username = request.username

        if "email" in _SetFields:
            # Empty/whitespace clears the address; otherwise validate format
            # and reject a duplicate held by another account (email drives
            # password-reset delivery, so it stays unique even though login
            # is by username). Owner-entered mail is trusted — the verified
            # change flow is gone — so a set address counts as verified.
            _EmailNorm = normalise_email(request.email)
            if _EmailNorm:
                if not is_valid_email(_EmailNorm):
                    return None, "That doesn't look like a valid email address."
                _EmailField = EntityField(User, User.Fields.EMAIL)
                _SameEmail: User | None = (
                    self.repository.get(User).one(_EmailField.eq(_EmailNorm))
                )
                if _SameEmail and _SameEmail.id != user_id:
                    return None, f"Email '{_EmailNorm}' is already in use."
            if _User.email != _EmailNorm:
                _User.email = _EmailNorm
                _User.email_verified = bool(_EmailNorm)

        if "send_deals_on_day" in _SetFields and request.send_deals_on_day is not None:
            _User.send_deals_on_day = request.send_deals_on_day

        if "deals_email_enabled" in _SetFields and request.deals_email_enabled is not None:
            _User.deals_email_enabled = request.deals_email_enabled

        if "deals_email_compact" in _SetFields and request.deals_email_compact is not None:
            _User.deals_email_compact = request.deals_email_compact

        if "theme" in _SetFields and request.theme is not None:
            if request.theme not in ALLOWED_THEMES:
                return None, f"Invalid theme '{request.theme}'."
            _User.theme = request.theme

        if "font_family" in _SetFields and request.font_family is not None:
            if request.font_family not in ALLOWED_FONT_FAMILIES:
                return None, f"Invalid font family '{request.font_family}'."
            _User.font_family = request.font_family

        if "font_size" in _SetFields and request.font_size is not None:
            if request.font_size not in ALLOWED_FONT_SIZES:
                return None, f"Invalid font size '{request.font_size}'."
            _User.font_size = request.font_size

        # grocery budget moved to AppSetting (install-wide household budget);
        # edited via PATCH /api/budget/settings, not here.

        # voice prefs. Plain bool fields; null is ignored.
        if "voice_input_enabled" in _SetFields and request.voice_input_enabled is not None:
            _User.voice_input_enabled = request.voice_input_enabled
        if "voice_output_enabled" in _SetFields and request.voice_output_enabled is not None:
            _User.voice_output_enabled = request.voice_output_enabled

        # Voice engine + Piper voice. R-010 carve-out: closed-set sentinels
        # validated here against the domain engine set and the TTS catalog ids.
        if "voice_engine" in _SetFields and request.voice_engine is not None:
            if request.voice_engine not in ALLOWED_VOICE_ENGINES:
                return None, f"Invalid voice engine '{request.voice_engine}'."
            _User.voice_engine = request.voice_engine
        if "voice_id" in _SetFields and request.voice_id is not None:
            if request.voice_id not in VOICE_IDS:
                return None, f"Invalid voice '{request.voice_id}'."
            _User.voice_id = request.voice_id

        # money opt-in removed — money is a single install-wide flag
        # (AppSetting.money_enabled); there is no per-user money layer.
        # FU-615 — batch cook-style moved to AppSetting (install-wide).
        # Zero-Input Pantry opt-out.
        if (
            "inferred_pantry_enabled" in _SetFields
            and request.inferred_pantry_enabled is not None
        ):
            _User.inferred_pantry_enabled = request.inferred_pantry_enabled

        # D-12 — "should I buy this?" is a per-user display overlay since
        # 2026-08-19 (it was an install-wide AppSetting; B7). Same
        # null-is-ignored rule as its neighbour above.
        if "buy_verdict_enabled" in _SetFields and request.buy_verdict_enabled is not None:
            _User.buy_verdict_enabled = request.buy_verdict_enabled

        # FU-653 — the three per-surface overlays. Same null-is-ignored rule;
        # looped because the handling is identical for all three.
        for _Field in (
            "inference_recipes_enabled",
            "inference_shopping_enabled",
            "inference_meal_plan_enabled",
        ):
            _Value = getattr(request, _Field)
            if _Field in _SetFields and _Value is not None:
                setattr(_User, _Field, _Value)

        # FU-615 — household headcount moved to AppSetting (install-wide);
        # edited via PATCH /app-settings.

        # Settings rebuild Phase 4 — profile picture. `clear_image` wins over
        # any `image` in the same payload (clear is the primary intent), same
        # shape as the Store image handler. Stored as data-URL bytes.
        if request.clear_image:
            _User.image = None
        elif "image" in _SetFields and request.image is not None:
            _User.image = request.image.encode("utf-8")

        # Dashboard rebuild Phase 2 — layout JSON. Present-in-body sets it (a
        # null clears it back to the default layout). Stored verbatim; the
        # backend doesn't parse it (client view-state).
        if "dashboard_layout" in _SetFields:
            _User.dashboard_layout = request.dashboard_layout

        # per-user assistant Mode selection. `llm_provider` picks the active
        # provider (or None → Basic); `llm_enabled` is the AI opt-in. Details
        # for each provider live in the `UserLlmProvider` table, edited via
        # `/assistant/providers`.
        # FU-360.6 — show/hide the Dora helper bubble. Plain bool; null ignored.
        if "show_assistant" in _SetFields and request.show_assistant is not None:
            _User.show_assistant = request.show_assistant

        if "daily_brief_enabled" in _SetFields and request.daily_brief_enabled is not None:
            _User.daily_brief_enabled = request.daily_brief_enabled

        # Explicit null is meaningful here (keep alerts forever), so presence
        # in the body decides, not the value.
        if "alert_discard_after_days" in _SetFields:
            days = request.alert_discard_after_days
            if days is not None and days not in ALERT_DISCARD_DAY_OPTIONS:
                return None, (
                    f"alert_discard_after_days must be one of "
                    f"{list(ALERT_DISCARD_DAY_OPTIONS)} or null."
                )
            _User.alert_discard_after_days = days

        if "llm_provider" in _SetFields:
            provider = request.llm_provider
            if provider is not None:
                provider = provider.strip()
                if not provider:
                    provider = None
                elif provider not in ALLOWED_LLM_PROVIDERS:
                    return None, f"Invalid LLM provider '{provider}'."
            _User.llm_provider = provider
        if "llm_enabled" in _SetFields and request.llm_enabled is not None:
            _User.llm_enabled = request.llm_enabled

        # Cross-field validation: turning AI mode on requires an active
        # provider whose config has been verified (a live probe succeeded).
        # The Mode picker only offers verified providers, so this guards
        # direct/stale API calls.
        if _User.llm_enabled:
            if not _User.llm_provider:
                return None, "Pick a provider before enabling AI mode."
            active = get_provider_config(self.repository, user_id, _User.llm_provider)
            if active is None or not active.verified:
                return None, (
                    f"{_User.llm_provider} isn't verified yet. Test the "
                    f"connection in Settings → Assistant first."
                )

        self.repository.save_changes()
        active_provider = (
            get_provider_config(self.repository, user_id, _User.llm_provider)
            if _User.llm_provider else None
        )
        return AuthenticatedUserDto.from_entity(_User, active_provider), None


@AUTH_ROUTER.route("/me", methods=["PATCH"])
@has_request_body(UpdateMeRequest)
def update_me():
    _UserIdRaw = session.get(SESSION_USER_ID_KEY)
    if not _UserIdRaw:
        return unauthorized()
    try:
        _UserId = UUID(_UserIdRaw)
    except (ValueError, TypeError):
        session.clear()
        return unauthorized()

    _Request: UpdateMeRequest = get_request_body()
    _Dto, _Error = UpdateMeHandler(SqlAlchemyRepository()).handle(_Request, _UserId)

    if _Error is not None:
        return business_rule_violation(_Error)
    if _Dto is None:
        session.clear()
        return unauthorized()

    _LOGGER.info("Updated profile for user %s", _UserId)
    return ok(_Dto)
