"""FU-519 tail — e2e for the /api/help router.

Two read-only endpoints behind the Help panel (the changelog endpoint went
with the What's new page, 2026-11-04):

  - GET /help/version    — current version + best-effort GitHub update check
    (network failure degrades to `latest_version: null` + `error`, never 5xx),
  - GET /help/food-fact  — random pick from the curated local list (shape +
    membership only; the pick is deliberately non-deterministic).

Both require an authenticated session (they're not in
PUBLIC_ENDPOINTS) — pinned via a fresh anonymous client.
"""
import requests

from dora_api.features.help.get_food_fact import FOOD_FACTS
from dora_api.features.help.version_info import CURRENT_VERSION
from tests.support import assert_problem

BASE = "http://localhost:5170/api"
HELP = f"{BASE}/help"

VERSION_KEYS = {
    "current_version", "latest_version", "update_available", "release_url", "error",
    "update_check_enabled",
}


#region ---------------- version ----------------


def test__version_check__repo_slug_is_the_one_constant():
    """Finalisation 19-R3 — the update check pointed at `BenTalese/DashyDora`
    (never existed) while the support channel and README said `dashy-dora`.
    Every URL that names the repository now reads `version_info.GITHUB_REPO`."""
    from dora_api.features.help import get_version
    from dora_api.features.help.version_info import GITHUB_REPO, GITHUB_URL
    from dora_api.features.nutrition.dataset_import import _USER_AGENT
    from dora_api.features.support.support_channel import _DEFAULT_SUPPORT_URL

    assert GITHUB_REPO == "BenTalese/dashy-dora"
    assert get_version._GITHUB_RELEASE_URL == f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    assert _DEFAULT_SUPPORT_URL.startswith(GITHUB_URL)
    assert GITHUB_URL in _USER_AGENT
    for stale in ("DashyDora/", "DiscountDora"):
        assert stale not in get_version._GITHUB_RELEASE_URL
        assert stale not in _DEFAULT_SUPPORT_URL
        assert stale not in _USER_AGENT


def test__version_check__is_newer_orders_pre_releases_correctly():
    """The hand-rolled tuple parse this replaces read `0.8.0-rc.1` as
    `(0, 8, 0, 1)` — newer than the final `0.8.0`. PEP 440 ordering now."""
    from dora_api.features.help.get_version import _is_newer

    assert _is_newer("0.8.0", "0.7.0") is True
    assert _is_newer("0.10.0", "0.9.0") is True
    assert _is_newer("0.7.0", "0.7.0") is False
    assert _is_newer("0.8.0-rc.1", "0.7.0") is True
    assert _is_newer("0.8.0-rc.1", "0.8.0") is False
    assert _is_newer("not-a-version", "0.7.0") is False


def test__get_version__Shape__MatchesContractAndCurrentVersion(api):
    resp = requests.get(f"{HELP}/version")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == VERSION_KEYS
    assert body["current_version"] == CURRENT_VERSION
    assert isinstance(body["update_available"], bool)
    # The GitHub lookup is best-effort: either we got a tag, or we got an
    # error string and no update claim. Never both empty-and-claiming.
    if body["latest_version"] is None:
        assert body["update_available"] is False
    else:
        assert isinstance(body["latest_version"], str)
    if body["error"] is not None:
        assert body["latest_version"] is None
        assert body["update_available"] is False


def test__get_version__CheckSwitchedOff__NeverCallsGitHub(api, monkeypatch):
    """FU-626: `DORA_UPDATE_CHECK=false` keeps an install from reaching out."""
    from dora_api.features.help import get_version

    def _boom():
        raise AssertionError("GitHub was called with the update check off")

    monkeypatch.setenv("DORA_UPDATE_CHECK", "false")
    monkeypatch.setattr(get_version, "_fetch_latest_release", _boom)
    body = requests.get(f"{HELP}/version").json()

    assert body["update_check_enabled"] is False
    assert body["latest_version"] is None
    assert body["update_available"] is False
    assert body["current_version"] == CURRENT_VERSION


#endregion version

#region ---------------- food fact ----------------


def test__get_food_fact__ReturnsOneCuratedFact(api):
    resp = requests.get(f"{HELP}/food-fact")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"fact"}
    # Random pick — assert membership in the curated list, not a value.
    assert body["fact"] in FOOD_FACTS


#endregion food fact

#region ---------------- auth posture ----------------


def test__help_endpoints__Anonymous__401(api):
    anon = requests.Session()
    for path in ("version", "food-fact"):
        assert_problem(anon.get(f"{HELP}/{path}"), 401)


#endregion auth posture
