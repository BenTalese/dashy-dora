"""The SPA's recipe closed vocabularies are generated from the server module
(R-003 / R-089, finalisation 01-R42); this pins the committed file is current.

Regenerate with: python scripts/dump_recipe_vocabulary.py
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED = REPO_ROOT / "web_app" / "src" / "generated" / "recipe_vocabulary.ts"


def test__recipe_vocabulary_generated_is_current():
    spec = importlib.util.spec_from_file_location(
        "dump_recipe_vocabulary", REPO_ROOT / "scripts" / "dump_recipe_vocabulary.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("dump_recipe_vocabulary", module)
    spec.loader.exec_module(module)
    committed = GENERATED.read_text(encoding="utf-8")
    assert committed.replace("\r\n", "\n") == module.render().replace("\r\n", "\n"), (
        "web_app/src/generated/recipe_vocabulary.ts is stale — run `python scripts/dump_recipe_vocabulary.py`"
    )
