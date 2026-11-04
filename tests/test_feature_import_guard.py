"""FU-977 (5): a broken feature package or module is named in the operator-facing
"failed to import" line, whether it's a sub-package or a plain module."""
import logging
import sys

import pytest

from dora_api.infrastructure.utils import import_feature_modules


def _make_package(tmp_path, name: str, files: dict[str, str]) -> None:
    root = tmp_path / name
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


@pytest.mark.parametrize(
    "files, broken",
    [
        # A sub-package whose __init__ raises (walk_packages' onerror path).
        ({"__init__.py": "", "bad/__init__.py": "raise RuntimeError('boom')"}, "bad"),
        # A plain module that raises (the import_module path).
        ({"__init__.py": "", "good/__init__.py": "", "good/mod.py": "import no_such_module_xyz"}, "good.mod"),
    ],
)
def test__broken_feature__is_named_in_the_guard_line(tmp_path, monkeypatch, caplog, files, broken):
    pkg = f"fu977_pkg_{broken.replace('.', '_')}"
    _make_package(tmp_path, pkg, files)
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(Exception):
            import_feature_modules(pkg)
        assert f"Feature package {pkg}.{broken} failed to import" in caplog.text
    finally:
        for mod in [m for m in sys.modules if m.startswith(pkg)]:
            del sys.modules[mod]
