"""Unit tests for server-owned cookability on RecipeDto.

§3.2 of the state-ownership refactor: the recipe DTO exposes `missing_count`
(ingredients whose stock item is out-of-stock / has no stock record) and
`cookable` (missing_count == 0), computed once from the already-loaded
ingredient tree. No client-side recomputation needed.

Decision (Chunk 1 / Q1): missing = out-of-stock only.  Low-stock
counts as "have it".
Decision (Chunk 2 / Q2): presence only, not quantity-aware — matches the
existing client behaviour; quantity-awareness is explicitly deferred.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from dora_api.features.recipes.get_recipes import RecipeDto


# ── stub helpers ──────────────────────────────────────────────────────────────

def _level(sequence):
    return SimpleNamespace(sequence=sequence, id=uuid4())


def _item(level_sequence, name="item"):
    """Stock item with the given stock level (None = no level record)."""
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        stock_level=_level(level_sequence) if level_sequence is not None else None,
        stock_location=None,
        # Echoed onto the ingredient DTO. None here keeps these cookability
        # cases about stock level only — the at-risk chips are their own
        # tests (`test_recipe_expiring_ingredients.py`).
        expiry_date=None,
    )


# The RecipeIngredient fields the DTO reads that these stubs don't vary.
_INGREDIENT_DEFAULTS = dict(
    section_id=None, is_optional=False, raw_text=None,
    label=None, preferred_buy_id=None, selected_product_id=None,
)


def _ingredient(item_sequence, name="item"):
    """Recipe ingredient stub. item_sequence=None → stock item has no level record."""
    return SimpleNamespace(
        id=uuid4(),
        stock_item=_item(item_sequence, name=name),
        quantity=None,
        unit=None,
        notes=None,
        **_INGREDIENT_DEFAULTS,
    )


def _recipe(*ingredient_args):
    """Minimal recipe stub. Each positional arg is forwarded to _ingredient()."""
    return SimpleNamespace(
        id=uuid4(),
        name="Test Recipe",
        notes=None,
        available_meals=0,
        category=None,
        cook_time_minutes=None,
        cuisine=None,
        difficulty=None,
        instructions=None,
        is_favourite=False,
        last_made_on=None,
        prep_time_minutes=None,
        recipe_collection=None,
        servings=None,
        source=None,
        time_of_day=None,
        version_group_id=None,
        kcal=None,
        # `steps_mode` was missing from the stub (pre-existing rot);
        # `created_at` is the FU-082 addition. Both are required by
        # RecipeDto.from_entity so the stub mirrors the real entity.
        steps_mode="freeform",
        created_at=datetime.now(timezone.utc),
        # Recipe-view feedback 2026-08-24 — the edit stamp. None = never
        # edited since it was added, which is what a fresh stub is.
        updated_at=None,
        ingredients=list(ingredient_args),
    )


# ── tests ─────────────────────────────────────────────────────────────────────

def test__cookable_when_all_ingredients_in_stock():
    # sequence 0 = Stocked, 1 = Low Stock — both count as "have it".
    dto = RecipeDto.from_entity(_recipe(_ingredient(0), _ingredient(1)))
    assert dto.cookable is True
    assert dto.missing_count == 0


def test__not_cookable_when_one_ingredient_out_of_stock():
    # sequence 2 = Out of Stock under the 3-band scheme.
    dto = RecipeDto.from_entity(_recipe(_ingredient(1), _ingredient(2)))
    assert dto.cookable is False
    assert dto.missing_count == 1


def test__low_stock_does_not_count_as_missing():
    # sequence 1 = Low Stock — ingredient is "present" for cookability.
    dto = RecipeDto.from_entity(_recipe(_ingredient(1)))
    assert dto.cookable is True
    assert dto.missing_count == 0


def test__none_stock_level_counts_as_missing():
    # Stock item exists but has no level assigned.
    dto = RecipeDto.from_entity(_recipe(_ingredient(None)))
    assert dto.cookable is False
    assert dto.missing_count == 1


def test__empty_recipe_is_cookable():
    dto = RecipeDto.from_entity(_recipe())
    assert dto.cookable is True
    assert dto.missing_count == 0


def test__missing_count_counts_all_missing_ingredients():
    dto = RecipeDto.from_entity(_recipe(
        _ingredient(2),   # out-of-stock
        _ingredient(2),   # out-of-stock
        _ingredient(1),   # low — not missing
    ))
    assert dto.cookable is False
    assert dto.missing_count == 2


def test__missing_count_dedupes_by_stock_item():
    # The same out-of-stock stock item listed on two ingredient rows counts once.
    shared = _item(2)
    ing_a = SimpleNamespace(id=uuid4(), stock_item=shared, quantity=None, unit=None, notes=None, **_INGREDIENT_DEFAULTS)
    ing_b = SimpleNamespace(id=uuid4(), stock_item=shared, quantity=None, unit=None, notes=None, **_INGREDIENT_DEFAULTS)
    dto = RecipeDto.from_entity(_recipe(ing_a, ing_b))
    assert dto.missing_count == 1
    assert dto.cookable is False


def test__ingredient_dto_exposes_status_booleans():
    # sequence 1 = Low, sequence 2 = Out.
    dto = RecipeDto.from_entity(_recipe(_ingredient(1), _ingredient(2)))
    low, out = dto.ingredients
    assert low.is_low_stock is True and low.is_missing is False
    assert out.is_missing is True and out.is_low_stock is False


def test__beyond_sequence_clamps_to_out_of_stock():
    # A stock level with sequence beyond the highest defined value
    # (future-proof) still counts as missing via the clamp in status_for.
    dto = RecipeDto.from_entity(_recipe(_ingredient(99)))
    assert dto.cookable is False
    assert dto.missing_count == 1


# ── missing_stock_item_names (Chunk 2) ────────────────────────────────────────

def test__missing_names_alphabetised_and_distinct():
    # Two out-of-stock items (one listed twice) + one in-stock item.
    dto = RecipeDto.from_entity(_recipe(
        _ingredient(2, name="zucchini"),
        _ingredient(2, name="apples"),
        _ingredient(2, name="apples"),    # duplicate → one entry
        _ingredient(1, name="butter"),    # low-stock → not missing, omitted
    ))
    assert dto.missing_stock_item_names == ["apples", "zucchini"]


def test__missing_names_empty_when_cookable():
    # sequence 0 = Stocked, 1 = Low — both count as "have it".
    dto = RecipeDto.from_entity(_recipe(_ingredient(0), _ingredient(1)))
    assert dto.cookable is True
    assert dto.missing_stock_item_names == []


def test__missing_names_includes_no_level_items():
    # No stock-level record → counts as missing per the contract.
    dto = RecipeDto.from_entity(_recipe(_ingredient(None, name="salt")))
    assert dto.missing_stock_item_names == ["salt"]


# ── IMPL_PLAN_RECIPE_IMPORTER §Chunk 4: tri-state cookability ────────────────
# A recipe with any unlinked required ingredient (``stock_item is None``)
# reads as cookable = None, not True or False. The DTO fields
# `missing_count` and `missing_stock_item_names` still count only the
# LINKED-missing rows — an unlinked ingredient contributes to
# `unlinked_ingredient_count` instead.


def _unlinked_ingredient(is_optional=False, raw_text="1 pound something"):
    """Recipe ingredient stub for the unlinked case (stock_item is None)."""
    return SimpleNamespace(
        id=uuid4(),
        stock_item=None,
        quantity=None,
        unit=None,
        notes=None,
        **{**_INGREDIENT_DEFAULTS, "is_optional": is_optional, "raw_text": raw_text},
    )


def test__unlinked_required_ingredient_makes_cookable_none():
    """One unlinked required ingredient → cookable is tri-state None,
    regardless of how many other ingredients are stocked."""
    dto = RecipeDto.from_entity(_recipe(
        _ingredient(0),                            # stocked
        _ingredient(1),                            # low
        _unlinked_ingredient(),                    # unlinked
    ))
    assert dto.cookable is None
    # Linked-missing count remains honest — nothing linked is missing here.
    assert dto.missing_count == 0
    assert dto.missing_stock_item_names == []
    assert dto.unlinked_ingredient_count == 1


def test__multiple_unlinked_still_reports_none():
    dto = RecipeDto.from_entity(_recipe(
        _unlinked_ingredient(),
        _unlinked_ingredient(),
        _unlinked_ingredient(),
    ))
    assert dto.cookable is None
    assert dto.unlinked_ingredient_count == 3
    assert dto.missing_count == 0


def test__unlinked_optional_ingredient_does_not_gate_cookability():
    """Optional ingredients are ignored by the cookability rule (§1.9).
    An unlinked OPTIONAL ingredient shouldn't push a recipe to None —
    the required ingredients still get a definitive True/False answer."""
    dto = RecipeDto.from_entity(_recipe(
        _ingredient(0),                            # required, stocked
        _unlinked_ingredient(is_optional=True),    # optional, unlinked → ignored
    ))
    assert dto.cookable is True
    assert dto.unlinked_ingredient_count == 0


def test__unlinked_plus_missing_still_reports_none():
    """When both an unlinked ingredient AND a linked-missing ingredient
    coexist, the unlinked one wins (None) — we can't answer definitively
    until every required ingredient is linked."""
    dto = RecipeDto.from_entity(_recipe(
        _ingredient(2, name="tomato"),             # linked-missing
        _unlinked_ingredient(),                    # unlinked
    ))
    assert dto.cookable is None
    # Linked-missing is still reported honestly on its own field.
    assert dto.missing_count == 1
    assert dto.missing_stock_item_names == ["tomato"]
    assert dto.unlinked_ingredient_count == 1
