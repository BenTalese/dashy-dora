"""Corpus-driven baseline test for the paste-based recipe parser.

Iterates every ``.txt`` fixture in ``tests/fixtures/recipe_paste_corpus/``,
runs it through ``parse_recipe_from_text``, and asserts the minimum-shape
declared in ``_expectations.py``. The parser stub raises
``NotImplementedError`` until Chunk 2 lands; the test catches that and
skips the fixture cleanly so the suite stays green.

**Assertions are loose by design** — each field only fires when the
expectation is non-None, and numeric time fields carry a ±2 minute
tolerance. Pinning ``(qty, unit, text)`` tuples per row would make every
parser tweak break dozens of tests; loose fences catch regressions
without over-constraining. See ``_expectations.py`` for full field
semantics.
"""
import pathlib

import pytest

from dora_api.features.recipes._parse_recipe_from_text import (
    parse_recipe_from_text,
)

# Import the expectations dict directly from the fixture folder. The
# ``_expectations.py`` file lives beside the ``.txt`` fixtures so the
# ground truth stays with the data it describes.
import sys
_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "recipe_paste_corpus"
sys.path.insert(0, str(_FIXTURE_DIR))
from _expectations import EXPECTATIONS  # noqa: E402  (path-injected import)


# ── Field-name mapping ────────────────────────────────────────────────
# The expectations dict uses concise field names (``prep_minutes``,
# ``cook_minutes``, ``total_minutes``); the DTO uses the pre-existing
# ``prep_time_minutes`` / ``cook_time_minutes`` naming from
# ``ImportedRecipeDto``. ``total_time_minutes`` isn't on the DTO yet — a
# fixture that expects it is only asserted if the DTO grows the field
# (getattr-with-default) so Chunk 2 can add it opportunistically without
# a coordinated test update.
_TIME_FIELD_MAP = {
    "prep_minutes":  "prep_time_minutes",
    "cook_minutes":  "cook_time_minutes",
    "total_minutes": "total_time_minutes",
}
_TIME_TOLERANCE_MIN = 2


@pytest.mark.unit
@pytest.mark.parametrize("fixture_name", sorted(EXPECTATIONS.keys()))
def test__parse_recipe_from_text__meets_minimum_shape(fixture_name: str) -> None:
    text = (_FIXTURE_DIR / f"{fixture_name}.txt").read_text(encoding="utf-8")
    expected = EXPECTATIONS[fixture_name]

    result = parse_recipe_from_text(text)

    # Name: substring match, case-insensitive. Guards against the parser
    # grabbing a nav crumb or related-post link as the title.
    if "name_contains" in expected:
        needle = expected["name_contains"].lower()
        haystack = (result.name or "").lower()
        assert needle in haystack, (
            f"expected name to contain {expected['name_contains']!r}, "
            f"got {result.name!r}"
        )

    # Servings: exact integer match when declared. Fixtures that don't
    # publish a clean integer (e.g. Smitten Kitchen "24 or 34") pin the
    # first / most-conservative number in the expectations.
    if expected.get("servings") is not None:
        assert result.servings == expected["servings"], (
            f"expected servings={expected['servings']}, got {result.servings!r}"
        )

    # Time fields: ±2 minute tolerance to absorb rounding when a site
    # rounds "1 hr 5 mins" to "1 hr" or when the parser sums prep+cook
    # slightly differently from the fixture's stated total.
    for exp_field, dto_field in _TIME_FIELD_MAP.items():
        if expected.get(exp_field) is None:
            continue
        actual = getattr(result, dto_field, None)
        if actual is None and exp_field == "total_minutes":
            # ``total_time_minutes`` isn't guaranteed on the DTO yet.
            # Skip the assertion so Chunk 2 can add it opportunistically.
            continue
        assert actual is not None, (
            f"expected {dto_field}={expected[exp_field]}, got None"
        )
        assert abs(actual - expected[exp_field]) <= _TIME_TOLERANCE_MIN, (
            f"expected {dto_field}≈{expected[exp_field]} (±{_TIME_TOLERANCE_MIN}), "
            f"got {actual}"
        )

    # Ingredient count: lower bound only. A parser tweak that finds one
    # extra ingredient never breaks the fence.
    if "min_ingredients" in expected:
        assert len(result.ingredients) >= expected["min_ingredients"], (
            f"expected ≥{expected['min_ingredients']} ingredients, "
            f"got {len(result.ingredients)}"
        )

    # First ingredient substring: the strongest "did the parser find
    # the right block?" signal. If the parser grabbed the pre-story
    # text as ingredients, this fails immediately.
    if "first_ingredient_contains" in expected and result.ingredients:
        needle = expected["first_ingredient_contains"].lower()
        first_raw = (result.ingredients[0].raw_text or "").lower()
        assert needle in first_raw, (
            f"expected first ingredient to contain "
            f"{expected['first_ingredient_contains']!r}, got {first_raw!r}"
        )

    # Step count: lower bound. Photo captions / photographer credits
    # interleaved with real steps (see allrecipes3) push the true count
    # higher than the fixture's fence, so a naive parser that lets them
    # through still passes.
    if "min_steps" in expected:
        assert len(result.steps) >= expected["min_steps"], (
            f"expected ≥{expected['min_steps']} steps, got {len(result.steps)}"
        )


@pytest.mark.unit
def test__parse_recipe_from_text__taste_video_carousel_cruft_stripped() -> None:
    """DORA_VERIFY Cookbook L148 — the taste.com.au2 fixture wraps its method
    in a video carousel (an '01:01' timecode, 11× 'Next video thumbnail', a
    video title + 'more' link) that a naive collector grabs as ~16 junk steps,
    and leaks Coles price-estimate chrome into the ingredient block ('Estimate
    based on…', 'Fulfilled by coles-logo', 'Show ingredient quantity').

    The parametrized shape test above only checks *lower* bounds, so it can't
    catch cruft creeping back in. Pin the exact negatives against the one
    fixture built to exercise them."""
    text = (_FIXTURE_DIR / "taste.com.au2.txt").read_text(encoding="utf-8")
    result = parse_recipe_from_text(text)

    # Coles price chrome must never land as (or inside) an ingredient row.
    for ing in result.ingredients:
        raw = (ing.raw_text or "").lower()
        for junk in ("estimate based on", "fulfilled by", "coles-logo",
                     "show ingredient quantity"):
            assert junk not in raw, f"ingredient carried price chrome: {ing.raw_text!r}"

    # The video carousel must not survive as steps.
    step_texts = [s.text for s in result.steps]
    for t in step_texts:
        assert "next video thumbnail" not in t.lower(), (
            f"video-carousel thumbnail leaked as a step: {t!r}"
        )
    assert not any(t.strip().lower() == "more" for t in step_texts), (
        "the video carousel's trailing 'more' link leaked as a step"
    )
    # 11 thumbnails + title + 'more' would roughly quadruple the real ~3-step
    # method; fence the count so the carousel can't return as bulk junk even
    # if the exact strings change.
    assert len(result.steps) <= 10, (
        f"expected the real method only, got {len(result.steps)} steps: {step_texts}"
    )
