"""Regenerate ``web_app/src/generated/recipe_vocabulary.ts`` from the Python
source of truth at ``dora_api/domain/entities/recipe.py`` (R-003 / R-089).

Run from repo root: ``python scripts/dump_recipe_vocabulary.py``

The output file is checked in; ``tests/test_recipe_vocabulary_generated.py``
fails when it is stale.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dora_api.domain.entities import recipe  # noqa: E402

HEADER = """// THIS FILE IS GENERATED — DO NOT EDIT BY HAND.
// Source of truth: dora_api/domain/entities/recipe.py
// Regenerate via: python scripts/dump_recipe_vocabulary.py
//
// The recipe closed vocabularies the server validates (R-010), so the
// pickers and filters offer exactly what a write accepts.
"""


def _tuple(name: str, values: tuple[str, ...], type_name: str) -> str:
    items = ", ".join(json.dumps(v) for v in values)
    return (
        f"export const {name} = [{items}] as const;\n"
        f"export type {type_name} = (typeof {name})[number];\n"
    )


def render() -> str:
    return "\n".join([
        HEADER,
        _tuple("DIFFICULTY_VALUES", recipe.ALLOWED_DIFFICULTY_VALUES, "Difficulty"),
        _tuple("STEPS_MODES", recipe.ALLOWED_STEPS_MODES, "RecipeStepsMode"),
        _tuple("DEFAULT_MEAL_SLOTS", recipe.DEFAULT_MEAL_SLOTS, "MealSlot"),
    ])


def main() -> int:
    target = REPO_ROOT / "web_app" / "src" / "generated" / "recipe_vocabulary.ts"
    target.write_text(render(), encoding="utf-8")
    print(f"wrote {target.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
