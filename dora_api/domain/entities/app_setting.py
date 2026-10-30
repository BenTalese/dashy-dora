from dataclasses import dataclass

from dora_api.domain.entities.base_entity import BaseEntity

# grocery-budget period. `weekly` rolls from Monday; `monthly` from the 1st
# (local-civil-date for simplicity; the home use-case doesn't justify
# timezone gymnastics). Lives here because the budget is a household concept
# (see `budget_amount` / `budget_period` below) — it moved off User.
BUDGET_PERIOD_WEEKLY = "weekly"
BUDGET_PERIOD_MONTHLY = "monthly"
ALLOWED_BUDGET_PERIODS = (BUDGET_PERIOD_WEEKLY, BUDGET_PERIOD_MONTHLY)

# Nutrition depth, install-wide (owner call 2026-08-14 — moved off `User`,
# where it had been a per-user mode layered on a second install-wide bool).
# R-010 carve-out: closed-set string sentinel, single validation point in
# `update_app_settings.py`, named constants at every read. SQLite-portable.
#
#   off      — the whole feature is hidden.
#   simple   — one hand-typed kcal number per recipe. No data source involved.
#   complex  — stock items link to foods in a nutrition catalogue, and recipe
#              nutrition rolls up from those links. Needs at least one source
#              available; see `features/nutrition/sources.py`.
NUTRITION_MODE_OFF = "off"
NUTRITION_MODE_SIMPLE = "simple"
NUTRITION_MODE_COMPLEX = "complex"
NUTRITION_MODE_VALUES = (
    NUTRITION_MODE_OFF,
    NUTRITION_MODE_SIMPLE,
    NUTRITION_MODE_COMPLEX,
)

# Which front-of-pack nutrition rating, if any, this install puts on recipes
# (owner call 2026-08-27). Same R-010 carve-out shape as the nutrition mode
# above: closed-set string sentinel, one validation point, named constants at
# every read.
#
#   none         — no rating anywhere. The default.
#   health_star  — the Australian/New Zealand Health Star Rating (FSANZ),
#                  0.5–5 stars. See `domain/health_star_rating.py`.
#   nutri_score  — the European Nutri-Score, updated (2023) algorithm, A–E.
#                  See `domain/nutri_score.py`.
#
# **Deliberately one choice rather than a set.** Both schemes answer the same
# question with different national arithmetic, and two competing verdicts on
# one recipe card is a worse product than either alone — the reader's next
# question becomes "which do I believe?", which Dora cannot answer for them.
# Charter Anti-creep tiebreak.
#
# `none` is the default for every install, including Australian ones. Neither
# scheme is a universal fact about food, and Dora does not pick a nutritional
# authority on a household's behalf at install time; Settings' "Match this
# device" offers the locally-recognised one and the picker takes any of them
# anywhere.
RATING_SCHEME_NONE = "none"
RATING_SCHEME_HEALTH_STAR = "health_star"
RATING_SCHEME_NUTRI_SCORE = "nutri_score"
RATING_SCHEME_VALUES = (
    RATING_SCHEME_NONE,
    RATING_SCHEME_HEALTH_STAR,
    RATING_SCHEME_NUTRI_SCORE,
)


@dataclass
class AppSetting(BaseEntity):
    """Install-wide settings, edited by admins. A single row — see
    features/app_settings for the get-or-create accessor.

    The assistant (Dora's AI mode) is opt-in and bring-your-own-LLM: an admin
    enables it and points it at an LLM endpoint they run themselves (e.g. a
    local Ollama). Nothing is enabled or downloaded by default.

    Scanning + QR labels (real-world barcode → product navigation, plus Dora's
    own item/shelf QR labels) are one opt-in surface gated by a single
    install-wide flag, off by default. Scanning is navigation-only — it never
    does live deal lookup.
    """
    # AI mode is a purely per-user concern — each account configures its own
    # provider/URL/model/API key on Settings → Assistant and opts in via
    # `User.llm_enabled`. There is deliberately no install-wide master
    # kill-switch: the old `master_llm_enabled` toggle was removed (owner
    # call 2026-08-12 — "allow users to use AI if they wish"). Per-user
    # URL / model / provider / API key live on User (see entity below).
    scanning_enabled: bool = False
    # SEC-3 — whether the login page offers "Create account" and
    # `POST /auth/register` accepts anyone who asks. Off by default: on a
    # household install the admin creates each account (Users page); an open
    # door on an install reachable through a reverse proxy let any visitor
    # sign in to the household's data.
    registration_enabled: bool = False
    # Owner ask 2026-08-27 — which front-of-pack rating goes on recipes.
    #
    # Started life as `health_star_rating_enabled`, a bool. It became a picker
    # the same week, because a boolean could only ever mean "the Australian one
    # or nothing", which read to everyone else as "this feature is not for
    # you". See `RATING_SCHEME_VALUES` for the options and why only one may be
    # active at a time.
    #
    # Whichever scheme is chosen also needs `nutrition_mode == complex` to
    # produce anything: a rating is computed from the foods the ingredients
    # link to, and simple mode has only a typed kcal. A scheme selected while
    # nutrition is in simple mode is a no-op, not an error.
    nutrition_rating_scheme: str = RATING_SCHEME_NONE
    # buy-verdict oracle ("should I buy this?"). Defaults **on**
    # because it's a pure-personal feature: no external calls, no crowd
    # data, no config required — the composer just needs the user's own
    # shopping-list / waste history. Admin can turn it off if the row-level
    # badges feel noisy on their pantry.
    # `buy_verdict_enabled` moved to User 2026-08-19 (D-12) — it only
    # changes what one person sees, so it was never household state.
    # C-cross Chunk 1 — install-wide feature flags (proposal §2.6). Surface
    # via `/api/health features.*` + admin-only `PATCH /api/admin/feature-
    # flags`. Per-user opt-ins (money, nutrition, image display) layer on
    # top of these — install flag = "available here at all"; user flag =
    # "do I personally want to see it". Defaults are conservative: every
    # flag here ships off.
    # `meal_planning_enabled` removed 2026-09-03 (owner call). It never
    # gated the meal-plans surface the way its own copy claimed — the nav
    # entry and the route were unconditional — so the only thing it did was
    # switch off the planned-demand signal. Meal planning is core; there was
    # nothing to turn off. Column dropped in migration a7c3e5d19f2b.
    money_enabled: bool = False
    # `deals_email_enabled` removed 2026-10-15 (owner): the weekly deals mail
    # sends whenever email is set up and the person has opted in, so an
    # install-wide switch on top of the per-user one only hid it. Column
    # dropped in migration e4b7c2a9f1d3.
    # `products_enabled` removed —
    # products is now a *data-presence* overlay. `features.products` is derived
    # server-side from whether any `Product` row exists (see health_check), not
    # from an admin/persona flag. The column is dropped in migration
    # f1a2b3c4d5e6.
    # Nutrition (owner call 2026-08-14). Two things changed at once here:
    #
    # 1. `nutrition_enabled` (install bool) + `User.nutrition_mode` (per-user
    #    off/simple/complex) collapsed into this **single install-wide** field.
    #    Two switches answering "is nutrition on?" was the money-settings shape
    #    the owner already had removed on 2026-08-12; nutrition kept it until
    #    now. `off` here means the whole feature is hidden.
    # 2. The dead `nutrition_db_source` seam is gone. It was a free-form string
    #    with no UI anywhere, whose only job was to gate a `complex` mode that
    #    had zero implementation. Complex is real now, and its availability is
    #    *derived* (do we hold a dataset / is a key set / is OFF reachable)
    #    rather than asserted by a magic string.
    nutrition_mode: str = NUTRITION_MODE_OFF
    # Optional api.data.gov key for querying USDA live instead of holding the
    # bulk dataset on disk. Empty ⇒ that provider is simply not offered.
    nutrition_usda_api_key: str = ""
    # Whether lookups may reach Open Food Facts for barcoded products. On by
    # default (it needs no key and the app already calls OFF for barcode-to-add),
    # but an offline or air-gapped install turns it off so the lookup stops
    # trying to reach the network.
    nutrition_off_lookup_enabled: bool = True
    # Meal Plans C-2.K — household IANA timezone (e.g. "Australia/Sydney").
    # The "today" date boundary is evaluated here, not server-local, so a
    # household is correct regardless of where the server is hosted. Default
    # UTC until an admin sets it in System settings. App-wide adoption: FU-174.
    timezone: str = "UTC"
    # Alerts C-9.2 — household-wide "expiring soon" window used by both the
    # alerts feed and the assistant (PROPOSAL_ALERTS §3.3). One server-side
    # source (R-003); the constant `EXPIRING_SOON_WINDOW_DAYS` is now the
    # seeded default, resolved via `stock_status.effective_expiring_soon_window`.
    expiring_soon_window_days: int = 7
    # Phase D / FU-186 — install-wide URL the Product Search nav entry opens
    # in a new tab when product data is present. Set by the install operator
    # to point at whatever search surface they run themselves (a sibling
    # companion, a static page, etc — Dora doesn't know or care).
    # Empty string ⇒ no URL configured; the "Product Search" nav entry is
    # hidden entirely until a URL is set (setting it, in Settings → Features,
    # is what makes the button appear). See
    # `docs/04_proposals/PROPOSAL_PRODUCTS_AS_OVERLAY.md` §4.1.
    product_search_url: str = ""
    # Which units this household measures in: `"metric"`, `"imperial"` or
    # `"us"`. Two jobs, one fact (R-003):
    #   1. every unit picker in the app offers that system's units plus the
    #      universal ones (pinch / dash / ea / pack …) — see
    #      `units.units_for_system`;
    #   2. per-unit prices are quoted in that system's shelf convention —
    #      `/100ml`,`/100g`,`/L`,`/kg` for metric and imperial (the UK prices
    #      in metric too), `/fl oz`,`/qt`,`/oz`,`/lb` for US.
    # Replaced `unit_pricing_locale` ("AU"/"US") on 2026-08-27, which covered
    # only job 2, was never exposed in the UI, and would have been a second
    # name for the same choice the moment job 1 landed. Compute math stays in
    # canonical L/kg regardless; only the rendered denominator changes.
    # Default metric — Dora is built here and ships AU-first.
    measurement_system: str = "metric"
    # install-wide currency + display
    # locale, so a non-AU install renders money and dates in a form its users
    # recognise. Single-source (R-003): every money render on the client goes
    # through one `Intl.NumberFormat(locale, { style: 'currency', currency })`
    # wrapper that reads both values from `/api/health`. Household-scoped
    # (one currency per install) — user chose install-wide over per-user,
    # matching the "a household shares a currency" model in the brief.
    # `currency` is an ISO 4217 code (3 letters); `locale` is a BCP-47 tag.
    # Defaults keep AU-shipped behaviour intact for existing installs.
    currency: str = "AUD"
    locale: str = "en-AU"
    # backup library controls. `backup_retention_count` caps
    # the library; oldest above the cap is auto-dropped on each new
    # write. Default 5 is Pi-disk-conscious. `backup_storage_path`
    # empty ⇒ resolved to `$DORA_DATA_DIR/backups/` at runtime; an
    # admin may point at an external mount / NAS path (validated on
    # save).
    backup_retention_count: int = 5
    backup_storage_path: str = ""
    # install-wide image compression knobs. Applied at upload
    # time by the client-side `processImageFile` helper (R-003 pipeline
    # chokepoint) to every image surface. Existing images are untouched
    # — forward-only. 85 is visually indistinguishable from "original";
    # 60–70 is the disk-conscious floor. `image_max_dimension` caps the
    # longest edge in pixels; images above are scaled down first.
    image_quality: int = 85
    image_max_dimension: int = 1920
    # PROPOSAL_STOCKTAKE_MODE §4 + §8 — the two global stocktake knobs.
    # `stocktake_default_cadence_band` is the baseline cadence when Auto
    # is off, and the fallback for items with no movement history.
    # Values: `'weekly'` (7d) / `'fortnightly'` (14d) / `'monthly'` (30d).
    # `stocktake_auto_tuning_enabled` is the master switch for the
    # movement-history self-tuner ("auto = speed" per the user's design
    # call) — on by default so a fresh install "just works".
    stocktake_default_cadence_band: str = "fortnightly"
    stocktake_auto_tuning_enabled: bool = True
    # 2026-08-20 owner feedback — the install-wide stocktake master switch and
    # the opt-in default it hands new items.
    # `stocktake_enabled` False = the feature doesn't exist for this install:
    # the Stock-overview button, the "Needs check" filter, the per-item mute
    # toggle and the queue all disappear, and `resolve_overdue_map` (the single
    # overdue authority, R-003) returns an empty map so the alerts bell can't
    # nag about a surface nobody can open.
    # `stocktake_new_items_opt_in` is what `create_stock_item` seeds
    # `StockItem.stocktake_alerts_are_enabled` with — True keeps the 2026-08-17
    # "an item you bothered to add is one you want checked" default; False lets
    # an install opt items in by hand instead.
    stocktake_enabled: bool = True
    stocktake_new_items_opt_in: bool = True
    # FU-317 (D5 install-wide, FU-517) — household-shared posture for the
    # daily meal-plan reconcile sweep. TRUE (default) keeps today's silent
    # `reconcile_consumed_meals` drain plus a new receipt the user can
    # dispute on `/meal-plans/reconcile`. FALSE flips the sweep to write
    # `unresolved_manual` receipts and leave `MealPlanEntry.consumed_at` +
    # `Recipe.available_meals` untouched — the reconcile page becomes the
    # mutation surface. Install-wide (not per-user) because `MealPlan` has
    # no user_id / household_id — the plan is household-shared, so the
    # posture must be too. See PROPOSAL_MEAL_RECONCILE.md §2 + §11 D5.
    auto_drain_past_meals: bool = True
    # FU-511 — install-wide auto-add mode. Replaces the per-item
    # `StockItem.auto_add_when_low` boolean with one setting shared by
    # every item. Values:
    #   `'off'`            — never auto-add on low.
    #   `'essential_only'` — fire only for items flagged as essential
    #                        (`is_essential=True`). Default.
    #   `'all'`            — fire for any item that transitions Stocked
    #                        → Low/Out.
    # The `essential_only` default is the closest single behaviour to
    # the pre-migration pattern (auto-add was conceptually a marker of
    # "staple you never want to run out of" — same shape as Essential).
    # Server-side authority; see `update_stock_item._try_auto_add`.
    auto_add_mode: str = "essential_only"
    # FU-615 — household cooking config, install-wide (moved off User).
    # `household_headcount` is how many people the household usually cooks
    # for; NULL = not set (cook mode falls back to each recipe's own
    # `servings`). `batch_features_enabled` is the household's cook-style:
    # False ("fresh") keeps the meal-planner pure scheduling, True ("batch")
    # reveals the cook-pool affordances (per-recipe ± / log-cook / "n free"),
    # the shortfall warning, and the "to cook by" line. Both were per-user
    # (a convenience home for cook-mode's scaler); a household has one
    # headcount + one cook-style, so they're install-wide now. Read by every
    # client via /api/health.cooking_policy; edited by an admin in
    # Settings → System → Cooking.
    household_headcount: int | None = None
    batch_features_enabled: bool = False
    # household grocery budget (moved off User). The budget tracks spend
    # across every *shared* shopping list in the period, so the target must
    # be shared too — one budget per household, not per person (same class
    # of fix as household_headcount above). `budget_amount` NULL/≤0 ⇒ the
    # feature is off (value-driven: no amount = no budget); a positive value
    # turns on the dashboard + assistant + meal-plan budget surfaces.
    # `budget_period` picks the rolling window. We deliberately don't store
    # the period *start* — it's derived from the current date so it can't go
    # stale. Any authenticated household member edits these via
    # `PATCH /api/budget/settings`; clients read them via
    # `/api/health.budget_policy`.
    budget_amount: float | None = None
    budget_period: str = BUDGET_PERIOD_WEEKLY
    # operational config that was formerly carried as
    # `DORA_*` env vars. An admin now configures a fresh install through
    # Settings → Admin → System; the two remaining bootstrap-only vars
    # (`DORA_SECRET_KEY`, `DORA_SECRET_ENCRYPTION_KEY`) stay in env because
    # they're read before the DB is reachable / are root keys the DB
    # ciphertext depends on. On desktop bundles both are auto-generated on
    # first boot (see `desktop_app.py _bootstrap_keys`).
    #
    # Bucket C secrets — SMTP password + VAPID private key — live here
    # encrypted at rest with the Fernet helper at
    # `infrastructure/security/secret_encryption` using
    # `DORA_SECRET_ENCRYPTION_KEY` as the wrapping key. The plaintext
    # never leaves the write handler; reads decrypt on demand inside the
    # resolver. The DTO surfaces a `<field>_configured: bool` instead of
    # the ciphertext so the admin UI can render Set/Change without ever
    # transporting the secret.
    #
    # SMTP (was DORA_SMTP_HOST / _PORT / _USERNAME / _PASSWORD / _FROM / _USE_TLS).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password_encrypted: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    # Push (was DORA_VAPID_PUBLIC_KEY / _PRIVATE_KEY / _SUBJECT).
    vapid_public_key: str = ""
    vapid_private_key_encrypted: str = ""
    vapid_subject: str = "mailto:admin@dora.local"
    # TTS / Piper (was DORA_PIPER_BIN / _BUNDLED_VOICE_DIR).
    piper_bin: str = ""
    piper_bundled_voice_dir: str = ""
    # Misc operational.
    # `email_enabled` was DORA_EMAIL_ENABLED — the install-wide "email
    # subsystem is switched on" flag surfaced via /api/health features.email.
    email_enabled: bool = False
    audit_retention_days: int = 365
    public_url: str = ""

    class Fields(BaseEntity.Fields):
        SCANNING_ENABLED = "scanning_enabled"
        REGISTRATION_ENABLED = "registration_enabled"
        NUTRITION_RATING_SCHEME = "nutrition_rating_scheme"
        MONEY_ENABLED = "money_enabled"
        NUTRITION_MODE = "nutrition_mode"
        NUTRITION_USDA_API_KEY = "nutrition_usda_api_key"
        NUTRITION_OFF_LOOKUP_ENABLED = "nutrition_off_lookup_enabled"
        TIMEZONE = "timezone"
        EXPIRING_SOON_WINDOW_DAYS = "expiring_soon_window_days"
        PRODUCT_SEARCH_URL = "product_search_url"
        MEASUREMENT_SYSTEM = "measurement_system"
        CURRENCY = "currency"
        LOCALE = "locale"
        BACKUP_RETENTION_COUNT = "backup_retention_count"
        BACKUP_STORAGE_PATH = "backup_storage_path"
        IMAGE_QUALITY = "image_quality"
        IMAGE_MAX_DIMENSION = "image_max_dimension"
        STOCKTAKE_DEFAULT_CADENCE_BAND = "stocktake_default_cadence_band"
        STOCKTAKE_AUTO_TUNING_ENABLED = "stocktake_auto_tuning_enabled"
        STOCKTAKE_ENABLED = "stocktake_enabled"
        STOCKTAKE_NEW_ITEMS_OPT_IN = "stocktake_new_items_opt_in"
        AUTO_DRAIN_PAST_MEALS = "auto_drain_past_meals"
        AUTO_ADD_MODE = "auto_add_mode"
        HOUSEHOLD_HEADCOUNT = "household_headcount"
        BATCH_FEATURES_ENABLED = "batch_features_enabled"
        BUDGET_AMOUNT = "budget_amount"
        BUDGET_PERIOD = "budget_period"
        SMTP_HOST = "smtp_host"
        SMTP_PORT = "smtp_port"
        SMTP_USERNAME = "smtp_username"
        SMTP_PASSWORD_ENCRYPTED = "smtp_password_encrypted"
        SMTP_FROM = "smtp_from"
        SMTP_USE_TLS = "smtp_use_tls"
        VAPID_PUBLIC_KEY = "vapid_public_key"
        VAPID_PRIVATE_KEY_ENCRYPTED = "vapid_private_key_encrypted"
        VAPID_SUBJECT = "vapid_subject"
        PIPER_BIN = "piper_bin"
        PIPER_BUNDLED_VOICE_DIR = "piper_bundled_voice_dir"
        EMAIL_ENABLED = "email_enabled"
        AUDIT_RETENTION_DAYS = "audit_retention_days"
        PUBLIC_URL = "public_url"
