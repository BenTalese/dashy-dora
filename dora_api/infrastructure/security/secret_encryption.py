"""Data-at-rest encryption for every secret Dora stores in the DB.

Dora persists several secrets to the database — SMTP password, VAPID
private key, per-user paid-provider LLM API keys — and wraps them all
with a single Fernet key so a DB dump (or backup theft) doesn't leak
plaintext. That wrapping key is Dora's KEK (key-encryption-key); it
lives in the environment variable ``DORA_SECRET_ENCRYPTION_KEY`` and
must never be stored in the DB itself (a backup containing both the
ciphertext and the key that decrypts it defeats the point).

Operators set it once at boot (env file, systemd EnvironmentFile,
k8s secret, docker/compose env) — same shape as every other secret
the app needs (R-005 distribution posture: env-driven config). If the
variable is unset, :func:`encrypt` and :func:`decrypt` raise
:class:`EncryptionUnavailable` so callers can surface a friendly error
("secret encryption isn't configured for this install — set
DORA_SECRET_ENCRYPTION_KEY") instead of crashing. Ollama-only installs
that never save a paid-provider LLM key, an SMTP password, or Web-Push
keys can leave the variable unset; it's only required to *save* a
secret.

Why an env var, not a generated file:

- Matches every other secret the app needs (no special case).
- Postgres-friendly: the API server can be stateless (FU-045) and
  every replica reads the same key from its env.
- Operators get an explicit "I made a choice" signal — auto-generating
  a key file on first boot is convenient but hides the security model
  from the operator who'll eventually rotate the key.

Key generation (for ops docs):

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

The returned string is a 32-byte url-safe-base64 value; that's what
goes into the env var verbatim.

History: this module lived at ``infrastructure/llm/key_encryption.py``
and its env var was named ``DORA_LLM_KEY_ENCRYPTION_KEY`` because it
was introduced (FU-153) purely for LLM API keys. It was later reused
for SMTP + VAPID secrets without renaming, which misled operators who
didn't use LLMs into thinking the gating didn't apply to them. Renamed
2026-08-04.
"""
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


_ENV_VAR = "DORA_SECRET_ENCRYPTION_KEY"
_LOGGER = logging.getLogger(__name__)


class EncryptionUnavailable(Exception):
    """Raised when the encryption key isn't configured for this install.

    Callers should translate this to a user-friendly 422 ("secret
    encryption isn't configured for this install — see operator docs")
    rather than a 500.
    """


class EncryptionFailed(Exception):
    """Raised when ciphertext can't be decoded (key rotated, blob
    corrupted). Treated by callers as "the saved secret is no longer
    usable — ask the user to re-enter it"."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet | None:
    raw = os.environ.get(_ENV_VAR, "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode("ascii"))
    except (ValueError, TypeError) as exc:
        # Bad key format (must be 32-byte url-safe-base64). Log the
        # operator-facing detail; treat as "no key configured" so
        # callers fail-fast rather than papering over a misconfig.
        _LOGGER.error(
            "%s is set but invalid (%s). Generate a fresh key with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'`.",
            _ENV_VAR, exc,
        )
        return None


def encryption_available() -> bool:
    """Returns True iff the encryption key is configured AND parses.

    Settings pages read this via the master-flag endpoint so the Save
    button on secret-bearing fields can show a clear "encryption isn't
    configured — ask your admin to set DORA_SECRET_ENCRYPTION_KEY"
    state, instead of failing only at save time.
    """
    return _fernet() is not None


def encrypt(plaintext: str) -> bytes:
    """Encrypt a UTF-8 plaintext secret. Raises EncryptionUnavailable
    when the env key is unset/invalid."""
    f = _fernet()
    if f is None:
        raise EncryptionUnavailable(
            f"{_ENV_VAR} isn't configured, so secrets can't be saved."
        )
    return f.encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decrypt a previously-encrypted blob. Raises EncryptionUnavailable
    when the env key is unset/invalid; raises EncryptionFailed when the
    blob can't be decoded with the current key (rotated / corrupted)."""
    f = _fernet()
    if f is None:
        raise EncryptionUnavailable(
            f"{_ENV_VAR} isn't configured, so saved secrets can't be decrypted."
        )
    try:
        return f.decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionFailed(
            "Saved secret couldn't be decrypted. The encryption key "
            "may have been rotated. Re-enter the value in Settings."
        ) from exc
