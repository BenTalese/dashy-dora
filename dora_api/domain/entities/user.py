from dataclasses import dataclass
from datetime import datetime

from dora_api.domain.entities.base_entity import BaseEntity


# Preference enum-like constants. Kept here so handlers and DTOs share one
# source of truth and the frontend can validate against these values too.
THEME_SYSTEM = "system"
# Named themes — five families with paired light + dark variants. See
# web_app/src/services/themeService.ts THEME_FAMILIES for the source-
# of-truth palette + label metadata. `system` (and the per-family
# `system-*` variants below) resolves on the client based on
# `prefers-color-scheme`.
THEME_PESTO = "pesto"
THEME_PESTO_DARK = "pesto-dark"
THEME_LEMON_TART = "lemon-tart"
THEME_LEMON_TART_DARK = "lemon-tart-dark"
THEME_BLUEBERRY = "blueberry"
THEME_BLUEBERRY_DARK = "blueberry-dark"
THEME_CHERRY_COLA = "cherry-cola"
THEME_CHERRY_COLA_DARK = "cherry-cola-dark"
THEME_SOURDOUGH = "sourdough"
THEME_SOURDOUGH_DARK = "sourdough-dark"
# Owner, 2026-09-03 — two families added: a deliberately minimal neutral pair
# (Salt & Pepper: one warm graphite hue, value contrast only) and a pink one
# (Dragonfruit: magenta rind + green tips), the first pink in the picker.
THEME_SALT_PEPPER = "salt-pepper"
THEME_SALT_PEPPER_DARK = "salt-pepper-dark"
THEME_DRAGONFRUIT = "dragonfruit"
THEME_DRAGONFRUIT_DARK = "dragonfruit-dark"
# Round-19 — per-family system mode. Splits the Preferences picker into
# Mode (System / Light / Dark) + Theme (Pesto / Lemon Tart / …) so a
# user can follow the OS using any family's variants, not just Pesto.
THEME_SYSTEM_PESTO = "system-pesto"
THEME_SYSTEM_LEMON_TART = "system-lemon-tart"
THEME_SYSTEM_BLUEBERRY = "system-blueberry"
THEME_SYSTEM_CHERRY_COLA = "system-cherry-cola"
THEME_SYSTEM_SOURDOUGH = "system-sourdough"
THEME_SYSTEM_SALT_PEPPER = "system-salt-pepper"
THEME_SYSTEM_DRAGONFRUIT = "system-dragonfruit"
# Legacy values accepted on the wire so existing rows don't fail
# validation; the SPA's themeService maps each to a current key at
# apply time:
#   pesto-noir       → pesto-dark
#   midnight-snack   → lemon-tart-dark   (absorbed into Lemon Tart family)
#   light, avocado   → pesto
#   dark             → pesto-dark
THEME_PESTO_NOIR = "pesto-noir"
THEME_MIDNIGHT_SNACK = "midnight-snack"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_AVOCADO = "avocado"
ALLOWED_THEMES = (
    THEME_SYSTEM,
    THEME_PESTO, THEME_PESTO_DARK,
    THEME_LEMON_TART, THEME_LEMON_TART_DARK,
    THEME_BLUEBERRY, THEME_BLUEBERRY_DARK,
    THEME_CHERRY_COLA, THEME_CHERRY_COLA_DARK,
    THEME_SOURDOUGH, THEME_SOURDOUGH_DARK,
    THEME_SALT_PEPPER, THEME_SALT_PEPPER_DARK,
    THEME_DRAGONFRUIT, THEME_DRAGONFRUIT_DARK,
    # Per-family system keys (round-19).
    THEME_SYSTEM_PESTO,
    THEME_SYSTEM_LEMON_TART,
    THEME_SYSTEM_BLUEBERRY,
    THEME_SYSTEM_CHERRY_COLA,
    THEME_SYSTEM_SOURDOUGH,
    THEME_SYSTEM_SALT_PEPPER,
    THEME_SYSTEM_DRAGONFRUIT,
    # Legacy
    THEME_PESTO_NOIR,
    THEME_MIDNIGHT_SNACK,
    THEME_LIGHT,
    THEME_DARK,
    THEME_AVOCADO,
)

FONT_FAMILY_DEFAULT = "default"
FONT_FAMILY_URBANIST = "urbanist"
FONT_FAMILY_NUNITO = "nunito"
FONT_FAMILY_INTER = "inter"
FONT_FAMILY_LEXEND = "lexend"
FONT_FAMILY_PLUS_JAKARTA_SANS = "plus_jakarta_sans"
ALLOWED_FONT_FAMILIES = (
    FONT_FAMILY_DEFAULT,
    FONT_FAMILY_URBANIST,
    FONT_FAMILY_NUNITO,
    FONT_FAMILY_INTER,
    FONT_FAMILY_LEXEND,
    FONT_FAMILY_PLUS_JAKARTA_SANS,
)

FONT_SIZE_SM = "sm"
FONT_SIZE_MD = "md"
FONT_SIZE_LG = "lg"
FONT_SIZE_XL = "xl"  # A6 — extra-large step
ALLOWED_FONT_SIZES = (FONT_SIZE_SM, FONT_SIZE_MD, FONT_SIZE_LG, FONT_SIZE_XL)

# grocery-budget period constants moved to AppSetting (the budget is now an
# install-wide household concept, not per-user — see app_setting.py
# BUDGET_PERIOD_*). This "grocery budget belongs to the household, not the
# person" move mirrors FU-615 (household_headcount / batch_features_enabled).

# Nutrition mode moved to `AppSetting` (owner call 2026-08-14) — it was a
# per-user mode layered on a second install-wide bool, the same double-switch
# shape money shed on 2026-08-12. Constants now live in
# `entities/app_setting.py`; `User.nutrition_mode` is dropped.

# Voice — which speech engine speaks Dora's replies / cook-mode steps and,
# for the Piper engine, which catalog voice. R-010 carve-out: closed-set
# string sentinels validated at a single boundary (`update_me.py`). The
# engine is the user's *preference*; if Piper can't actually speak (no
# binary / model), the SPA transparently falls back to the browser voice
# (see useSpeechOutput) — so `piper` is a safe default. The set of valid
# `voice_id`s is owned by the TTS feature catalog (features/tts/
# voice_catalog.py `VOICE_IDS`), not duplicated here.
VOICE_ENGINE_BROWSER = "browser"
VOICE_ENGINE_PIPER = "piper"
ALLOWED_VOICE_ENGINES = (VOICE_ENGINE_BROWSER, VOICE_ENGINE_PIPER)


# per-user LLM provider. Closed set validated at the
# update_me boundary (R-010 carve-out, same shape as nutrition_mode).
# Ollama is the local/free path; OpenAI /
# Anthropic / Gemini are paid API providers that additionally require
# an encrypted API key.
LLM_PROVIDER_OLLAMA = "ollama"
LLM_PROVIDER_OPENAI = "openai"
LLM_PROVIDER_ANTHROPIC = "anthropic"
LLM_PROVIDER_GEMINI = "gemini"
ALLOWED_LLM_PROVIDERS = (
    LLM_PROVIDER_OLLAMA,
    LLM_PROVIDER_OPENAI,
    LLM_PROVIDER_ANTHROPIC,
    LLM_PROVIDER_GEMINI,
)
# Subset that needs an API key — used by update_me to decide when to
# fail-fast if the install hasn't configured key encryption.
LLM_PROVIDERS_REQUIRING_API_KEY = (
    LLM_PROVIDER_OPENAI,
    LLM_PROVIDER_ANTHROPIC,
    LLM_PROVIDER_GEMINI,
)


# The discard windows a user can pick (R-010: one closed set, checked once at
# the PATCH /auth/me boundary). Fourteen is the default: long enough to cover a
# fortnight away, short enough that the bell never becomes an archive.
ALERT_DISCARD_DAY_OPTIONS = (7, 14, 30)


@dataclass
class User(BaseEntity):
    email: str | None
    password_hash: str | None
    send_deals_on_day: int
    username: str
    is_admin: bool = False
    # Owner call 2026-08-17 — an account can be *switched off* instead of
    # deleted. Deletion is destructive and irreversible (sessions, alert
    # prefs and push subscriptions go with it); a housemate who moved out,
    # or an account you want to park, only needs the door locked. Enforced
    # in two places and nowhere else: `login` refuses to mint a session for
    # an inactive user, and `get_me` clears an existing cookie on the next
    # probe — so deactivating someone signs them out rather than waiting
    # for their session to lapse. The admin API refuses to deactivate you
    # (self) or the last active admin, mirroring the `is_admin` guard.
    is_active: bool = True
    # Opt-IN flag for the weekly deals email; the preferred send day
    # (`send_deals_on_day`) is kept independently so toggling off and back on
    # doesn't lose it.
    #
    # Was `True` when this column was added, to keep pre-existing subscribers
    # receiving mail across the migration. That rationale is dead (pre-release,
    # no real users) and the default was actively wrong: a fresh install has no
    # SMTP, so every new user landed pre-subscribed to an email the server
    # cannot send — and the Notifications toggle is `:disable`d without SMTP, so
    # they couldn't even turn it off. Email channels are opt-in
    # (P10 Anti-creep); this is now the only one.
    deals_email_enabled: bool = False
    deals_email_compact: bool = False
    theme: str = THEME_SYSTEM
    font_family: str = FONT_FAMILY_DEFAULT
    font_size: str = FONT_SIZE_MD
    # NULL until the user finishes (or skips) the welcome wizard. The
    # auth/router guard reads this on every navigation to decide whether
    # to bounce them to /welcome. Cleared by `POST /onboarding/restart`
    # (About → "Run the welcome tour again", and the 24-hour skip banner).
    onboarding_completed_at: datetime | None = None
    # A1: marks whether the user has clicked the verify-email link sent on
    # registration. First-user-is-admin auto-verifies so a fresh install
    # without SMTP doesn't lock its admin out.
    email_verified: bool = False
    # A1: bumped on every successful password change / reset. Stored as
    # the cutoff a session cookie's issued-at must beat, so resetting a
    # password effectively invalidates every existing session.
    password_changed_at: datetime | None = None
    # grocery budget moved to AppSetting (install-wide household budget):
    # spend is summed across every shared shopping list, so the target has
    # to be shared too — a per-user budget compared against a household
    # spend total is incoherent. See app_setting.py + FU-615 precedent.
    # voice opt-ins. Off by default because the Web Speech APIs
    # are permission-gated and behaviour varies by browser; we never
    # silently activate a microphone or speaker. The SPA reads these on
    # boot to seed the per-page toggles.
    voice_input_enabled: bool = False
    voice_output_enabled: bool = False
    # Voice engine + Piper voice selection. `voice_engine` is `browser` |
    # `piper`; default `piper` so Dora uses the nicer neural voice when it's
    # available (the bundled Amy/Ryan models ship for this), with a
    # browser-speech fallback when it isn't. `voice_id` names the chosen
    # catalog voice (default Amy). Only consulted when `voice_output_enabled`
    # is on — these decide *how* she speaks, not *whether*.
    voice_engine: str = VOICE_ENGINE_PIPER
    voice_id: str = "amy"
    # money-features opt-in removed: money is a single install-wide
    # concern now (AppSetting.money_enabled). There is no per-user money
    # layer — if the install has money on, dollar surfaces render for
    # everyone; off hides them for everyone. Dropped the old per-user
    # `money_features_enabled` (owner call: "kitchen setup, not personal").
    # FU-615 — `batch_features_enabled` moved to AppSetting (install-wide
    # cook-style; a household has one cook-style, not one per person).
    # per-user "always ask which draft list on quick-add" toggle.
    # Zero-Input Pantry opt-out. Default True: inferred stock
    # levels (the belief overlay) are the headline experience. Charter 10 —
    # some users want purely manual control, so this toggle switches the
    # belief chip + inference-driven quick-checks off.
    inferred_pantry_enabled: bool = True
    # D-12 (`IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`) — "should I buy this?"
    # moved here from `AppSetting.buy_verdict_enabled` on 2026-08-19. It was
    # household-scoped for a pure per-user *display* overlay, so one person
    # hiding a badge hid it for everyone (B7; owner confirmed the original
    # scoping was a mistake). The rule it established: a setting that mutates
    # shared state is household-scoped; one that only changes what you see is
    # per-user. Sits beside `inferred_pantry_enabled` because it's the same kind
    # of thing — one of Dora's opinions, which you may or may not want to read.
    buy_verdict_enabled: bool = True
    # FU-653 — the same belief, surfaced where stock items *appear* rather
    # than where they're managed: a remark on a recipe whose ingredient Dora
    # thinks has run out, suggestions on a shopping list, a flag on a planned
    # meal. One toggle each (owner, 2026-08-17) because they annotate three
    # different jobs, and someone who wants the recipe hint may not want their
    # shopping list editorialised. **Default False**, unlike the stock toggle
    # above: these add commentary to pages the user opened for another reason,
    # so they're opt-in. `inferred_pantry_enabled` remains the *stock* surface's
    # switch. Single authority for reading them:
    # `features/stock_items/inference_overlay.SURFACE_FLAGS`.
    inference_recipes_enabled: bool = False
    inference_shopping_enabled: bool = False
    inference_meal_plan_enabled: bool = False
    # `show_recipe_images` removed 2026-08-29. The C-cross Chunk 5 opt-in
    # was designed to govern every recipe photo in the app so a user could
    # run a text-dense, low-bandwidth UI; FU-508 dropped its stock-image
    # half, the cookbook's cards/compact switch took photos over there, and
    # cook mode / print / the planner rail never honoured it — leaving one
    # hero image, behind a toggle that swapped it for a same-sized "Photo
    # hidden" box. See ADR-062.
    # FU-615 — `household_headcount` moved to AppSetting (install-wide;
    # a household has one headcount). Cook mode reads it via /api/health.
    # (No alerts-email fields — the digest was cut at Step-0 Q4,
    # `IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`. Alerts reach the user
    # in-app and via web push; `daily_brief_enabled` below is the one
    # scheduled summary that survives.)
    # Settings rebuild Phase 4 (§2.9) — optional profile picture, stored as a
    # data-URL blob (same convention as Store/StockItem images). Deferred at
    # the ORM layer so list endpoints never drag the bytes per row; the
    # dedicated `/users/<id>/image` route triggers the load on access and
    # `has_image` is derived from an IS-NOT-NULL check (mirrors StoreDto).
    image: bytes | None = None
    # Dashboard rebuild Phase 2 — per-user dashboard layout (card order +
    # hidden set + future zone tweaks), stored as a small JSON string. NULL =
    # the user hasn't customised; the SPA falls back to the default order. Kept
    # opaque to the backend on purpose (it's pure client view-state, R-003:
    # presentation belongs to the client) — we persist it verbatim so it
    # survives a cache clear and follows the user across devices.
    dashboard_layout: str | None = None
    # per-user assistant config. `llm_enabled` is the user's own opt-in and
    # the sole gate on AI mode — there is no install-wide master switch
    # (removed 2026-08-12). `llm_provider` names the *active* provider
    # (closed-set sentinel, R-010 / ALLOWED_LLM_PROVIDERS) or NULL for
    # Basic mode. The per-provider details (base URL / model / API key /
    # verified) live in the `UserLlmProvider` child table so a user can
    # configure several providers and flip between them — this column just
    # points at the one in use.
    llm_enabled: bool = False
    llm_provider: str | None = None
    # FU-360.6 — per-user "show the Dora helper bubble at all" opt-out.
    # **Default True** (Charter P1 Effortless — the helper is discoverable by
    # default). Distinct from `llm_enabled`: that switches the AI *mode*; this
    # hides the whole assistant launcher for users who don't want it. When
    # False the SPA doesn't mount the bubble, so Basic *and* AI mode are gone.
    show_assistant: bool = True
    # Daily brief push (owner, 2026-08-17). ONE push per day, at
    # DAILY_BRIEF_HOUR household-local, summarising tomorrow's meals and any
    # shopping day that's due. Deliberately *not* a per-slot reminder: five
    # slots across seven days is up to 35 notifications a week, which trains
    # the user to ignore the channel (Charter P10 Anti-creep). The owner also
    # ruled out a just-in-time "dinner's in an hour" nudge — "they know when
    # dinner is" — which is why `MealSlot` still has no start time.
    #
    # Opt-IN (default False), matching every other notification channel here.
    # The send hour is fixed rather than configurable: one fewer thing to set
    # up, and evening is the only hour where the brief is *actionable* (you
    # can still defrost something or fill a gap in the plan).
    daily_brief_enabled: bool = False
    # Owner 2026-10-15 — "discard alerts older than X days". Alerts whose
    # episode began more than this many days ago drop out of this user's bell,
    # as if dismissed. NULL keeps everything. One of `ALERT_DISCARD_DAY_OPTIONS`.
    alert_discard_after_days: int | None = 14
    # Chunk 6 / D-4 — when this user last finished a stocktake session. The
    # Sweep phase needs it: it shows items that dropped out of rotation *since
    # your last run*, not the full excluded set (the tin you stopped buying two
    # years ago is supposed to stay invisible — surfacing it every session is
    # exactly the nagging this plan removes). "Newly excluded" is therefore an
    # event relative to a per-user watermark.
    #
    # **Per-user, not household**, deliberately: a stocktake is a shared
    # activity but "what changed since *I* last looked" is a personal question,
    # and two people sharing a pantry would otherwise blank each other's Sweep.
    # NULL = never run one; the Sweep phase stays empty on a first session
    # rather than dumping every long-dead item into it.
    stocktake_last_session_at: datetime | None = None
    # TODO: avoid god object | separate auth credential from user profile

    class Fields(BaseEntity.Fields):
        EMAIL = "email"
        PASSWORD_HASH = "password_hash"
        SEND_DEALS_ON_DAY = "send_deals_on_day"
        USERNAME = "username"
        IS_ADMIN = "is_admin"
        IS_ACTIVE = "is_active"
        DEALS_EMAIL_ENABLED = "deals_email_enabled"
        DEALS_EMAIL_COMPACT = "deals_email_compact"
        THEME = "theme"
        FONT_FAMILY = "font_family"
        FONT_SIZE = "font_size"
        ONBOARDING_COMPLETED_AT = "onboarding_completed_at"
        EMAIL_VERIFIED = "email_verified"
        PASSWORD_CHANGED_AT = "password_changed_at"
        VOICE_INPUT_ENABLED = "voice_input_enabled"
        VOICE_OUTPUT_ENABLED = "voice_output_enabled"
        VOICE_ENGINE = "voice_engine"
        VOICE_ID = "voice_id"
        INFERRED_PANTRY_ENABLED = "inferred_pantry_enabled"
        BUY_VERDICT_ENABLED = "buy_verdict_enabled"
        INFERENCE_RECIPES_ENABLED = "inference_recipes_enabled"
        INFERENCE_SHOPPING_ENABLED = "inference_shopping_enabled"
        INFERENCE_MEAL_PLAN_ENABLED = "inference_meal_plan_enabled"
        IMAGE = "image"
        DASHBOARD_LAYOUT = "dashboard_layout"
        LLM_ENABLED = "llm_enabled"
        LLM_PROVIDER = "llm_provider"
        SHOW_ASSISTANT = "show_assistant"
        DAILY_BRIEF_ENABLED = "daily_brief_enabled"
        ALERT_DISCARD_AFTER_DAYS = "alert_discard_after_days"
        STOCKTAKE_LAST_SESSION_AT = "stocktake_last_session_at"
