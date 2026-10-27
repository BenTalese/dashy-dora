"""GET /api/help/changelog — returns parsed changelog entries.

Reads CHANGELOG.md at the repo root and splits it into per-version blocks.
The frontend renders these as collapsed cards; the most recent ("Unreleased"
+ the top released version) are expanded by default.
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dora_api.features.routers import HELP_ROUTER
from dora_api.infrastructure.api_response import ok

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ChangelogEntry:
    version: str
    date: str | None
    body: str  # markdown text under the heading


@dataclass(frozen=True, slots=True)
class ChangelogDto:
    entries: List[ChangelogEntry] = field(default_factory=list)


_VERSION_HEADING_RE = re.compile(
    # `## [0.6.0] - 2026-05-20` or `## 0.6.0` or `## [Unreleased]`
    r"^##\s+\[?(?P<version>[^\]\s]+)\]?(?:\s*-\s*(?P<date>\S+))?\s*$",
    re.MULTILINE,
)


def _changelog_path() -> Path:
    # `Path()` here = the CWD the API was launched from, which by convention
    # is the repo root (matches how migrations/logs find their relatives).
    return Path() / "CHANGELOG.md"


def parse_changelog(text: str) -> List[ChangelogEntry]:
    entries: List[ChangelogEntry] = []
    matches = list(_VERSION_HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip("\n")
        entries.append(ChangelogEntry(
            version = match.group("version"),
            date = match.group("date"),
            body = body,
        ))
    return entries


@HELP_ROUTER.route("/changelog", methods=["GET"])
def get_changelog():
    path = _changelog_path()
    if not path.exists():
        _LOGGER.info("CHANGELOG.md not found at %s — returning empty list.", path)
        return ok(ChangelogDto(entries=[]))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _LOGGER.warning("Failed to read changelog: %s", exc)
        return ok(ChangelogDto(entries=[]))
    return ok(ChangelogDto(entries=parse_changelog(text)))
