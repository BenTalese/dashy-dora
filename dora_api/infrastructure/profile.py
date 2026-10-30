"""D3 — runtime profile (`development` / `production` / `test`).

Lives in dora_api's infrastructure package and is imported by both
service config managers so the profile concept stays single-source.
Profile is read once at module load via DORA_ENV; tests override by
setting the env var before importing.

The profile drives:
  - default log level
  - default debug flag
  - whether dev seed data may run
  - default CORS origins (open localhost set vs. required pinned list)
  - which "required env vars" must be present before boot

See `validate_production_requirements()` for the boot-time gate.
"""
import os
import sys
from enum import Enum
from typing import Sequence


class Profile(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


_ALIASES = {
    "dev": Profile.DEVELOPMENT,
    "development": Profile.DEVELOPMENT,
    "local": Profile.DEVELOPMENT,
    "prod": Profile.PRODUCTION,
    "production": Profile.PRODUCTION,
    "test": Profile.TEST,
    "testing": Profile.TEST,
    "ci": Profile.TEST,
}


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean env var. Empty / unset → `default`; otherwise true for
    `1`, `true`, `yes`, `on` (any case). The one truthy parser — it used to be
    written out eight times across the config, profile and middleware modules
    (finalisation 19-R10, R-003)."""
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in _TRUTHY


def current_profile() -> Profile:
    """Read DORA_ENV once per call. Cheap; we don't cache so tests
    that mutate the env var mid-run still see fresh values."""
    raw = (os.environ.get("DORA_ENV") or "").strip().lower()
    if not raw:
        return Profile.DEVELOPMENT
    return _ALIASES.get(raw, Profile.DEVELOPMENT)


def is_production() -> bool:
    return current_profile() is Profile.PRODUCTION


def is_test() -> bool:
    return current_profile() is Profile.TEST


# Required env vars per profile. Production demands a hard set;
# development asks for nothing. Test runs are gated by pytest's own
# fixtures so we don't require anything here.
PRODUCTION_REQUIRED_VARS: tuple[str, ...] = (
    # Signs session cookies. Without this every restart invalidates
    # every session AND the cookie is signable by anyone with the
    # source.
    "DORA_SECRET_KEY",
    # Pinned CORS origins (comma-separated). Without this the SPA
    # can't talk to the API from a real domain — production should
    # never fall back to the localhost defaults.
    "DORA_CORS_ORIGINS",
    # First admin account is bootstrapped against this email; without
    # it the first random visitor to /register becomes admin, which
    # is fine for dev but not for a public deploy.
    "ADMIN_BOOTSTRAP_EMAIL",
)


_BANNER_RULE = "═" * 63


def _print_banner(title: list[str], body: list[str]) -> None:
    """Boxed stderr notice shared by the boot-time gate and the insecure-
    cookie warning (finalisation 19-R11). stderr so container runtimes
    capture it even before the logger is wired up."""
    lines = ["", _BANNER_RULE, *title, _BANNER_RULE, "", *body, _BANNER_RULE, ""]
    print("\n".join(lines), file=sys.stderr, flush=True)


def validate_production_requirements(extra: Sequence[str] = ()) -> None:
    """Refuse to boot when in production and any required env var is
    missing. Prints a friendly multi-line error listing every missing
    var, then exits.

    `extra` lets a caller add deployment-specific requirements without
    touching the shared list (SMTP, push and AI keys live in Settings, not
    env — see `IMPL_PLAN_ENV_TO_APPSETTING.md`).

    Bypassed when DORA_SKIP_PROD_VALIDATION=true — the desktop bundle
    sets this because its required-vars story is different (no public
    CORS host, no bootstrap admin email, SECRET_KEY is auto-generated
    to the user-data dir). Never set this in a server deployment.
    """
    if not is_production():
        return
    if env_flag("DORA_SKIP_PROD_VALIDATION"):
        return

    required = list(PRODUCTION_REQUIRED_VARS) + list(extra)
    missing = [name for name in required if not (os.environ.get(name) or "").strip()]
    if missing:
        body = [" Missing:"]
        body += [f"   - {name}" for name in missing]
        body += [
            "",
            " Fix:  add the missing vars to your .env (or the deploy",
            " environment) and restart. See .env.example for what each",
            " var does.",
            "",
            " To run in dev mode instead, set DORA_ENV=development.",
        ]
        _print_banner(
            [" DORA_ENV=production but required environment variables are",
             " missing. Refusing to start."],
            body,
        )
        # Exit non-zero so compose marks the container as failed.
        sys.exit(1)

    # CORS runs with credentials enabled, so a wildcard origin would let any
    # website make authenticated calls with a signed-in user's cookie.
    cors_origins = [
        origin.strip()
        for origin in (os.environ.get("DORA_CORS_ORIGINS") or "").split(",")
    ]
    if "*" in cors_origins:
        _print_banner(
            [" DORA_ENV=production but DORA_CORS_ORIGINS contains \"*\".",
             " Refusing to start."],
            [" Credentialed CORS with a wildcard origin lets any website act",
             " as a signed-in user. List the exact origin(s) the SPA is",
             " served from instead, e.g.",
             "   DORA_CORS_ORIGINS=https://dora.example.com"],
        )
        sys.exit(1)


def warn_if_insecure_cookies_in_production() -> None:
    """Loud stderr warning (not a hard refusal) when `DORA_ENV=production`
    and the operator has **explicitly** turned Secure cookies off via
    `DORA_SECURE_COOKIES=false`. The default in production is now
    `SESSION_COOKIE_SECURE=True` (see `app.py`) so this warning only
    fires on a deliberate opt-out — meant to make the choice audible
    at boot ("you're serving prod without Secure cookies — sure?") for
    the LAN-behind-VPN / no-cert home-lab case.

    Escape hatch: `DORA_SKIP_PROD_VALIDATION=true` silences the warning
    regardless — same override as `validate_production_requirements`.
    """
    if not is_production():
        return
    if env_flag("DORA_SKIP_PROD_VALIDATION"):
        return
    raw = (os.environ.get("DORA_SECURE_COOKIES") or "").strip().lower()
    if raw not in {"0", "false", "no", "off"}:
        return

    _print_banner(
        [" WARNING: DORA_ENV=production and DORA_SECURE_COOKIES=false."],
        [
            " The session cookie will NOT carry the `Secure` attribute, so",
            " a browser will send it over plain HTTP too. If this install",
            " is fronted by HTTPS (Let's Encrypt, Cloudflare, load-balancer",
            " TLS termination, etc.) unset DORA_SECURE_COOKIES (or set it",
            " to `true`) so the safe default takes over.",
            "",
            " If you deliberately serve the app over plain HTTP (internal",
            " LAN behind a VPN, home-lab install with no cert) keep the",
            " current setting; this warning is your one audible reminder.",
        ],
    )
