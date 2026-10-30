"""USDA FoodData Central bulk-dataset import.

The "download button" nutrition source: fetch a CSV bundle from USDA, parse it,
and populate `NutritionFood` + `NutritionPortion`. Deliberately the *default*
provider, because it's the only one with no strings attached — FDC data is
public domain (CC0), so it can be redistributed, cached and used offline
without attribution or share-alike obligations, unlike Open Food Facts (ODbL).

Only the two generic-food datasets are offered:

  Foundation  ~3.7MB zipped / 32MB unzipped — current, well-curated
  SR Legacy   ~6.7MB zipped / 54MB unzipped — frozen 2018, far broader

Branded Foods is deliberately *not* offered: at 428MB zipped / 2.9GB unzipped
it dwarfs everything else in the app, and packaged goods are better reached by
barcode through Open Food Facts anyway. Generic foods are what recipe
ingredients actually name ("flour", "banana"), which is what the rollup needs.

Runs on a daemon thread with in-memory status, the same shape as the Piper
voice download (`features/tts/voice_provision.py`) — the user starts it, the
admin page polls. Status is a transient UI hint; the durable truth is simply
how many rows the dataset has, which `sources.py` reads back.
"""
import csv
import io
import logging
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, Tuple
from urllib.request import Request, urlopen
from uuid import uuid4

from dora_api.domain.entities.nutrition_food import (
    NUTRITION_SOURCE_USDA_FOUNDATION,
    NUTRITION_SOURCE_USDA_SR_LEGACY,
    NutritionFood,
)
from dora_api.domain.entities.nutrition_portion import NutritionPortion
from dora_api.features.help.version_info import GITHUB_URL
from dora_api.features.nutrition.food_categories import normalise_category
from dora_api.features.nutrition.nutrients import (USDA_NUTRIENT_ATTRS,
                                                   USDA_NUTRIENT_RANK,
                                                   to_float)
from dora_api.persistence.field import EntityField as Field

_LOGGER = logging.getLogger(__name__)

# Release dates are baked into FDC filenames. SR Legacy is frozen ("the final
# release … will not be updated"), so its URL is stable forever; Foundation
# ships a couple of times a year, so *that* URL will eventually 404. Rather
# than add a schema column for it, the start-import endpoint accepts an
# optional `url` override — the admin page exposes it, and a failed download
# says so plainly instead of leaving a dead button.
# Host matters: `www.usda.gov/fdc-datasets/...` is fronted by Akamai and
# answers **403** to programmatic clients regardless of User-Agent (verified
# 2026-08-15 — this is what broke the download button). The FDC origin
# `fdc.nal.usda.gov` serves the same files with no such gate.
_FDC_HOST = "https://fdc.nal.usda.gov/fdc-datasets"
_DEFAULT_URLS = {
    NUTRITION_SOURCE_USDA_FOUNDATION:
        f"{_FDC_HOST}/FoodData_Central_foundation_food_csv_2026-04-30.zip",
    NUTRITION_SOURCE_USDA_SR_LEGACY:
        f"{_FDC_HOST}/FoodData_Central_sr_legacy_food_csv_2018-04.zip",
}

_DATASET_LABELS = {
    NUTRITION_SOURCE_USDA_FOUNDATION: "USDA Foundation Foods",
    NUTRITION_SOURCE_USDA_SR_LEGACY: "USDA SR Legacy",
}

# The nutrients kept, and their USDA names, live in `nutrients.py` (R-002 —
# the live-API path reads the same table). Matched by (name, unit) out of
# `nutrient.csv` rather than by hardcoded FDC nutrient ids: the ids are stable
# in practice but the names are what the file documents, and "Energy" appears
# twice (kcal and kJ), so the unit is load-bearing, not decoration.
_WANTED_NUTRIENTS: Dict[Tuple[str, str], str] = USDA_NUTRIENT_ATTRS

_FETCH_TIMEOUT_SECONDS = 120
# Identify honestly: this call goes to USDA, so pointing the contact URL at
# Open Food Facts (copy-paste from the OFF client) was simply wrong.
_USER_AGENT = f"DashyDora (nutrition dataset import; +{GITHUB_URL})"


@dataclass(frozen=True, slots=True)
class ParsedPortion:
    """A portion as the CSV states it, linked by USDA's `fdc_id` rather than by
    a `NutritionFood.id`.

    Deliberately *not* a `NutritionPortion`: `repository.add()` assigns a fresh
    id to every entity it stores (that's the house convention — the repository
    owns identity), so a food's real id doesn't exist until after it's added.
    Building portions against parse-time ids produced 14,449 rows pointing at
    ids that were never stored, and the whole import died on a foreign-key
    violation at the first flush. The link is resolved in `_replace_dataset`,
    after the foods are in.
    """
    fdc_id: str
    amount: float
    measure: str
    gram_weight: float


@dataclass
class ImportState:
    """In-memory progress for one dataset. `phase` drives the admin page's
    wording; `foods` is what actually landed.

    The counters exist because `phase` alone left the admin page showing an
    indeterminate spinner for the whole run, and an SR Legacy import is
    minutes long — there was no way to tell a slow import from a wedged one.
    Each phase reports the only figure it honestly knows:

      * ``downloading`` — ``bytes_done`` / ``bytes_total``. A real percentage,
        because USDA sends ``Content-Length``. ``bytes_total`` is 0 when the
        server declines to, and the page must fall back to indeterminate
        rather than divide by it.
      * ``parsing`` — ``rows_done`` only. Deliberately *not* a percentage:
        the row count of the archive isn't known until it has been read, and
        inventing a denominator to drive a bar to 90% and stall is the kind
        of fake progress P12 (No-invent) rules out. A live, climbing count is
        honest and answers the actual question ("is it stuck?").
      * ``saving`` — ``foods``/``portions``, already set before the write.
    """
    phase: str = "idle"       # idle | downloading | parsing | saving | done | error
    foods: int = 0
    portions: int = 0
    bytes_done: int = 0
    bytes_total: int = 0      # 0 = the server didn't say
    rows_done: int = 0
    error: Optional[str] = None


_LOCK = threading.Lock()
_STATE: Dict[str, ImportState] = {}


def dataset_label(source: str) -> str:
    return _DATASET_LABELS.get(source, source)


def default_url(source: str) -> str:
    return _DEFAULT_URLS.get(source, "")


def state_for(source: str) -> ImportState:
    with _LOCK:
        return _STATE.get(source, ImportState())


def is_running(source: str) -> bool:
    with _LOCK:
        state = _STATE.get(source)
        return state is not None and state.phase in ("downloading", "parsing", "saving")


def start_import(source: str, url: str | None = None) -> ImportState:
    """Kick off a background import. Re-entrant: a second call while one is in
    flight just returns the running state rather than starting a second fetch."""
    if source not in _DEFAULT_URLS:
        raise ValueError(f"Unknown nutrition dataset '{source}'.")
    with _LOCK:
        existing = _STATE.get(source)
        if existing is not None and existing.phase in ("downloading", "parsing", "saving"):
            return existing
        _STATE[source] = ImportState(phase="downloading")

    thread = threading.Thread(
        target = _run_import,
        args = (source, (url or "").strip() or _DEFAULT_URLS[source]),
        name = f"nutrition-import-{source}",
        daemon = True,
    )
    thread.start()
    return state_for(source)


def _set(source: str, **fields) -> None:
    with _LOCK:
        state = _STATE.setdefault(source, ImportState())
        for key, value in fields.items():
            setattr(state, key, value)


def _run_import(source: str, url: str) -> None:
    # A worker thread has no Flask app context, so it pushes its own. `app` is
    # a module-level Flask instance (there's no create_app factory here).
    # Imported locally so this module stays importable without the app — the
    # parser is unit-tested standalone.
    from dora_api.app import app
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    try:
        _LOGGER.info("Importing nutrition dataset '%s' from %s", source, url)
        payload = _download(
            url,
            on_progress = lambda done, total: _set(
                source, bytes_done=done, bytes_total=total,
            ),
        )

        # `rows_done` resets here rather than carrying the download's figures
        # forward: the page reads one counter per phase, and a stale row count
        # sitting under a fresh "Parsing…" is worse than none.
        _set(source, phase="parsing", rows_done=0)
        foods, portions = parse_fdc_csv_zip(
            payload, source,
            on_rows = lambda seen: _set(source, rows_done=seen),
        )
        if not foods:
            raise ValueError(
                "The download contained no usable foods. Check the URL points "
                "at a FoodData Central *CSV* bundle."
            )

        _set(source, phase="saving", foods=len(foods), portions=len(portions))
        with app.app_context():
            _replace_dataset(SqlAlchemyRepository(), source, foods, portions)

        _set(source, phase="done", error=None)
        _LOGGER.info(
            "Imported nutrition dataset '%s': %d foods, %d portions",
            source, len(foods), len(portions),
        )
    except Exception as exc:  # noqa: BLE001 — any failure becomes UI state
        _LOGGER.exception("Nutrition dataset import failed for '%s'", source)
        message = _friendly_error(str(exc) or exc.__class__.__name__)
        _set(source, phase="error", error=message)


# Every failure here reaches the user as a line of text under a dead button,
# so each one has to say what to do next. Raw urllib strings ("HTTP Error 403:
# Forbidden") tell an admin nothing about which of these situations they're in.
def _friendly_error(message: str) -> str:
    if "HTTP Error 404" in message:
        return (
            "That release URL returned 404, so it has probably been replaced. "
            "Grab the current CSV link from fdc.nal.usda.gov/download-datasets "
            "and paste it in as a custom URL."
        )
    if "HTTP Error 403" in message:
        return (
            "The download was refused (403). If you pasted a custom URL, check "
            "it points at fdc.nal.usda.gov. The www.usda.gov mirror blocks "
            "automated downloads."
        )
    if "urlopen error" in message or "timed out" in message.lower():
        return f"Couldn't reach USDA to download the dataset ({message})."
    return message


# How much has to arrive before the state is updated again. The admin page
# polls on a timer, so ticking more often than it reads is pure lock traffic;
# 256KB is a visible step on a 3.7MB download and a small one on a 55MB.
_DOWNLOAD_TICK_BYTES = 256 * 1024
_DOWNLOAD_CHUNK_BYTES = 64 * 1024


def _download(url: str, on_progress=None) -> bytes:  # noqa: ANN001
    """Fetch the bundle, reporting bytes as they arrive.

    Read in chunks rather than `response.read()` purely so there is something
    to report — the whole payload still lands in memory, which is fine at the
    sizes offered (Branded Foods, the one that wouldn't be, is deliberately
    not on the menu; see the module docstring).
    """
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310
        # Absent on a chunked response, and not to be trusted as a promise —
        # it seeds the bar's denominator, nothing more.
        try:
            total = int(response.headers.get("Content-Length") or 0)
        except ValueError:
            total = 0
        if on_progress is not None:
            on_progress(0, total)

        buffer = io.BytesIO()
        done = 0
        last_reported = 0
        while True:
            chunk = response.read(_DOWNLOAD_CHUNK_BYTES)
            if not chunk:
                break
            buffer.write(chunk)
            done += len(chunk)
            if on_progress is not None and done - last_reported >= _DOWNLOAD_TICK_BYTES:
                on_progress(done, total)
                last_reported = done
        if on_progress is not None:
            # A final exact figure, so a finished download never rests at 97%
            # because the last chunk fell short of the tick.
            on_progress(done, total or done)
        return buffer.getvalue()


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _member(archive: zipfile.ZipFile, basename: str) -> Optional[str]:
    """FDC bundles nest their CSVs one directory deep, and the directory name
    carries the release date — so match on basename, not full path."""
    for name in archive.namelist():
        if name.rsplit("/", 1)[-1].lower() == basename:
            return name
    return None


# Rows between progress reports while parsing. `food_nutrient.csv` is millions
# of rows and dominates the phase, so this is what the counter is really for.
_PARSE_TICK_ROWS = 25_000


class _RowCounter:
    """Cumulative row tally across every CSV in the bundle, reported on a tick.

    Cumulative rather than per-file on purpose: the user is watching one
    "parsing" phase, and a count that reset to zero five times over would read
    as five restarts. Not thread-safe and doesn't need to be — one import runs
    on one worker thread, and `_set` does its own locking.
    """

    def __init__(self, on_tick=None):  # noqa: ANN001
        self.seen = 0
        self._on_tick = on_tick
        self._last = 0

    def count(self) -> None:
        self.seen += 1
        if self._on_tick is not None and self.seen - self._last >= _PARSE_TICK_ROWS:
            self._on_tick(self.seen)
            self._last = self.seen


def _rows(archive: zipfile.ZipFile, member: str, counter=None) -> Iterable[dict]:  # noqa: ANN001
    with archive.open(member) as raw:
        # utf-8-sig: FDC ships a BOM, which would otherwise corrupt the first
        # column name and silently break every lookup against it.
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        for row in csv.DictReader(text):
            if counter is not None:
                counter.count()
            yield row


def parse_fdc_csv_zip(payload: bytes, source: str, on_rows=None):  # noqa: ANN001
    """Pure parse step — bytes in, entities out. Separated from the download
    and the DB write so it can be tested against a small fixture archive.

    `on_rows` is an optional progress sink called with the cumulative row
    count every `_PARSE_TICK_ROWS`; it stays optional so the parser tests keep
    calling this with two arguments and no fake sink.
    """
    counter = _RowCounter(on_rows)
    archive = zipfile.ZipFile(io.BytesIO(payload))

    food_member = _member(archive, "food.csv")
    nutrient_member = _member(archive, "nutrient.csv")
    # Optional, unlike the three below: an older or hand-made bundle without it
    # still imports, its foods simply carry no category. Failing the whole
    # import over the Health Star Rating's input would be the wrong trade —
    # the nutrients are what the app is actually for.
    category_member = _member(archive, "food_category.csv")
    food_nutrient_member = _member(archive, "food_nutrient.csv")
    if not (food_member and nutrient_member and food_nutrient_member):
        raise ValueError(
            "Not a FoodData Central CSV bundle. Expected food.csv, nutrient.csv "
            "and food_nutrient.csv inside the archive."
        )

    # nutrient id → the NutritionFood attribute it feeds.
    nutrient_attr: Dict[str, str] = {}
    nutrient_rank: Dict[str, int] = {}
    for row in _rows(archive, nutrient_member, counter):
        key = (_norm(row.get("name", "")), _norm(row.get("unit_name", "")))
        attr = _WANTED_NUTRIENTS.get(key)
        if attr:
            nutrient_attr[row["id"]] = attr
            nutrient_rank[row["id"]] = USDA_NUTRIENT_RANK[key]

    # USDA food-group id → its description. Read for the Health Star Rating's
    # fvnl test and nothing else (see `food_categories.py`); the file has always
    # been in the bundle and was simply never opened.
    categories: Dict[str, str] = {}
    if category_member:
        for row in _rows(archive, category_member, counter):
            description = normalise_category(row.get("description"))
            if row.get("id") and description:
                categories[row["id"]] = description

    imported_at = datetime.now(timezone.utc)
    foods: Dict[str, NutritionFood] = {}
    for row in _rows(archive, food_member, counter):
        fdc_id = row.get("fdc_id")
        description = (row.get("description") or "").strip()
        if not fdc_id or not description:
            continue
        foods[fdc_id] = NutritionFood(
            id = uuid4(),
            source = source,
            source_ref = fdc_id,
            name = description,
            brand = (row.get("brand_owner") or "").strip() or None,
            barcode = (row.get("gtin_upc") or "").strip() or None,
            food_category = categories.get((row.get("food_category_id") or "").strip()),
            imported_at = imported_at,
        )

    # (fdc_id, attr) → rank of a fallback key whose value is currently held.
    # Only fallback writes are tracked, so this stays small: a preferred
    # (rank 0) value always wins and is never displaced.
    fallback_held: Dict[Tuple[str, str], int] = {}
    for row in _rows(archive, food_nutrient_member, counter):
        nutrient_id = row.get("nutrient_id", "")
        attr = nutrient_attr.get(nutrient_id)
        if not attr:
            continue
        fdc_id = row.get("fdc_id", "")
        food = foods.get(fdc_id)
        if food is None:
            continue
        amount = to_float(row.get("amount"))
        if amount is None:
            continue
        rank = nutrient_rank[nutrient_id]
        held = (fdc_id, attr)
        if rank == 0:
            setattr(food, attr, amount)
            fallback_held.pop(held, None)
        elif getattr(food, attr) is None or rank <= fallback_held.get(held, -1):
            setattr(food, attr, amount)
            fallback_held[held] = rank

    portions = _parse_portions(archive, foods)

    # A food with no energy value can't contribute to a rollup and would just
    # be noise in the picker, so it's dropped rather than stored as a row that
    # looks usable and isn't (P12 No-invent). Its portions go with it.
    usable = [f for f in foods.values() if f.kcal_per_100g is not None]
    usable_refs = {f.source_ref for f in usable}
    portions = [p for p in portions if p.fdc_id in usable_refs]
    return usable, portions


def _parse_portions(archive: zipfile.ZipFile, foods: Dict[str, NutritionFood]) -> list:
    """`food_portion.csv` + `measure_unit.csv` → household measures with gram
    weights. This is the half that makes "2 cups flour" convertible; without it
    only mass-unit ingredients could ever be counted."""
    portion_member = _member(archive, "food_portion.csv")
    if not portion_member:
        return []

    unit_names: Dict[str, str] = {}
    unit_member = _member(archive, "measure_unit.csv")
    if unit_member:
        for row in _rows(archive, unit_member):
            name = (row.get("name") or "").strip()
            # FDC uses the literal string "undetermined" for rows whose measure
            # is carried by `modifier` instead.
            if name and name.lower() != "undetermined":
                unit_names[row["id"]] = name

    portions = []
    for row in _rows(archive, portion_member):
        food = foods.get(row.get("fdc_id", ""))
        gram_weight = to_float(row.get("gram_weight"))
        if food is None or not gram_weight:
            continue
        amount = to_float(row.get("amount")) or 1.0
        measure = (
            unit_names.get(row.get("measure_unit_id", ""), "")
            or (row.get("portion_description") or "").strip()
            or (row.get("modifier") or "").strip()
        )
        if not measure:
            continue
        portions.append(ParsedPortion(
            fdc_id = food.source_ref,
            amount = amount,
            measure = measure,
            gram_weight = gram_weight,
        ))
    return portions


def _replace_dataset(repository, source: str, foods, portions) -> None:  # noqa: ANN001
    """Swap a dataset wholesale: delete this source's rows, insert the new set.

    Whole-replace rather than upsert because a re-import is "take the current
    release", and reconciling ~8k rows one-by-one would be slower and buy
    nothing. StockItem links are `SET NULL` on delete, so a re-import quietly
    unlinks items rather than cascading into the pantry — the honest failure
    mode, and the reason re-import isn't offered casually in the UI.
    """
    existing = repository.get(NutritionFood).where(
        Field(NutritionFood, NutritionFood.Fields.SOURCE).eq(source)
    ).all()
    for food in existing:
        # Portions cascade on the FK; only the foods need removing explicitly.
        repository.remove(food)
    repository.save_changes()

    # Foods are committed **before** portions, and that ordering is load-bearing.
    # `NutritionPortion.nutrition_food_id` is a plain UUID column with no ORM
    # relationship (R-032), so SQLAlchemy's unit of work has no dependency graph
    # to sort by and is free to flush portions first — which it does, and every
    # row then fails the foreign key. The synthetic fixture the parser tests use
    # never caught it because those tests don't touch the database; the real
    # 8k-row SR Legacy import fails on the first flush.
    for food in foods:
        repository.add(food)
    repository.save_changes()

    # Only now do the foods have their real ids — `repository.add()` assigns a
    # fresh one to every entity, discarding whatever it was constructed with.
    # So the parse-time link (USDA's `fdc_id`) is resolved here, against ids
    # that actually exist.
    id_by_fdc_id = {food.source_ref: food.id for food in foods}
    for portion in portions:
        food_id = id_by_fdc_id.get(portion.fdc_id)
        if food_id is None:
            continue
        repository.add(NutritionPortion(
            id = uuid4(),
            nutrition_food_id = food_id,
            amount = portion.amount,
            measure = portion.measure,
            gram_weight = portion.gram_weight,
        ))
    repository.save_changes()
