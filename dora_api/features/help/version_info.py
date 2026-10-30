"""Single source of truth for the current Dashy Dora version.

Kept in code (rather than reading from setup.py / pyproject.toml) so the
runtime doesn't need to import build tooling at request time, and so the
Dora assistant can return the version with zero I/O.

Bump when you cut a release. The frontend changelog page expects each
released version to have a matching `## [VERSION]` heading in CHANGELOG.md
at the repo root.

This file is also the SPA's version source (FU-861): `web_app/quasar.config.ts`
reads `CURRENT_VERSION` from it at build time, so the bundle and the API can't
name different versions. Keep the assignment a plain string literal.
"""
import os

CURRENT_VERSION = "0.7.0"


def build_id() -> str | None:
    """The exact artifact: `DORA_BUILD_ID` (a git short sha, stamped by the
    image build or a packaging script), or None for a source checkout. The SPA
    bundle carries its own copy so About can tell when the two differ."""
    return os.environ.get("DORA_BUILD_ID", "").strip() or None

# The GitHub repository, as `owner/name`. One place (R-003): the Help page's
# update check, the "Report an issue" default and the dataset-import
# User-Agent all build their URLs from it. The repository was renamed from
# `DiscountDora` with the product; three call sites were carrying three
# different spellings, one of which (`DashyDora`) never existed, so the update
# check 404'd on every install (finalisation 19-R3).
GITHUB_REPO = "BenTalese/dashy-dora"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
