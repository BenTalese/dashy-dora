"""GET /api/auth/capabilities — pre-auth capability probe.

Small unauthenticated surface the SPA reads to decide whether to render
optional entry points on the auth screens: whether outbound email is going
somewhere, and the install's password minimum. Add more as public-facing
capabilities appear.

Why this exists: the reset-password flow always runs (204 on request,
dry-run logs the link when SMTP is unset) so anti-enumeration holds even
on installs with no email configured. But a regular user can't read the
server log, so the "Forgot password?" link is a dead end for them on a
fresh install. Gating it on this flag closes that gap.
"""
from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.features.auth.setup_demo import is_setup_demo_active, is_setup_demo_available
from dora_api.features.desktop.quit_desktop import can_quit
from dora_api.features.routers import AUTH_ROUTER
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.auth_helpers import MIN_PASSWORD_LENGTH, can_mail_links
from dora_api.infrastructure.configuration_manager import DORA_CONFIG
from dora_api.infrastructure.email_sender import email_sender_configured


@AUTH_ROUTER.route("/capabilities", methods=["GET"])
def get_auth_capabilities():
    return ok({
        # "Can a reset / verify mail reach anyone?" — which also needs a
        # public URL on a production install, since the link is the whole
        # point of the mail and is never built from request headers (SEC-2).
        "email_sender_configured": email_sender_configured() and can_mail_links(),
        # Demo / sellable-showcase mode (FU-392). Lets the SPA render the
        # persistent "you're in a demo, it resets periodically" banner and
        # pre-fill the demo login hint without an authenticated call.
        "demo_mode": DORA_CONFIG.is_demo_mode_enabled(),
        # The first-setup demo (setup_demo.py): the banner offers "Set up
        # Dora" back to the one-time setup while it's on.
        "setup_demo": is_setup_demo_active(),
        # Whether /setup may offer "Look around a demo first" (no users, and
        # not locked to ADMIN_BOOTSTRAP_EMAIL).
        "setup_demo_available": is_setup_demo_available(),
        # SEC-3 — whether the login page offers "Create account".
        "registration_enabled": bool(
            get_or_create_app_setting(SqlAlchemyRepository()).registration_enabled
        ),
        # FU-656: the length rule, so a form can hint it before the save
        # without restating the number (validate_password stays the authority).
        "min_password_length": MIN_PASSWORD_LENGTH,
        # Running as the desktop app: About offers Quit Dora.
        "desktop": can_quit(),
    })
