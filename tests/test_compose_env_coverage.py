"""Every env var the app reads must be accounted for in `compose.yml`.

Why this exists
---------------
`compose.yml`'s `environment:` block is an explicit allow-list. A var an
operator sets in `.env` that isn't named there never reaches the
container, and nothing complains — the app just behaves as though it were
unset. That's not hypothetical: `DORA_SECRET_ENCRYPTION_KEY` was missing
from the block for months (found 2026-08-17), so operators who set the
key correctly still got "Secret encryption isn't set up on this install",
and the whole encrypted-secrets surface was dead in the container. The
same audit found `DORA_SMTP_USER` in compose against `DORA_SMTP_USERNAME`
in the code — a silent one-word mismatch nothing would ever have caught.

`env_file:` now forwards the operator's whole `.env`, which fixes the
class of bug at runtime. This test guards the *documentation* half: it
fails when a new env var appears in the code and nobody decided whether
an operator is meant to set it. Every name must be either

  * present in the `environment:` block, or
  * listed in `INTENTIONALLY_OMITTED` below with a reason.

Adding a name to the omit-list is a fine outcome — the point is that the
decision is made once, in writing, rather than forgotten.

R-034-style structural pin: cheap, no runtime, and it re-checks by hand
in seconds something that takes half an hour to audit manually.
"""
import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_COMPOSE = _REPO_ROOT / "compose.yml"

# Files that read process environment. `dora_api/**` is the app;
# gunicorn.conf.py + startup.sh configure the server process itself.
_SCAN_DIRS = ("dora_api",)
_SCAN_FILES = ("gunicorn.conf.py", "startup.sh", "Dockerfile")

# A bare string literal that looks like one of our env var names. This is
# deliberately broader than matching `os.environ.get("X")` call sites:
# `secret_encryption.py` reads its var through a module constant
# (`_ENV_VAR = "DORA_SECRET_ENCRYPTION_KEY"`), so a call-site-only scanner
# misses precisely the variable that caused the original bug.
_NAME_IN_PY = re.compile(r"""["']((?:DORA|ADMIN)_[A-Z][A-Z0-9_]*)["']""")
# Shell / Dockerfile: `${DORA_FOO}`, `$DORA_FOO`, `ENV DORA_FOO=`.
_NAME_IN_SH = re.compile(r"\$\{?((?:DORA|ADMIN)_[A-Z][A-Z0-9_]*)\}?|^\s*ENV\s+((?:DORA|ADMIN)_[A-Z][A-Z0-9_]*)", re.M)

# Names that appear as literals but are NOT environment variables.
_NOT_ENV_VARS = frozenset({
    # Doc/log strings naming the *other* halves of a settings group, and
    # historical names kept only in prose.
    "DORA_LLM_KEY_ENCRYPTION_KEY",   # pre-2026-08-04 name of DORA_SECRET_ENCRYPTION_KEY; never read
    "DORA_VAPID_PRIVATE_KEY",        # named in comments only; the key is an AppSetting secret
    # startup.sh shell locals (lower-cased copies used for comparisons),
    # not process environment the operator ever sets.
    "DORA_ENV_LC",
    "DORA_API_SERVER_LC",
})

# Read by the code, deliberately absent from the `environment:` block.
# Keep the reason with the name — this list is the record of the decision.
INTENTIONALLY_OMITTED: dict[str, str] = {
    # ── Escape hatches that weaken the install ───────────────────────
    "DORA_CSRF_DISABLED":
        "dev-only CSRF bypass; refused in production. Naming it in compose "
        "invites setting it to get past a boot failure.",
    "DORA_DISABLE_SECURITY_HEADERS":
        "dev-only; same reasoning as DORA_CSRF_DISABLED.",
    "DORA_SKIP_PROD_VALIDATION":
        "skips the production-requirements check that refuses to boot "
        "without a secret key / CORS origins. Never advertise it.",

    # ── Dev-seed controls ────────────────────────────────────────────
    "DORA_SEED_BULK_ITEMS": "dev seed only; production refuses to seed.",
    "DORA_SEED_QA_FIXTURES": "dev/e2e seed only.",
    "DORA_SEED_MONEY_ON": "dev seed only (dora-verify-backend-money profile).",
    "DORA_SEED_DATASET":
        "dev seed only — picks the dense or bulk dev dataset. Production "
        "refuses to seed at all, so forwarding it would advertise a knob "
        "that can never do anything there.",

    # ── Container-internal; the Dockerfile owns these ────────────────
    "DORA_API_HOST": "bind address inside the container; fixed by the image.",
    "DORA_BIND": "gunicorn bind string; derived by startup.sh.",
    "DORA_SPA_DIR": "path to the built SPA inside the image.",
    "DORA_GUNICORN_LOG_LEVEL": "derived from DORA_LOG_LEVEL by gunicorn.conf.py.",
    "DORA_WEB_KEEPALIVE": "gunicorn tuning with a sane default; override via .env if ever needed.",
    "DORA_WEB_GRACEFUL_TIMEOUT": "as above.",

    # ── Promoted to AppSetting; env survives only inside migration
    #    b7d2f9c1e4a3, which read it once at upgrade time. No runtime
    #    fallback — forwarding these would advertise a setting that does
    #    nothing. Edited under Settings → Admin instead.
    #    (IMPL_PLAN_ENV_TO_APPSETTING / FU-333.)
    "DORA_SMTP_HOST": "migration-only; SMTP lives on AppSetting.",
    "DORA_SMTP_PORT": "migration-only; SMTP lives on AppSetting.",
    "DORA_SMTP_USERNAME": "migration-only; SMTP lives on AppSetting.",
    "DORA_SMTP_USE_TLS": "migration-only; SMTP lives on AppSetting.",
    "DORA_SMTP_FROM": "migration-only; SMTP lives on AppSetting.",
    "DORA_EMAIL_ENABLED": "migration-only; AppSetting.email_enabled.",
    "DORA_PUBLIC_URL": "migration-only; AppSetting.public_url.",
    "DORA_AUDIT_RETENTION_DAYS": "migration-only; AppSetting.audit_retention_days.",
    "DORA_VAPID_PUBLIC_KEY": "migration-only; push keys live on AppSetting.",
    "DORA_VAPID_SUBJECT": "migration-only; push keys live on AppSetting.",
    "DORA_PIPER_BIN": "migration-only; TTS paths live on AppSetting.",
    "DORA_PIPER_BUNDLED_VOICE_DIR": "migration-only; TTS paths live on AppSetting.",
}


def _iter_source_files():
    for d in _SCAN_DIRS:
        for path in (_REPO_ROOT / d).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path
    for name in _SCAN_FILES:
        path = _REPO_ROOT / name
        if path.exists():
            yield path


def _names_read_by_the_app() -> set[str]:
    found: set[str] = set()
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".py":
            found.update(_NAME_IN_PY.findall(text))
        else:
            for a, b in _NAME_IN_SH.findall(text):
                found.add(a or b)
    return {n for n in found if n and n not in _NOT_ENV_VARS}


def _names_declared_in_compose() -> set[str]:
    text = _COMPOSE.read_text(encoding="utf-8")
    # `- NAME=...` entries in the environment block. Comment lines start
    # with `#` after the indent, so they're excluded by the `- ` anchor.
    return set(re.findall(r"^\s*-\s+([A-Z][A-Z0-9_]*)=", text, re.M))


def test__compose_forwards_every_env_var_the_app_reads():
    read = _names_read_by_the_app()
    declared = _names_declared_in_compose()
    omitted = set(INTENTIONALLY_OMITTED)

    undecided = sorted(read - declared - omitted)
    assert not undecided, (
        "These env vars are read by the app but neither forwarded in "
        "compose.yml's `environment:` block nor listed in "
        "INTENTIONALLY_OMITTED:\n  "
        + "\n  ".join(undecided)
        + "\n\nAdd each to compose.yml (operators are meant to set it) or to "
          "INTENTIONALLY_OMITTED with a reason (they aren't)."
    )


def test__compose_declares_nothing_the_app_never_reads():
    """The mirror check — a var in compose that nothing reads is either a
    typo (`DORA_SMTP_USER` for `DORA_SMTP_USERNAME`) or dead weight that
    misleads the next operator reading the file."""
    read = _names_read_by_the_app()
    declared = _names_declared_in_compose()
    # PUID/PGID/TZ are consumed by the base image's init, not our code.
    infra = {"PUID", "PGID", "TZ"}

    orphans = sorted(declared - read - infra)
    assert not orphans, (
        "compose.yml forwards env vars nothing in the codebase reads:\n  "
        + "\n  ".join(orphans)
        + "\n\nEither the name is misspelled, or the setting was removed and "
          "the compose entry wasn't."
    )


@pytest.mark.parametrize("name", sorted(INTENTIONALLY_OMITTED))
def test__omitted_names_are_still_read_somewhere(name: str):
    """Stops the omit-list rotting into a list of names that no longer
    exist, which would quietly stop guarding anything."""
    assert name in _names_read_by_the_app(), (
        f"{name} is on INTENTIONALLY_OMITTED but nothing reads it any more. "
        "Drop the entry."
    )
