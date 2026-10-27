"""The SPA's substitution table is generated from the server module
(R-003, finalisation 11-R12); this pins the committed file is current.

Regenerate with: python scripts/dump_substitutes.py
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED = REPO_ROOT / "web_app" / "src" / "generated" / "substitutes_table.ts"


def test__substitutes_table_generated_is_current():
    spec = importlib.util.spec_from_file_location(
        "dump_substitutes", REPO_ROOT / "scripts" / "dump_substitutes.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("dump_substitutes", module)
    spec.loader.exec_module(module)
    committed = GENERATED.read_text(encoding="utf-8")
    assert committed.replace("\r\n", "\n") == module.render().replace("\r\n", "\n"), (
        "web_app/src/generated/substitutes_table.ts is stale — run `python scripts/dump_substitutes.py`"
    )
