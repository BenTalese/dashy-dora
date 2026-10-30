"""Structural pins on the deployment files (finalisation 19-R1 / 19-R2).

Same spirit as `test_compose_env_coverage`: cheap, no runtime, and each one
re-checks in seconds something that only ever showed up on a deployed box.

* The Docker image must build the SPA through `npm run build` — the one place
  the build mode (`quasar build -m pwa`) lives. A bare `quasar build` is SPA
  mode: the image shipped for months without the service worker, manifest,
  install prompt or offline cache FU-336 added, because the mode flip never
  reached the Dockerfile.
* `.dockerignore` must exclude the frontend's own `.env`. README step 1 tells
  the operator to create it with `VITE_API_BASE_URL=http://localhost:5170/api`
  for `quasar dev`; copied into the image it is baked into the SPA bundle and
  every other device then calls the wrong host.
"""
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (_REPO_ROOT / name).read_text(encoding="utf-8")


def _uncommented(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def test__dockerfile__builds_the_spa_through_npm_run_build_in_pwa_mode():
    dockerfile = _read("Dockerfile")
    package_json = _read("web_app/package.json")

    assert re.search(r'"build":\s*"quasar build -m pwa"', package_json), (
        "web_app/package.json `build` is no longer `quasar build -m pwa`; FU-336 regressed"
    )
    live = "\n".join(_uncommented(dockerfile))
    assert "npm run build" in live, "Dockerfile must build the SPA via `npm run build`"
    assert not re.search(r"^\s*RUN\s+quasar build\b", live, re.M), (
        "Dockerfile calls `quasar build` directly — that is SPA mode, no service worker"
    )
    # And the image refuses to build without the PWA artefacts.
    assert "dist/spa/sw.js" in live and "dist/spa/manifest.json" in live


def test__dockerignore__excludes_the_frontend_env_but_keeps_its_example():
    lines = _uncommented(_read(".dockerignore"))
    assert "web_app/.env" in lines
    assert "web_app/.env.*" in lines
    assert "!web_app/.env.example" in lines


def test__spa_package_version__matches_current_version():
    """FU-861 — the SPA bundle takes its version from `version_info.py` at
    build time; package.json's own field must not tell a different story."""
    import json
    from pathlib import Path

    from dora_api.features.help.version_info import CURRENT_VERSION

    root = Path(__file__).resolve().parents[1]
    package = json.loads((root / "web_app" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == CURRENT_VERSION
