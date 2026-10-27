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
from dora_api.features.routers import AUTH_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.infrastructure.configuration_manager import DORA_CONFIG
from dora_api.infrastructure.email_sender import email_sender_configured


@AUTH_ROUTER.route("/capabilities", methods=["GET"])
def get_auth_capabilities():
    return ok({
        "email_sender_configured": email_sender_configured(),
        # Demo / sellable-showcase mode (FU-392). Lets the SPA render the
        # persistent "you're in a demo, it resets periodically" banner and
        # pre-fill the demo login hint without an authenticated call.
        "demo_mode": DORA_CONFIG.is_demo_mode_enabled(),
    })
