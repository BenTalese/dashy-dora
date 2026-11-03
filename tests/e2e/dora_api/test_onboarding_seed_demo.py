"""FU — `POST /onboarding/finish` with `seed_demo` on a genuinely fresh install.

The demo seed has two paths and only one of them was ever exercised here: on a
dev-seeded (or already-onboarded) DB the "Spaghetti Aglio e Olio" recipe
already exists, so the handler short-circuits on its idempotency check and the
row-creating half never runs. A real first-run install has neither the recipe
nor its three pantry items, and that half went stale — it was still passing an
`image=` kwarg to `StockItem`, a field the entity dropped, so every genuine
first setup that ticked "Add a demo recipe + this-week meal plan" 500'd and the
wizard's Finish could not complete.

This test forces the fresh-install branch: drop the recipes, and rename the
demo's ingredients out of the way so the handler has to create its own.
"""
import requests

from tests.e2e.dora_api._onboarding_finish import finish_demo
from sqlalchemy import text

from dora_api.app import app, db

BASE = "http://localhost:5170/api"

# Match the starter pack (finalisation 14-R2) — the demo reuses the wizard's items.
_DEMO_INGREDIENT_NAMES = ("Pasta", "Garlic", "Olive oil")


def _force_fresh_install_state() -> None:
    """No recipes, and none of the demo's ingredients present by name."""
    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(text('DELETE FROM "MealPlanEntry"'))
            conn.execute(text('DELETE FROM "RecipeIngredient"'))
            conn.execute(text('DELETE FROM "Recipe"'))
            for name in _DEMO_INGREDIENT_NAMES:
                # Match the handler's own case-insensitive, trimmed lookup —
                # an exact-name UPDATE leaves near-miss rows behind and the
                # handler then reuses one instead of creating it.
                conn.execute(
                    text(
                        'UPDATE "StockItem" SET name = :new '
                        "WHERE lower(trim(name)) = :old"
                    ),
                    {"new": f"zz-renamed {name}", "old": name.strip().lower()},
                )
        db.session.remove()


def test__seed_demo__fresh_install__creates_items_recipe_and_plan(api):
    _force_fresh_install_state()

    response = finish_demo()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["seeded"] is True, body
    # The row-creating half actually ran: all three ingredients were missing,
    # so the handler had to construct StockItems itself (the branch that broke).
    assert body["items_created"] == len(_DEMO_INGREDIENT_NAMES), body
    assert body["recipe_created"] is True, body
    assert body["meal_plan_created"] is True, body


def test__seed_demo__joins_an_existing_plan_for_this_week__never_a_second_one(api):
    """Finalisation 14-R1 — `MealPlan` has no week uniqueness and the demo
    always inserted a new plan anchored on this Monday, so a household that
    had already planned the week saw two overlapping plans. The demo now
    joins the existing plan: the plan count is unchanged, one entry is added."""
    from datetime import date, timedelta

    _force_fresh_install_state()
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    created = requests.post(f"{BASE}/meal-plans", json={"start_date": monday.isoformat(), "entries": []})
    assert created.status_code in (200, 201), created.text

    def _counts() -> tuple[int, int]:
        with app.app_context():
            with db.engine.begin() as conn:
                plans = conn.execute(text('SELECT COUNT(*) FROM "MealPlan"')).scalar_one()
                entries = conn.execute(text('SELECT COUNT(*) FROM "MealPlanEntry"')).scalar_one()
            db.session.remove()
        return int(plans), int(entries)

    plans_before, entries_before = _counts()
    body = finish_demo().json()
    assert body["seeded"] is True and body["meal_plan_created"] is True, body
    plans_after, entries_after = _counts()

    assert plans_after == plans_before, "the demo must join this week's plan, not add a second one"
    assert entries_after == entries_before + 1


def test__seed_demo__second_call__is_a_no_op(api):
    _force_fresh_install_state()
    assert finish_demo().json()["seeded"] is True

    repeat = finish_demo()

    assert repeat.status_code == 200, repeat.text
    assert repeat.json() == {
        "seeded": False,
        "items_created": 0,
        "recipe_created": False,
        "meal_plan_created": False,
    }
