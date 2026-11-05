"""FU-664 — a genuine first install, end to end, on a database that has never
been seeded.

Several code paths only ever run once, on a truly empty database: the first
admin's `/auth/bootstrap-admin`, and the wizard's `/onboarding/finish` seeding
default groups, the location tree, the starter-pack items and the demo recipe.
The e2e suite boots on the bulk dev seed, where every one of those is already
satisfied — so the seeders hit their "already exists, skip" branch and the
row-creating half never runs. That is how `SeedDemoHandler` kept passing an
`image=` kwarg `StockItem` had dropped, unnoticed, until a real first setup
500'd. (The demo-mode showcase seed is the same shape: only a
`DORA_DEMO_MODE` boot ever runs it.)

So this walks the real path in a child process against a throwaway SQLite file:
production's `init_db` branch (`flask_migrate.upgrade()` from empty — the
migrations, not `create_all`, provide the lookup rows), then the first admin,
then the whole wizard draft with every default picked. A second child builds
the showcase dataset from empty. Any handler whose call site has drifted from
an entity signature raises here instead of on someone's first boot.

Lean on purpose (owner stance: tests for stable, expensive-to-recheck
contracts): one walk, counts asserted loosely as "created something, 200".
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

_WIZARD_WALK = r'''
from dora_api.startup import bootstrap
from dora_api.app import app
from dora_api.features.onboarding.onboarding import _load_seed

bootstrap(is_test_env=False)  # production's branch: upgrade() from empty

client = app.test_client()
assert client.get("/api/auth/bootstrap-required").get_json() == {"required": True}
resp = client.post("/api/auth/bootstrap-admin", json={
    "username": "first", "password": "Abcdefghij1", "timezone": "Australia/Sydney",
})
assert resp.status_code == 200, resp.get_data(as_text=True)
csrf = client.get_cookie("dora_csrf")
headers = {"X-CSRF-Token": csrf.value} if csrf else {}

state = client.get("/api/onboarding/state")
assert state.status_code == 200 and state.get_json()["first_user"] is True, state.get_data(as_text=True)

assert client.get("/api/onboarding/catalog").status_code == 200
items = [
    {"name": it["name"], "group_name": it.get("group"), "location_name": it.get("location")}
    for pack in _load_seed("starter_packs.json") for it in pack.get("items", [])
]
assert items, "starter packs are empty"
draft = {
    "preferences": {"theme": "blueberry"},
    "seed": {"groups": True, "locations": True,
             "extra_group_names": ["My own group"], "extra_location_names": ["Garage"]},
    "items": {"items": items},
    "seed_demo": True,
}
resp = client.post("/api/onboarding/finish", json=draft, headers=headers)
assert resp.status_code == 200, resp.get_data(as_text=True)
body = resp.get_json()
assert body["seed"]["groups_created"] > 0 and body["seed"]["locations_created"] > 0, body
assert body["items"]["created"] > 0, body
assert body["demo"]["seeded"] is True and body["demo"]["recipe_created"] is True, body

me = client.get("/api/auth/me").get_json()
assert me["onboarding_completed_at"], me
print("SMOKE_OK")
'''

_SHOWCASE_BUILD = r'''
from dora_api.persistence.seed_showcase import reset_showcase
reset_showcase()
print("SMOKE_OK")
'''


def _run_child(temp_db: Path, code: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DORA_DB_PATH": str(temp_db),
        "DORA_DATA_DIR": str(temp_db.parent),
        "DORA_LOG_DIR": str(temp_db.parent / "logs"),
        # Test profile: no scheduler thread, no production env checks. Debug
        # off + no demo mode so init_db takes the real install's `upgrade()`.
        "DORA_ENV": "test",
        "DORA_DEBUG": "false",
        "DORA_DEMO_MODE": "false",
        "DORA_ALLOW_DESTRUCTIVE": "false",
    }
    # `DORA_DB_URL` outranks `DORA_DB_PATH` (see test_migrations._run_migration).
    env.pop("DORA_DB_URL", None)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, timeout=300,
    )


@pytest.fixture()
def temp_db():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "fresh.db"


@pytest.mark.slow
def test__fresh_install__first_admin_and_full_wizard_seed_on_an_empty_database(temp_db):
    result = _run_child(temp_db, _WIZARD_WALK)
    assert result.returncode == 0 and "SMOKE_OK" in result.stdout, (
        f"fresh-install walk failed:\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}"
    )


@pytest.mark.slow
def test__fresh_install__showcase_seed_builds_from_empty(temp_db):
    result = _run_child(temp_db, _SHOWCASE_BUILD)
    assert result.returncode == 0 and "SMOKE_OK" in result.stdout, (
        f"showcase seed failed:\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}"
    )
