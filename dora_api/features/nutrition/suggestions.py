"""Auto-matching a stock item to a nutrition food — as a *suggestion*.

The owner's ask (2026-08-15): "people don't like having to manually input data
and set stuff up. If a stock item isn't linked to any nutrition data, auto
search and best-match on the name and show it as a suggested link — accept,
ignore, or search yourself. It shouldn't get in the way, and it should be
obvious it's a suggestion."

This reverses nothing about P12 No-invent, and the distinction is the whole
design: a score computed here is **never written**. `StockItem.nutrition_food_id`
is still only ever set by a human pressing Accept (or picking through the
existing lookup). What changed is that the human is now shown a candidate
instead of being handed an empty search box, and every suggestion travels with
the number that produced it so the UI can label a weak guess as a weak guess
(P3 Honest).

**Local catalogue only.** Suggestions never call Open Food Facts or the USDA
API: this runs across the whole pantry at once, so a live source would mean
hundreds of round-trips through an endpoint already known to flap, and a
suggestion that takes six seconds to arrive is worse than no suggestion. The
manual picker keeps its full multi-source search — that's the "search yourself"
path, and it's the one place a live source is worth the wait.

Scoring is deliberately a readable formula rather than a fuzzy-match library
(R-019 No-magic): the reason a row scored 0.62 has to be explainable to the
person deciding whether to trust it.
"""
import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional
from uuid import UUID

from dora_api.domain.entities.nutrition_food import (
    NUTRITION_SOURCE_LABELS, NutritionFood,
)
from dora_api.domain.entities.stock_item import StockItem
from dora_api.features.nutrition.text_matching import normalised, tokens
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.bool_operation import Or
from dora_api.persistence.field import EntityField as Field

_LOGGER = logging.getLogger(__name__)

# Below this, no suggestion is offered at all. A wrong calorie figure the user
# accepted because it was the only thing on screen is worse than an empty row —
# the pantry is full of items ("dish soap") that *should* match nothing.
MIN_CONFIDENCE = 0.45
# At or above this the match is a near-certainty ("Bananas" → "Bananas, raw").
# The UI still asks; it just stops hedging the wording — and it's the only band
# the bulk "accept all" verb will touch, which is what the exact value is tuned
# against: at 0.70 a catalogue missing the obvious row promotes its next-best
# ("Banana chips, sweetened" scored 0.73 for "Bananas" in the calibration set)
# into a one-click mass-accept. 0.78 keeps those in the tap-to-confirm band.
STRONG_CONFIDENCE = 0.78

# A candidate has to account for **more than half** the words in the stock
# item's name. Without this floor any two-word household item finds a
# one-word food that shares a word — "Toilet paper" matched "Toilet" and
# "Dish soap" matched "Soap" at exactly 0.50, which is the precise failure the
# owner's "don't bug me about toilet paper" case is about. Losing the odd real
# match to it ("Basmati rice" → "Rice, white, long-grain") is the right trade:
# a missing suggestion costs one search, a wrong one costs wrong calories.
MIN_RECALL = 0.5

# How hard a catalogue name is penalised for words the stock item never
# mentioned. "Banana, raw" should beat "Banana chips, sweetened, dried" for
# "banana", but a dataset name is *expected* to carry qualifiers, so the
# penalty is a fraction of the score rather than a veto.
_EXTRA_WORD_PENALTY = 0.4

# Tokens shorter than this are skipped when fetching candidates — a LIKE on
# "oz" would drag in half the catalogue for nothing. They still *score* if the
# row is fetched by a longer sibling token.
_MIN_CANDIDATE_TOKEN = 3
# Per-token fetch cap on the single-item path. A stock item named "chicken"
# would otherwise pull every chicken row in SR Legacy to score one suggestion.
_MAX_CANDIDATES_PER_TOKEN = 300


@dataclass(frozen=True, slots=True)
class FoodSuggestion:
    """A candidate link, and the arithmetic behind it. `confidence` is carried
    to the client because the UI's job is to make a guess *look* like a guess —
    it is never used to decide anything server-side."""
    nutrition_food_id: UUID
    name: str
    brand: str | None
    source: str
    source_label: str
    kcal_per_100g: float | None
    confidence: float
    is_strong: bool


@dataclass(frozen=True, slots=True)
class UnmatchedStockItem:
    stock_item_id: UUID
    name: str
    suggestion: FoodSuggestion | None


def _score(item_tokens: set[str], item_normalised: str, food: NutritionFood) -> float:
    """How well *food* answers a stock item, in [0, 1].

    Two questions, in order of how much they matter:

    1. **Does it account for the words the user typed?** ("chicken breast" is
       not answered by a row about chicken soup.) That's `recall`, and it's the
       base of the score.
    2. **Does it drag in words the user didn't?** A long, heavily-qualified
       dataset name is a worse answer to a plain pantry name than a short one,
       so surplus words shave a fraction off.

    An exact name match short-circuits to 1.0 — at that point the arithmetic
    has nothing to add.
    """
    food_tokens = tokens(food.name)
    if not food_tokens or not item_tokens:
        return 0.0
    if normalised(food.name) == item_normalised:
        return 1.0

    overlap = len(item_tokens & food_tokens)
    if overlap == 0:
        return 0.0

    recall = overlap / len(item_tokens)
    if recall <= MIN_RECALL:
        return 0.0
    surplus_ratio = (len(food_tokens) - overlap) / len(food_tokens)
    return recall * (1.0 - _EXTRA_WORD_PENALTY * surplus_ratio)


def _to_suggestion(food: NutritionFood, confidence: float) -> FoodSuggestion:
    return FoodSuggestion(
        nutrition_food_id = food.id,
        name = food.name,
        brand = food.brand,
        source = food.source,
        source_label = NUTRITION_SOURCE_LABELS.get(food.source, food.source),
        kcal_per_100g = food.kcal_per_100g,
        confidence = round(confidence, 3),
        is_strong = confidence >= STRONG_CONFIDENCE,
    )


def _best(item_name: str, candidates: Iterable[NutritionFood]) -> FoodSuggestion | None:
    """The highest-scoring candidate above the floor, or None.

    A food with no kcal figure is skipped outright: linking one contributes
    nothing to a recipe rollup, so suggesting it would be asking the user to
    confirm a link that changes no number on any screen.
    """
    item_tokens = tokens(item_name)
    item_normalised = normalised(item_name)
    if not item_tokens:
        return None

    best_food: Optional[NutritionFood] = None
    best_score = 0.0
    for food in candidates:
        if food.kcal_per_100g is None:
            continue
        score = _score(item_tokens, item_normalised, food)
        # Ties break on the shorter name — the less-qualified row is the
        # generic one, and generic is the right answer for a pantry staple.
        # Without this the winner would depend on database row order.
        if score > best_score or (
            score == best_score and best_food is not None
            and len(food.name) < len(best_food.name)
        ):
            best_score = score
            best_food = food

    if best_food is None or best_score < MIN_CONFIDENCE:
        return None
    return _to_suggestion(best_food, best_score)


def suggest_for_name(repository: Repository, item_name: str) -> FoodSuggestion | None:
    """One item's suggestion — the stock-item-detail path.

    Fetches candidates with a targeted `contains` per distinctive token rather
    than reading the catalogue, because this runs on a single page load for a
    single item.
    """
    search_tokens = sorted(
        (token for token in tokens(item_name) if len(token) >= _MIN_CANDIDATE_TOKEN),
        key=len, reverse=True,
    )
    if not search_tokens:
        return None

    name_field = Field(NutritionFood, NutritionFood.Fields.NAME)
    # Longest tokens first, capped — the most distinctive word in the name is
    # the one most likely to pull the right row, and three LIKEs is plenty.
    conditions = [name_field.contains(token) for token in search_tokens[:3]]
    condition = conditions[0]
    for extra in conditions[1:]:
        condition = Or(condition, extra)

    candidates = repository.get(NutritionFood).where(condition).all()
    return _best(item_name, candidates[:_MAX_CANDIDATES_PER_TOKEN * len(conditions)])


def unmatched_items(repository: Repository) -> List[UnmatchedStockItem]:
    """Every stock item that could take a nutrition link but hasn't got one,
    each with its best suggestion.

    Ignored items are excluded — that's what ignoring is for. Unlike the
    single-item path this reads the catalogue once and builds an inverted index
    over it, because the alternative (one query per item) is a query storm on a
    page that exists to process a whole pantry at once. The local catalogue is
    bounded by what the dataset importer can install (USDA Foundation ~300 rows,
    SR Legacy ~7,800) plus whatever individual live foods have been resolved, so
    one read is cheap and predictable.
    """
    items = repository.get(StockItem).where(
        Field(StockItem, StockItem.Fields.NUTRITION_FOOD_ID).is_null()
        & Field(StockItem, StockItem.Fields.NUTRITION_IGNORED).eq(False)
    ).all()
    if not items:
        return []

    foods = repository.get(NutritionFood).all()
    by_token: dict[str, list[NutritionFood]] = {}
    for food in foods:
        if food.kcal_per_100g is None:
            continue
        for token in tokens(food.name):
            by_token.setdefault(token, []).append(food)

    results: List[UnmatchedStockItem] = []
    for item in items:
        candidates: dict[UUID, NutritionFood] = {}
        for token in tokens(item.name):
            for food in by_token.get(token, ()):
                candidates[food.id] = food
        results.append(UnmatchedStockItem(
            stock_item_id = item.id,
            name = item.name,
            suggestion = _best(item.name, candidates.values()) if candidates else None,
        ))

    # Items Dora can actually help with first — the point of the page is to
    # clear the ones that need a single tap, not to scroll past the hopeless
    # ones. Within each half, alphabetical so the order is stable across loads.
    results.sort(key=lambda r: (
        r.suggestion is None,
        -(r.suggestion.confidence if r.suggestion else 0.0),
        r.name.lower(),
    ))
    _LOGGER.info(
        "Nutrition matching: %d unlinked stock items, %d with a suggestion.",
        len(results), sum(1 for r in results if r.suggestion is not None),
    )
    return results


def ignored_item_count(repository: Repository) -> int:
    """How many items the user has waved off — the page offers to show them
    again, so it has to know whether that offer is worth rendering."""
    return repository.get(StockItem).count(
        Field(StockItem, StockItem.Fields.NUTRITION_IGNORED).eq(True)
    )


def ignored_items(repository: Repository) -> List[UnmatchedStockItem]:
    """The waved-off set, so the page can offer an undo. No suggestions are
    computed — the user already said they don't want one."""
    items = repository.get(StockItem).where(
        Field(StockItem, StockItem.Fields.NUTRITION_IGNORED).eq(True)
    ).all()
    return sorted(
        (UnmatchedStockItem(stock_item_id=i.id, name=i.name, suggestion=None) for i in items),
        key=lambda r: r.name.lower(),
    )
