"""Regenerate ``web_app/src/generated/substitutes_table.ts`` from the Python
source of truth at ``dora_api/domain/substitutes.py`` (R-003).

Run from repo root: ``python scripts/dump_substitutes.py``

The output file is checked in; ``tests/test_substitutes_table_generated.py``
fails when it is stale.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dora_api.domain import substitutes  # noqa: E402

HEADER = """// THIS FILE IS GENERATED — DO NOT EDIT BY HAND.
// Source of truth: dora_api/domain/substitutes.py
// Regenerate via: python scripts/dump_substitutes.py
//
// The curated substitution table, for Basic mode's offline answer.
"""


def render() -> str:
    table = json.dumps(substitutes.SUBSTITUTES, indent=4, ensure_ascii=False)
    aliases = json.dumps(substitutes.SUBSTITUTE_ALIASES, indent=4, ensure_ascii=False)
    return "\n".join([
        HEADER,
        f"export const SUBSTITUTES: Readonly<Record<string, readonly string[]>> = {table};\n",
        f"export const SUBSTITUTE_ALIASES: Readonly<Record<string, string>> = {aliases};\n",
    ])


def main() -> int:
    target = REPO_ROOT / "web_app" / "src" / "generated" / "substitutes_table.ts"
    target.write_text(render(), encoding="utf-8")
    print(f"wrote {target.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
