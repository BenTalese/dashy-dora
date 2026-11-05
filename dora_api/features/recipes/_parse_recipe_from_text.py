"""Text-only recipe parser — the core of the paste-based importer.

**Chunk 2 (Class A parser)** — anchor-based extraction for sites that
publish explicit ``Ingredients`` / ``Instructions`` / ``Method`` /
``Directions`` header lines. Ships with the meta-block sweep for
Prep / Cook / Total / Servings / Yield.

**Chunk 3 (Class B fallback)** — grammar-based extraction for
Smitten-Kitchen-shaped sites (no ``Ingredients`` header). Anchors on
the first ``Serves N`` / ``Yield:`` / ``Servings:`` line; collects
ingredient-shape lines downward through the block; stops at the first
numbered step or long verb-prefixed prose paragraph. Sub-section
headers (``Sauce``, ``Meatballs``, ``For the chicken``) are skipped
in place — the current DTO has no section field, so we lose the
grouping in exchange for finding the individual ingredients.

Design notes:

* DTOs live in ``imported_recipe_dtos.py`` so both this file and the
  handler (``import_recipe_from_content.py``) can import them without
  a circular dependency.
* ``_parse_qty_unit`` grammar lives inline here — its only caller is
  this parser after Chunk 5 retired the URL-importer file.
* ``source_url`` is left blank on the returned DTO; the handler
  stamps it from the request body before responding.
* Fuzzy-matching against the user's ``StockItem`` set is NOT done
  here — the parser is pure and side-effect-free. The handler that
  wraps it does the match pass.

Style:

* Every helper below has a one-line ``### Header`` above the def that
  names the site shape it exists for. Grep-friendly if a fixture
  regresses.
* All regexes at module scope so the test suite doesn't recompile
  them per call.
"""
import re
import uuid
from typing import List

from dora_api.features.recipes.imported_recipe_dtos import (
    ImportedIngredientDto,
    ImportedRecipeDto,
    ImportedStepDto,
)


# ── Ingredient-line quantity/unit grammar ────────────────────────────

# Greedy "1 1/2 cups" / "1.5 tbsp" / "2-3 cloves of garlic" parser. We
# accept a permissive grammar because recipe sites are wildly inconsistent
# and we'd rather hand the user *something* than refuse to parse. Moved
# inline in Chunk 5 (was in ``import_recipe_from_url.py`` before the
# URL importer file was retired).
_QTY_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<qty>
        \d+\s*\/\s*\d+              # 1/2
      | \d+(?:\.\d+)?\s+\d+\s*\/\s*\d+   # 1 1/2
      | \d+(?:\.\d+)?              # 1.5
    )?
    \s*
    (?P<unit>
        cups?|tbsps?|tsps?|tablespoons?|teaspoons?|
        g|kg|ml|l|oz|lb|lbs|cloves?|cans?|pinch|slices?|
        sprigs?|bunch(?:es)?|knob|stick|pieces?
    )?
    \s*
    (?P<rest>.*)
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _parse_qty_unit(raw: str) -> tuple[float | None, str | None, str]:
    """Return (quantity, unit, remainder). Remainder is the readable name."""
    text = raw.strip()
    match = _QTY_PATTERN.match(text)
    if not match:
        return None, None, text
    qty_str = (match.group("qty") or "").strip()
    unit = match.group("unit")
    rest = (match.group("rest") or "").strip(" ,.-")
    quantity: float | None = None
    if qty_str:
        try:
            if " " in qty_str:  # "1 1/2" mixed form
                whole, frac = qty_str.split(" ", 1)
                num, den = frac.split("/", 1)
                quantity = float(whole) + (float(num) / float(den))
            elif "/" in qty_str:
                num, den = qty_str.split("/", 1)
                quantity = float(num) / float(den)
            else:
                quantity = float(qty_str)
        except (ValueError, ZeroDivisionError):
            quantity = None
    return quantity, unit, rest or text


# ── Meta block: times + servings ──────────────────────────────────────

# R-068 carve-out (FU-799): every value this module reads out of prose —
# prep / cook / total minutes, servings, quantities and units, the step list —
# is a *proposal*. `import-from-content` only returns a draft; it lands in the
# recipe editor, where the user sees and corrects each field before
# `POST /recipes` records it as a real column. Nothing here drives behaviour
# on its own, which is the rule's stated non-goal ("the importer's first-pass
# parse"). Step timers are deliberately not inferred here: a structured step's
# `timer_minutes` is the cook's to declare (ADR-065).

# Time-value primitives. ``(?![a-z])`` guards against matching "m" in
# "medium" or "h" in "hot" — after the unit we require a non-letter
# (digit, whitespace, EOL, punctuation all fine). Case-insensitive.
_HOURS_VALUE_RE = re.compile(r"(\d+)\s*(?:hours?|hrs?|h)(?![a-z])", re.I)
_MINS_VALUE_RE = re.compile(r"(\d+)\s*(?:minutes?|mins?|m)(?![a-z])", re.I)

# Label sweep — finds every occurrence of a meta-block label anywhere in
# the text, remembers where each match ends, and slices out the value
# chunk between it and the next label. Two branches:
#
#   1. Line-start form: label at the beginning of a line (with optional
#      indentation). Handles Woolworths / Taste bare labels, HBH's
#      "Prep Time 25 minutes minutes", AllRecipes' "Prep Time:", and
#      RecipeTin's no-space "Servings4 – 5".
#   2. Inline form: label mid-line, MUST be followed by a colon. Catches
#      Sally's all-one-line meta ("Author: ... Prep Time: 4 hours ...
#      Cook Time: 30 minutes Total Time: 8 hours ..."). The colon
#      requirement rejects prose false-positives like "The recipe
#      makes 2 crusts" (Sally's story text) or "so using the right
#      type makes all the difference" (RecipeTin story).
#
# ``time`` as a total-time synonym only fires in the INLINE branch (SK3's
# "Servings: 4 Time: 45 minutes Source: Smitten Kitchen"). At line start,
# "time" is too promiscuous — HBH3 has "chill time 2 hours hours" as a
# separate row above the real total, and we don't want that stealing
# the total slot.
_META_LABEL_RE = re.compile(
    r"""
    (?:
        # ── Branch 1: line-start ─────────────────────────────────────
        ^\s*
        (?:
            (?P<prep_l>prep(?:\s+time)?)
          | (?P<cook_l>cook(?:\s+time)?)
          | (?P<total_l>total(?:\s+time)?)
          | (?P<yield_l>yield)
          | (?P<servings_l>servings?|serves|makes|number\s+of\s+servings?)
        )
        (?=\s*(?::|\d|\n|$))
        \s* :? \s*
      |
        # ── Branch 2: inline, must have colon ────────────────────────
        # Bare ``time`` deliberately excluded here — Simply Recipes' 2/3
        # slot a "Resting time:" line between cook and total. Matching
        # "time:" would consume that as the total. SK3's inline "Time:
        # 45 minutes Source: ..." loses total in exchange; SK3 is
        # Class B (Chunk 3 territory) so that's an acceptable trade.
        (?<=[\s|;])
        (?:
            (?P<prep_i>prep(?:\s+time)?)
          | (?P<cook_i>cook(?:\s+time)?)
          | (?P<total_i>total(?:\s+time)?)
          | (?P<yield_i>yield)
          | (?P<servings_i>servings?|serves|makes)
        )
        \s* : \s*
    )
    """,
    re.I | re.VERBOSE | re.MULTILINE,
)

# Maps each canonical label key to the pair of group names it can hit
# (line-start branch + inline branch). Loop-driven in ``_sweep_meta``.
_META_LABEL_KEYS: tuple[tuple[str, str, str], ...] = (
    ("prep",     "prep_l",     "prep_i"),
    ("cook",     "cook_l",     "cook_i"),
    ("total",    "total_l",    "total_i"),
    ("yield_",   "yield_l",    "yield_i"),
    ("servings", "servings_l", "servings_i"),
)


def _time_to_minutes(chunk: str) -> int | None:
    """Extract minutes from a time value string.

    Handles:
        "10 mins" / "10 minutes"                              → 10
        "10 minutes minutes" (HBH double-word quirk)          → 10
        "10m" / "10minutes"                                   → 10
        "1 hr" / "1 hour" / "1 hrs"                           → 60
        "3 hrs 10 mins" / "3 hours 10 minutes"                → 190
        "3 hours, 15 minutes (includes chilling)" (Sally's)   → 195
        "2 hours hours 10 minutes minutes" (HBH3 quirk)       → 130
        "1h 05m" / "1h05m" / "4hr25m"                         → 65/265
        "8 hours (includes chilling)"                         → 480

    Only the FIRST non-empty line of the chunk is inspected — later lines
    often carry a sibling label's value (HBH3 slots "chill time 2 hours"
    between the prep and total lines; without this restriction, prep
    would sum in the chill-time hours and land on 130 min instead of 10).
    Within that first line, first-hours + first-minutes are summed;
    a naive ``sum(all)`` would double-count Woolworths' verbose duplicate
    ("Preparation time is 10minutes\\n10m" → 20 instead of 10).
    """
    if not chunk:
        return None
    first_line = ""
    for line in chunk.splitlines():
        if line.strip():
            first_line = line
            break
    if not first_line:
        return None
    hours_match = _HOURS_VALUE_RE.search(first_line)
    mins_match = _MINS_VALUE_RE.search(first_line)
    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(mins_match.group(1)) if mins_match else 0
    total = hours * 60 + minutes
    return total if total > 0 else None


def _sweep_meta(text: str) -> dict[str, str]:
    """Sweep the entire text for meta-block labels; return {key: chunk}.

    The chunk for each label runs from the char AFTER the label to
    the char BEFORE the next label (or EOF). First occurrence of each
    key wins — a page that repeats "Prep Time: 15 min" in a comment
    doesn't override the recipe card's value. Labels handled: ``prep``,
    ``cook``, ``total``, ``yield_``, ``servings``.
    """
    matches = list(_META_LABEL_RE.finditer(text))
    if not matches:
        return {}

    result: dict[str, str] = {}
    for i, m in enumerate(matches):
        # Which named group did we hit? Check both branches per key.
        key: str | None = None
        for canon, group_l, group_i in _META_LABEL_KEYS:
            if m.group(group_l) or m.group(group_i):
                key = canon
                break
        if key is None:
            continue
        chunk_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[m.end():chunk_end]
        # First occurrence wins.
        if key not in result:
            result[key] = chunk
    return result


def _extract_times(text: str) -> tuple[int | None, int | None, int | None]:
    """Return (prep_minutes, cook_minutes, total_minutes)."""
    meta = _sweep_meta(text)
    return (
        _time_to_minutes(meta.get("prep", "")),
        _time_to_minutes(meta.get("cook", "")),
        _time_to_minutes(meta.get("total", "")),
    )


_FIRST_INT_RE = re.compile(r"\d+")


def _extract_servings(text: str) -> int | None:
    """Return the first integer in the servings/yield chunk, or None.

    Priority order: ``servings`` label > ``yield_`` label. ``Serves 6 to
    8 as a tapa`` gives 6 (first int); ``Yield: 1 9-inch pie`` gives 1.
    Both are honest — the parser reports what the source declared,
    even when the yield count is a pie/cookie count rather than plates.
    """
    meta = _sweep_meta(text)
    for key in ("servings", "yield_"):
        chunk = meta.get(key, "")
        if not chunk:
            continue
        match = _FIRST_INT_RE.search(chunk)
        if match:
            return int(match.group(0))
    return None


# ── Section anchors: Ingredients / Instructions ──────────────────────

# ``Ingredients (14)`` (taste.com.au bakes the count into the header),
# ``Ingredients:`` (some sites), plain ``Ingredients``, ``6 Ingredients``
# (Woolworths prefixes the count). Anchor is a STANDALONE line —
# trailing description tokens are not accepted so a story sentence like
# "Key ingredients in our recipe..." doesn't false-fire.
_INGREDIENTS_ANCHOR_RE = re.compile(
    r"^\s*(?:\d+\s+)?ingredients?\s*(?:\(\d+\))?\s*:?\s*$",
    re.I,
)
_STEPS_ANCHOR_RE = re.compile(
    r"^\s*(?:instructions?|directions?|method)\s*:?\s*$",
    re.I,
)
# Stop markers: any of these on a bare line ends the current block.
# Ordered by prevalence in the corpus. ``Notes`` catches Sally's Notes
# section; ``Nutrition`` catches Simply Recipes' Nutrition Facts;
# ``Related`` / ``Post navigation`` / ``Leave a Reply`` catch the
# Smitten Kitchen footer (Chunk 3 will also lean on these).
_STOP_MARKER_RE = re.compile(
    r"""
    ^\s*(?:
        notes?
      | nutrition(?:\s+(?:facts|information|per\s+serving))?
      | recipe\s+tip
      | recipe\s+notes
      | editor'?s\s+note
      | related
      | see\s+more
      | post\s+navigation
      | leave\s+a\s+reply
      | share\s+this
      | tried\s+this\s+recipe
      | you\s+might\s+also\s+like
      | comments?
      | love\s+the\s+recipe
      | \d+\s+comments?\s+on
      | print\s+recipe
      | email\s+recipe
      | save\s+recipe
    )\b.*$
    """,
    re.I | re.VERBOSE,
)

# Recipe-card scaffolding around the ingredient/step blocks. These lines
# are inside the block but not part of the actual data.
_INGREDIENT_NOISE_RE = re.compile(
    r"""
    ^\s*(?:
        \d+/?\d*x         # AllRecipes scaling widget: "1/2x", "1x", "2x"
      | original\s+recipe # "Original recipe (1X) yields N servings"
      | us\s+customary    # HBH "US Customary – Metric" unit-toggle line
      | cook\s+mode
      | prevent(?:\s+your)?\s+screen
      | keep\s+screen\s+awake
      | tap\s+or\s+hover  # RecipeTin's "Tap or hover to scale"
      | shop\s+ingredients
      | instacart
      | number\s+of\s+servings? # WW "Number of servings" header
      | print
      | save
      | \d+\s+ingredients?$   # WW "6 Ingredients" section header
      | show\s+ingredient\s+quantity  # taste.com.au widget label
      | estimate\s+based\s+on  # taste/Coles price-estimate widget
      | fulfilled\s+by         # taste/Coles "Fulfilled by coles-logo"
    )\b.*$
    """,
    re.I | re.VERBOSE,
)

# Lines that appear inside the steps block but aren't real steps.
_STEP_NOISE_RE = re.compile(
    r"""
    ^\s*(?:
        step\s+\d+(?:\s+of\s+\d+)?\s*$  # taste "Step 1", WW "Step 1 of 3"
      | abbreviated\s+recipe:?\s*$      # RecipeTin's "ABBREVIATED RECIPE:"
      | full\s+recipe:?\s*$
      | dotdash\s+meredith               # AllRecipes photographer credit
      | simply\s+recipes\s+/            # Simply Recipes photo credit
      | show\s+ingredient\s+quantity     # taste "Method / Show ingredient quantity" widget
      | next\s+video\s+thumbnail         # taste video-carousel spam
      | .+[-\s]step\s?\d+\s*$            # taste per-step photo caption ("Shephards Pie-Step 1")
    )\b.*$
    """,
    re.I | re.VERBOSE,
)

# Trailing junk that marks the end of the real steps on taste.com.au: a
# bare video timecode ("01:01"), the "Next video thumbnail" carousel, or
# a lone "more" nav link. Everything after the FIRST such line (video
# title/description, related links) is not part of the method. Used as an
# extra stop condition in ``_find_steps_block`` — kept separate from
# ``_STEP_NOISE_RE`` because these END the block rather than being skipped
# in place (the video title "How to prepare citrus" that follows the
# carousel has no marker of its own and would otherwise leak).
_STEPS_TRAILING_JUNK_RE = re.compile(
    r"^\s*(?:\d{1,2}:\d{2}|next\s+video\s+thumbnail|more)\s*$",
    re.I,
)

# Sub-section headers within an ingredient block. Ends with ``:`` and
# starts with a letter. HBH / RecipeTin use these ("Portuguese chicken
# seasoning:", "Blanched tofu:", "Sauce:"). Bare uncolon'd sub-headers
# like Smitten Kitchen's "Sauce" / "Meatballs" are Class B territory —
# Chunk 3 handles them; Chunk 2's anchor-based path stays literal.
_SUBSECTION_HEADER_RE = re.compile(r"^\s*[A-Za-z][^:\d]{0,80}:\s*$")

# Bullet markers stripped before per-line parsing. Each is a single char
# except ▢ (WordPress Tasty Recipes checkbox) which is multi-byte.
_BULLET_PREFIX_RE = re.compile(r"^[\s\-\*•▢·]+")

# Ingredient-shape guard: a real ingredient line either starts with a
# digit (or fraction glyph) OR is preceded by a quantity-holding leading
# token. Used to reject narrative lines that slip past the bullet strip.
# Also accepts ingredient-shape lines without a leading quantity (e.g.
# "salt and pepper, to taste", "Freshly ground black pepper") — the guard
# just requires the line to be short-ish and not sentence-shaped.
_FRACTION_GLYPHS = "½¼¾⅓⅔⅛⅜⅝⅞"


def _looks_like_ingredient(line: str) -> bool:
    """Heuristic: does this line read as an ingredient row?

    Two positive signals:
    * Starts with a quantity — a digit, a fraction glyph, or a range
      digit (a strong yes).
    * Is 20+ chars, isn't a full sentence, doesn't end with a period.
      That catches "salt and pepper, to taste" (24 chars, no digit) but
      rejects nav-menu single words like "Occasions" (9 chars).

    Chunk 2 tolerates a small false-negative rate on short unbulleted
    ingredients (Smitten Kitchen's "Vegetable oil" — 13 chars) because
    those recipes are Class B and get grammar-based extraction in
    Chunk 3.
    """
    s = line.strip()
    if not s:
        return False
    if len(s) > 200:
        return False   # sentence-shaped
    if len(s) < 4:
        return False   # rejects bare "8" (Woolworths' "Number of servings\n8")
    if s[0].isdigit() or s[0] in _FRACTION_GLYPHS:
        return True
    if len(s) >= 20 and s.count(".") <= 1 and not s.endswith("."):
        return True
    return False


# ── Ingredient block detection ──────────────────────────────────────


def _find_ingredient_block(lines: list[str]) -> tuple[int, int]:
    """Return (start, end) indices into ``lines`` for the ingredient block.

    Both indices exclusive of the anchor and stop-marker lines.

    Multiple ``Ingredients`` anchors are common:
    * Nav menus (top + footer) on AllRecipes, Sally's Baking.
    * "Sightseeing" ingredient overviews on HBH (unbulleted, chatty).
    * The real recipe card (bulleted or digit-fronted).

    Anchor scoring picks the block that reads like real ingredients:
    each following non-blank line gets +2 if it starts with a bullet
    marker (▢, -, *, •) and +1 if it starts with a digit or fraction
    glyph. Nav menus score 0 (short single words); real cards score
    high (5+ digit-fronted lines).

    On tie or all-zero, prefer the LAST anchor (recipe card comes after
    the story). Returns (-1, -1) when no anchor exists — Smitten
    Kitchen and its shape-alikes are Class B territory.
    """
    anchors: list[int] = []
    for idx, line in enumerate(lines):
        if _INGREDIENTS_ANCHOR_RE.match(line):
            anchors.append(idx)
    if not anchors:
        return (-1, -1)

    # Find the first steps anchor globally — the recipe-card ingredient
    # block sits *immediately* before it. Nav-menu "Ingredients" entries
    # in headers and footers score high on digit-content because the
    # meta block (with all its "10 mins" / "4 servings" digits) falls
    # inside their window; the proximity rule dodges that trap.
    first_steps = -1
    for j, line in enumerate(lines):
        if _STEPS_ANCHOR_RE.match(line):
            first_steps = j
            break

    # Prefer the LAST ingredient anchor that appears before the first
    # steps anchor. Fallbacks: no steps anchor found → last ingredient
    # anchor overall (Class B may not have an explicit steps header).
    if first_steps > 0:
        candidates = [a for a in anchors if a < first_steps]
        chosen = candidates[-1] if candidates else anchors[-1]
    else:
        chosen = anchors[-1]

    end = len(lines)
    for j in range(chosen + 1, len(lines)):
        if _STEPS_ANCHOR_RE.match(lines[j]) or _STOP_MARKER_RE.match(lines[j]):
            end = j
            break
    return (chosen + 1, end)


def _extract_ingredients(block: list[str]) -> List[ImportedIngredientDto]:
    """Turn raw ingredient-block lines into DTOs.

    Skips noise (scaling widgets, "Original recipe...", unit-toggles,
    Cook-Mode / Print / Save widgets). Sub-section headers (lines
    ending in ``:``) are dropped — Chunk 4's schema work adds structured
    sections, but the CURRENT ``ImportedIngredientDto`` shape has no
    section field, so keeping the raw section header would masquerade
    as an ingredient. (The wire has ``ImportedIngredientDto`` fields
    only; Chunk 4 extends this.)

    De-dups consecutive lines with identical ``rest`` (after strip +
    lower) so Woolworths' double-listed pairs collapse to one entry
    per real ingredient.
    """
    out: list[ImportedIngredientDto] = []
    last_rest: str | None = None
    for raw in block:
        line = raw.strip()
        if not line:
            continue
        if _INGREDIENT_NOISE_RE.match(line):
            continue
        if _SUBSECTION_HEADER_RE.match(line):
            continue
        # Class B sub-section headers (bare, no colon). "Sauce",
        # "Meatballs", "To finish, if desired", "For the chicken". Also
        # kicks in on Class A blocks that happen to have a bare header
        # (e.g. Simply Recipes' "Cook the pasta:" style, which uses a
        # colon and would already be caught above, but the bare form
        # exists in the wild too).
        if _CLASS_B_SUBSECTION_RE.match(line):
            continue
        # Strip bullet prefix + retry emptiness.
        stripped = _BULLET_PREFIX_RE.sub("", line).strip()
        if not stripped:
            continue
        if not _looks_like_ingredient(stripped):
            continue
        qty, unit, rest = _parse_qty_unit(stripped)
        rest_norm = rest.lower().strip()
        if last_rest is not None and rest_norm == last_rest:
            # Woolworths double-listed same-line dupe.
            continue
        last_rest = rest_norm
        out.append(ImportedIngredientDto(
            raw_text=stripped,
            stock_item_id=None,
            stock_item_name=None,
            match_score=0,
            quantity=qty,
            unit=unit,
            notes=None,
        ))
    return out


# ── Steps block detection ──────────────────────────────────────────


def _find_steps_block(lines: list[str], after: int) -> tuple[int, int]:
    """Return (start, end) for the steps block after ``after`` (exclusive).

    Prefers an explicit ``Instructions`` / ``Directions`` / ``Method``
    anchor. If none exists downstream of the ingredient block (rare on
    Class A; the Class B fallback in Chunk 3 handles anchor-less shape),
    returns (-1, -1).
    """
    anchor = -1
    for idx in range(after, len(lines)):
        if _STEPS_ANCHOR_RE.match(lines[idx]):
            anchor = idx
            break
    if anchor < 0:
        return (-1, -1)
    end = len(lines)
    for j in range(anchor + 1, len(lines)):
        if _STOP_MARKER_RE.match(lines[j]) or _STEPS_TRAILING_JUNK_RE.match(lines[j]):
            end = j
            break
    return (anchor + 1, end)


# Strip leading step-number markers: "1.", "1)", "Step 1:", indented
# forms. Kept broad — the corpus has variants across every site.
_STEP_NUMBER_STRIP_RE = re.compile(r"^\s*(?:step\s+)?\d+[.):]\s*", re.I)


def _extract_steps(block: list[str]) -> List[ImportedStepDto]:
    """Turn raw step-block lines into DTOs.

    Each non-noise line becomes one step. The current DTO doesn't carry
    section grouping, so Simply Recipes' "Cook the pasta:" sub-headers
    become their own top-level steps here — that's the same behaviour
    the existing JSON-LD importer has and it round-trips fine through
    the SPA's step editor.

    ``client_id`` is fresh per call so the SPA can round-trip the ids
    into ``CreateRecipeCommand.steps[].client_id`` unchanged.
    """
    out: list[ImportedStepDto] = []
    seq = 0
    for raw in block:
        line = raw.strip()
        if not line:
            continue
        if _STEP_NOISE_RE.match(line):
            continue
        # Strip leading number marker; skip if what's left is empty.
        cleaned = _STEP_NUMBER_STRIP_RE.sub("", line).strip()
        if not cleaned:
            continue
        # Skip photo alt-text: a line that reads like "A <noun> of ..." /
        # "close up of ..." / "overhead ..." often follows real steps.
        # Loose heuristic: <60 chars, no verb-shape end punctuation.
        if _looks_like_photo_alt(cleaned):
            continue
        out.append(ImportedStepDto(
            client_id=str(uuid.uuid4()),
            parent_client_id=None,
            sequence=seq,
            text=cleaned,
            hint=None,
        ))
        seq += 1
    return out


_PHOTO_ALT_HEAD_RE = re.compile(
    r"^(?:a|an|close\s+up|overhead|top\s+down|side\s+view|"
    r"finished|plated|ingredients|the)\s+",
    re.I,
)


def _looks_like_photo_alt(line: str) -> bool:
    """Loose guard: does this look like image alt-text rather than a step?

    Alt-text patterns: short (< 120 chars), starts with a determiner or
    ``close up`` / ``overhead``, doesn't end with a period, doesn't
    contain a verb-heavy phrase like ``cook`` / ``stir`` / ``add`` in
    the first half. We avoid over-filtering: real steps that happen to
    start with "A" (like "A pinch of salt.") wouldn't match because the
    length + terminal-period guards catch them.
    """
    if len(line) > 120:
        return False
    if line.endswith(".") or line.endswith("!"):
        return False
    if not _PHOTO_ALT_HEAD_RE.match(line):
        return False
    # Verb check on the first half — if a common step verb appears
    # early, it's probably a real step written in narrative style.
    head = line[: len(line) // 2].lower()
    for verb in ("cook", "stir", "add", "mix", "combine", "heat", "bake",
                 "preheat", "chop", "slice", "whisk", "pour", "serve"):
        if verb in head:
            return False
    return True


# ── Class B fallback: no-header shape (Smitten Kitchen) ─────────────

# Class B trigger: recipe body starts at a "Serves N" / "Yield:" /
# "Servings:" / "Makes N" line WITHOUT an "Ingredients" header ever
# appearing. Anchor pattern is intentionally line-anchored so we don't
# fire on a story mention like "the original serves 6 as a tapa";
# leading whitespace tolerated (SK3's meta is indented).
_CLASS_B_ANCHOR_RE = re.compile(
    r"^\s*(?:serves?|servings?|yields?|makes)\b",
    re.I,
)

# Notes / tips lines the parser skips WHILE scanning for the first
# ingredient. SK3 stashes an "Always good to note:" paragraph and a
# separate "Note: You can watch..." between the servings anchor and
# the ingredient block — neither is an ingredient.
_CLASS_B_NOTE_RE = re.compile(
    r"^\s*(?:note|notes|tip|tips|nb|hint|always|also|remember)\b",
    re.I,
)

# Bare sub-section header — no colon required. Matches SK1's "Sauce"
# and "Meatballs" as well as "For the chicken" / "To finish, if
# desired" / "To serve" sub-headers. Kept narrow (short line, title-
# case-ish, ends without punctuation except optional colon) so
# ordinary short prose lines don't accidentally match.
_CLASS_B_SUBSECTION_RE = re.compile(
    r"""
    ^\s*
    (?:
        for\s+the\s+[a-z][a-z\s\-]{2,40}     # "For the chicken"
      | to\s+(?:serve|finish|garnish|assemble)(?:,\s+if\s+desired)?  # "To serve" / "To finish, if desired"
      | (?-i:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?) # 1-2 words, ALL title-case
    )
    \s* :? \s* $
    """,
    re.I | re.VERBOSE,
)
# The bare title-case branch uses ``(?-i:...)`` to force case-sensitive
# matching — that rejects "Nonstick cooking spray" (Simply Recipes 2's
# first ingredient) where the second word "cooking" starts lowercase,
# while accepting real Class B sub-section headers like "Sauce" and
# "Meatballs" whose words all lead with capitals.

# Step-shape line: numbered marker at line start (SK2's "1. Heat 2
# tablespoons..."). Distinguishes from ingredient lines which use
# "1 large egg" — digit followed by SPACE and letter, not "1." format.
_CLASS_B_NUMBERED_STEP_RE = re.compile(r"^\s*\d+[.)]\s+[A-Za-z]")

# Cooking-verb prefix — a long paragraph starting with one of these
# verbs is a step, not an ingredient. Matches SK1's "Make sauce:" and
# SK3's "Heat a large skillet..." patterns. Case-insensitive so
# lowercase-titled sites still work.
_CLASS_B_STEP_VERBS = (
    "make", "heat", "bring", "combine", "mix", "stir", "cook",
    "preheat", "prepare", "whisk", "add", "pour", "bake", "roast",
    "sauté", "saute", "simmer", "boil", "toss", "arrange", "slide",
    "in a ",     # "In a skillet..."
    "in the ",
)


def _looks_like_class_b_step(line: str) -> bool:
    """Grammar guard for Class B: does this line start a step?"""
    if _CLASS_B_NUMBERED_STEP_RE.match(line):
        return True
    if len(line) < 40:
        return False
    lower = line.lower().lstrip()
    for verb in _CLASS_B_STEP_VERBS:
        if lower.startswith(verb):
            return True
    return False


def _find_class_b_blocks(
    lines: list[str],
) -> tuple[int, int, int, int]:
    """Find (ing_start, ing_end, step_start, step_end) for a Class B recipe.

    Returns (-1, -1, -1, -1) if no anchor found. Called ONLY when
    Class A ``_find_ingredient_block`` returned no match — no explicit
    ``Ingredients`` header exists.

    Algorithm:
    1. Find the first line matching ``_CLASS_B_ANCHOR_RE``.
    2. Skip forward past notes / tips / sub-section headers to find
       the first ingredient-shape line. That's ``ing_start``.
    3. Collect ingredient-shape lines downward (letting sub-section
       headers pass through — they'll be skipped by
       ``_extract_ingredients``) until a step-shape line hits.
       That's ``ing_end`` / ``step_start``.
    4. Steps run from there to the first stop marker.
    """
    anchor = -1
    for idx, line in enumerate(lines):
        if _CLASS_B_ANCHOR_RE.match(line):
            anchor = idx
            break
    if anchor < 0:
        return (-1, -1, -1, -1)

    # Advance to the first ingredient-shape line after the anchor.
    ing_start = -1
    idx = anchor + 1
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped:
            idx += 1
            continue
        if _CLASS_B_NOTE_RE.match(stripped):
            idx += 1
            continue
        if _STOP_MARKER_RE.match(line):
            # Ran off the end of the recipe body without finding an
            # ingredient — Class B gives up.
            return (-1, -1, -1, -1)
        # Sub-section header ("Sauce", "Meatballs") — skip forward
        # looking for the real first ingredient.
        if _CLASS_B_SUBSECTION_RE.match(stripped):
            idx += 1
            continue
        if _looks_like_class_b_step(stripped):
            # Recipe has zero ingredients before the first step — bail.
            return (-1, -1, -1, -1)
        # Any leading digit / fraction / short-descriptor line qualifies
        # as the recipe body's first ingredient. Also accept lines that
        # look like the "About 4 tablespoons olive oil, plus more..."
        # SK2 shape (starts with a determiner + qty word) via
        # ``_looks_like_ingredient``'s general check.
        if _looks_like_ingredient(stripped):
            ing_start = idx
            break
        # Otherwise: skip and keep looking.
        idx += 1

    if ing_start < 0:
        return (-1, -1, -1, -1)

    # Advance to the first step-shape line (or stop marker).
    ing_end = ing_start
    idx = ing_start
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped:
            idx += 1
            continue
        if _STOP_MARKER_RE.match(line):
            ing_end = idx
            break
        if _looks_like_class_b_step(stripped):
            ing_end = idx
            break
        idx += 1
    else:
        ing_end = len(lines)

    # Steps: from ing_end to the first stop marker.
    step_start = ing_end
    step_end = len(lines)
    for j in range(step_start, len(lines)):
        if _STOP_MARKER_RE.match(lines[j]):
            step_end = j
            break

    return (ing_start, ing_end, step_start, step_end)


# ── Name extraction ─────────────────────────────────────────────────


_NAME_NOISE_PREFIXES = (
    "submitted by",
    "author:",
    "by ",
    "updated on",
    "updated ",
    "published on",
    "published ",
    "tested by",
    "cook mode",
    "prevent",
    "keep screen",
    "save recipe",
    "print recipe",
    "email recipe",
    "save to",
    "share this",
    "rate ",
    "rating",
    "my rating",
    "leave a",
    "shop ",
    "jump to",
    "instacart",
    "skip to",
    "search",
    "home »",
    "next video",
    "step ",
    "get the",
    "reviews",
    "photos",
    "ratings",
    "adapted from",
    "from ",
    "recipe video above",
    "recipe notes",
    "description",             # Sally's "Description" section header
    "notes",
    "prep",   # meta labels themselves
    "cook",
    "total",
    "serves",
    "servings",
    "yield",
    "makes",
    "difficulty",
    "cover and edge",
    "sally's baking",
    "half baked",
    "fresh ideas",
    "the ",   # "The New Spanish Table" (Smitten source attribution)
    "simply recipes /",        # SR photographer credit ("Simply Recipes / Morgan Baker")
    "dotdash meredith",        # AllRecipes photographer credit
    "you might also",
    "you may also",
    "related",
    "shop the recipe",
    "tried this recipe",
    "on: ",                    # "Updated on: 02/06/26" → "on: ..."
    "calories",
    "nutritional",
    "next up",
    "next post",
    "previous post",
    "post navigation",
    "my recipe box",
    "recipe of the day",
    "in the kitchen",
    "food news",
    "fresh ideas image",
    "tired of losing recipes",
    "about us",
    "get the magazine",
    "one pot",                  # RecipeTin category breadcrumb
    "beef recipes",
    "iconic dishes",
    "kicky",                    # SR related-post list heading
    "more ",                    # SR "More 20-Minute Pastas..."
    "how to freeze",
    "cover and edge design",
    "sally's baking 101",
    "order today",
    "search",
    "sign up",
    "log in",
    "quick & easy",
)

# Additional exact-line noise (checked as regex on the full stripped
# line — some noise lines are numbers or specific phrases).
_NAME_NOISE_LINE_RE = re.compile(
    r"""
    ^(?:
        \d+(?:\.\d+)?                       # ratings: "4.3", "41"
      | \(\d+\)                             # rating count: "(171)"
      | \d+\s+(?:reviews?|photos?|ratings?|comments?|ingredients?|stars?)  # "114 Reviews"
      | \d+\s*/\s*\d+\s*(?:cup|tbsp|tsp)? # fraction leader "1/2 cup"
      | \(\d+\)\s*
      | \d+\s+ratings?
      | ​                                   # zero-width space
      | \s*
      | .*\s+from\s+\d+\s+reviews?          # "4.7 from 154 reviews"
      | (?:\d+\s+stars?\s*){2,}.*           # "5 Stars 4 Stars 3 Stars ..."
      | \d+\s+comments?\s+on\s+.*           # "383 comments on scallion meatballs..."
    )$
    """,
    re.I | re.VERBOSE,
)

# Breadcrumb line detection. HBH uses "Home » Recipes » <Name>.";
# Sally's uses "Recipes · Cookies · <Name>". We split on either
# separator and take the last non-empty segment.
_BREADCRUMB_SEPARATORS = ("»", "·")


def _looks_like_name_noise(line: str) -> bool:
    """True if the line is definitely NOT a recipe title."""
    s = line.strip()
    if not s:
        return True
    if _NAME_NOISE_LINE_RE.match(s):
        return True
    lower = s.lower()
    for prefix in _NAME_NOISE_PREFIXES:
        if lower.startswith(prefix):
            return True
    return False


def _looks_like_description(line: str) -> bool:
    """True if the line is a long narrative description, not a title."""
    s = line.strip()
    if len(s) > 90:
        return True   # titles cap around 90 chars; longer = story / caption
    if any(marker in s for marker in (". ", "! ", "? ", "; ")):
        return True   # mid-line sentence punctuation
    return False


_CAMEL_ARTIFACT_RE = re.compile(r"[a-z]{2}[A-Z]")


def _looks_like_title(line: str) -> bool:
    """Strict title-shape check for the top-window candidate scan.

    Rules:
    * 8-90 chars long. Titles cap around 60-70 chars; the shortest in
      the corpus is "Mapo Tofu" at 9 chars, so the lower bound is 8.
    * 2-15 words. 2 accepts short real titles ("Mapo Tofu", "Italian
      Meatballs"); 15 rejects sentences.
    * Doesn't start with a digit / fraction glyph (that's an ingredient).
    * Doesn't start with an opening quote character.
    * Doesn't end with sentence punctuation (., !, ?) or a comma.
    * Doesn't contain a parenthesis — those are prose annotations
      ("Preserved black beans (salted black beans)").
    * Doesn't contain a mid-line colon-plus-space — "Three years ago:
      Pecan Sandies..." (SK footer year-list) matches this trap.
    * Doesn't contain a camel-case artifact (two lowercase letters
      followed by an uppercase) — Smitten Kitchen paste collapses
      whitespace at some phrase boundaries ("peppercooking" from
      "pepper" + "cooking").
    * Not flagged by ``_looks_like_description`` (long or mid-sentence
      punctuation).
    """
    s = line.strip()
    if len(s) < 8 or len(s) > 90:
        return False
    words = s.split()
    if len(words) < 2 or len(words) > 15:
        return False
    if s[0].isdigit() or s[0] in _FRACTION_GLYPHS:
        return False
    if s[0] in '"“”':
        return False
    if s[-1] in ".!?,;:":
        return False
    if "(" in s or ")" in s:
        return False
    if ": " in s:
        return False
    if _CAMEL_ARTIFACT_RE.search(s):
        return False
    if _looks_like_description(s):
        return False
    return True


def _extract_name(
    lines: list[str],
    meta_anchor: int,
    ingredient_anchor: int,
) -> str:
    """Three-strategy name extraction.

    1. **Breadcrumb line**: any line in the first 80 that contains ``»``
       or ``·`` — split on the separator and take the last non-empty
       segment. HBH (``Home » Recipes » <Name>.``), Sally's
       (``Recipes · Cookies · <Name>``), and taste.com.au all publish
       clean titles this way. Cheapest + strongest signal when present.
    2. **Top-window longest candidate**: scan lines 5–100 for
       title-shaped lines that aren't nav, noise, or descriptions.
       Pick the LONGEST one. Longest-wins solves the RecipeTin
       ``Fast Prep, Big Flavours`` tagline problem — the site tagline
       is 4 words / 24 chars, the recipe title is 8+ words / 50+ chars.
    3. **Backwards scan from meta anchor**: last-resort fallback for
       fixtures where nothing meaty appears above the meta block.

    Returns "Imported recipe" if all three strategies fail.
    """
    # Strategy 1: breadcrumb.
    for line in lines[:80]:
        stripped = line.strip()
        for sep in _BREADCRUMB_SEPARATORS:
            if sep in stripped:
                parts = [p.strip() for p in stripped.split(sep) if p.strip()]
                if len(parts) >= 2:
                    candidate = parts[-1].rstrip(".")
                    if (candidate
                            and len(candidate.split()) >= 2
                            and not _looks_like_name_noise(candidate)):
                        return candidate
                break   # don't try the other separator on this line

    # Strategy 2: candidate ranking by (occurrence-count, length, position).
    # Real recipe titles have three properties in the paste:
    # * They appear MULTIPLE times (H1 + recipe-card header + byline).
    # * They are LONGER than category breadcrumbs and taglines.
    # * They appear EARLY (in the top window, before the story).
    #
    # Window is bounded by the meta anchor when we found one — never
    # scan past the meta block, because footer nav (which repeats the
    # site tagline) starts appearing after the recipe body.
    window_end = min(120, len(lines))
    if meta_anchor > 20:
        window_end = min(window_end, meta_anchor)
    elif ingredient_anchor > 20:
        window_end = min(window_end, ingredient_anchor)

    candidate_positions: dict[str, int] = {}
    for idx in range(5, window_end):
        line = lines[idx].strip()
        if not line:
            continue
        if _looks_like_name_noise(line):
            continue
        if not _looks_like_title(line):
            continue
        candidate = line.rstrip(".")
        # First position in the window (a title repeated as breadcrumb +
        # H1 + card should record its earliest window position).
        if candidate not in candidate_positions:
            candidate_positions[candidate] = idx

    if candidate_positions:
        text_lower = "\n".join(lines).lower()
        counted = [
            (c, text_lower.count(c.lower()), candidate_positions[c])
            for c in candidate_positions
        ]
        # Require ≥ 2 occurrences — single-occurrence candidates are
        # image alt-text ("Baked casserole with melted cheese chicken
        # rice and vegetables in a dish") or story asides that happen
        # to pass the title-shape filter. Real recipe titles ALWAYS
        # repeat in a paste (H1 + recipe-card header + often a byline).
        counted = [c for c in counted if c[1] >= 2]
        if counted:
            # Rank: length DESC → count DESC → position ASC. SR2 puts
            # "King Ranch Chicken Casserole" (27 char, 3 occurrences)
            # up against the real "Lasso up This Dump-and-Bake Cowgirl
            # Casserole ..." (63 char, 2 occurrences); length first
            # picks the right one. Count breaks ties between similar-
            # length candidates; position is the final tiebreaker.
            counted.sort(key=lambda x: (-len(x[0]), -x[1], x[2]))
            return counted[0][0]

    # Strategy 3: backwards scan from meta.
    anchor = meta_anchor if meta_anchor > 0 else ingredient_anchor
    if anchor > 0:
        for idx in range(anchor - 1, -1, -1):
            line = lines[idx].strip()
            if not line:
                continue
            if _looks_like_name_noise(line):
                continue
            if _looks_like_description(line):
                continue
            return line.rstrip(".")

    return "Imported recipe"


# ── Public API ────────────────────────────────────────────────────────


def parse_recipe_from_text(text: str) -> ImportedRecipeDto:
    """Parse a plain-text recipe blob into an ``ImportedRecipeDto``.

    Input is what a user gets when they hit Ctrl+A / Ctrl+C on a recipe
    website and paste — page nav, story preamble, meta block, ingredient
    list, instructions, footer noise. The parser strips the noise and
    extracts the structured recipe.

    Returns the same ``ImportedRecipeDto`` shape the existing importer
    uses so downstream fuzzy-matching against the user's stock items,
    the preview surface, and the save path all stay wire-compatible.

    Class A (anchored) sites take the ``_find_ingredient_block`` +
    ``_find_steps_block`` path. When Class A finds no ingredient anchor
    (Smitten Kitchen and shape-alikes — no explicit ``Ingredients``
    header exists), the parser falls back to
    ``_find_class_b_blocks``'s grammar-based extraction.
    """
    lines = text.splitlines()

    # Meta block first — used both for values AND to anchor name
    # extraction (we scan backwards from the meta block).
    prep, cook, total = _extract_times(text)
    servings = _extract_servings(text)

    # Anchor: earliest line CONTAINING a meta label (search, not match, so
    # Sally's inline "Author: ... Prep Time: ..." is caught even though
    # the line doesn't start with a label).
    meta_anchor_line = -1
    for idx, line in enumerate(lines):
        if _META_LABEL_RE.search(line):
            meta_anchor_line = idx
            break

    ing_start, ing_end = _find_ingredient_block(lines)
    if ing_start >= 0:
        # Class A path.
        ingredients = _extract_ingredients(lines[ing_start:ing_end])
        step_start, step_end = _find_steps_block(
            lines,
            after=ing_end if ing_end > 0 else 0,
        )
        steps = _extract_steps(lines[step_start:step_end]) if step_start >= 0 else []
    else:
        # Class B fallback.
        b_ing_start, b_ing_end, b_step_start, b_step_end = _find_class_b_blocks(lines)
        if b_ing_start >= 0:
            ingredients = _extract_ingredients(lines[b_ing_start:b_ing_end])
            steps = _extract_steps(lines[b_step_start:b_step_end])
            # Point ingredient_anchor at the class-B start so name
            # extraction can still scan backwards from it if needed.
            ing_start = b_ing_start
        else:
            ingredients = []
            steps = []

    ingredient_anchor = ing_start - 1 if ing_start >= 0 else -1
    name = _extract_name(lines, meta_anchor_line, ingredient_anchor)

    # Flatten steps into a plain instructions string for the ``instructions``
    # field — the existing wire has both structured ``steps`` and a
    # freeform ``instructions`` blob; keep both populated so the SPA's
    # freeform-mode fallback still renders something readable.
    instructions = "\n\n".join(s.text for s in steps) if steps else None

    is_degraded = len(ingredients) < 3

    return ImportedRecipeDto(
        name=name,
        cuisine_id=None,
        cuisine_name=None,
        category_id=None,
        category_name=None,
        difficulty=None,
        servings=servings,
        prep_time_minutes=prep,
        cook_time_minutes=cook,
        instructions=instructions,
        source_url="",   # Chunk 5's endpoint stamps this from the request.
        ingredients=ingredients,
        steps=steps,
        is_degraded=is_degraded,
        total_time_minutes=total,
    )
