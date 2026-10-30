"""Direct tests for the shared persistence query machinery (FU-519 item 3,
PROPOSAL_TEST_SUITE_IMPROVEMENTS §5.D).

Covers `SqlAlchemyQueryBuilder.paginate` (slicing math, totals, sort incl. the
case-insensitive string collation and the id tiebreaker), the full
`bool_operation` operator set, `field_map` resolution (mapped name, direct
attribute fallback, unknown-field error), filter-value coercion (int / bool /
datetime / UUID-string), and the BINARY(16) UUID round-trip — all against real
project entities (StockLocation / StockLevel / StockItem) so the real column
types (UUIDType, Boolean, DateTime) are exercised.

Isolation: this file never touches the shared `data/dora.test.db` (owned by
the concurrently-running e2e suite) and never opens `dora_api.app`'s engine.
The DB env vars are overridden to a throwaway temp path *before* any dora_api
import (defence-in-depth against `.env` leaking the dev DB path), and the
module-level `db` handle inside `sqlalchemy_repository` is monkeypatched to a
stub whose `.session` is bound to a private temp-file SQLite engine created
here. `dora_api.app` is still imported *transitively* (the repository module
imports it for `db`, and mapping configuration happens there) — but its lazy
flask-sqlalchemy engine is never created, so no shared file is opened.
"""
import os
import tempfile
from pathlib import Path

# Must run before any dora_api import — dora_api.app resolves the DB URL at
# import time. DORA_DB_URL wins over DORA_DB_PATH, so pin both.
_ISOLATION_DIR = Path(tempfile.mkdtemp(prefix="dora-repo-tests-"))
os.environ["DORA_DB_PATH"] = str(_ISOLATION_DIR / "never-opened.db")
os.environ["DORA_DB_URL"] = f"sqlite:///{(_ISOLATION_DIR / 'never-opened.db').as_posix()}"

from datetime import datetime  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from uuid import UUID  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy import inspect as sa_inspect  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import dora_api.persistence.sqlalchemy_repository as repo_module  # noqa: E402
from dora_api.domain.entities.stock_item import StockItem  # noqa: E402
from dora_api.domain.entities.stock_level import StockLevel  # noqa: E402
from dora_api.domain.entities.stock_location import StockLocation  # noqa: E402
from dora_api.infrastructure.query_options import (FilterClause,  # noqa: E402
                                                   InvalidQueryParameter,
                                                   QueryOptions, SortClause)
from dora_api.persistence.bool_operation import (And, Equal, Not,  # noqa: E402
                                                 Or)
from dora_api.persistence.field import EntityField  # noqa: E402
from dora_api.persistence.sqlalchemy_repository import \
    SqlAlchemyRepository  # noqa: E402
from dora_api.persistence.table_mappings import _mapper_registry  # noqa: E402


def _uid(n: int) -> UUID:
    """Deterministic UUIDs whose BINARY(16) storage sorts in int order —
    makes the id-tiebreaker assertions exact."""
    return UUID(int=n)


# ── Seed dataset ─────────────────────────────────────────────────────────────
# StockLocation — mixed-case names chosen so case-insensitive vs raw-byte
# ordering genuinely differ (uppercase letters sort before all lowercase in a
# byte sort, so a passing NOCASE assertion can't be an accident).
#
#   id      name            kind    parent_id   sequence
#   _uid(1) "Pantry"        zone    None        1
#   _uid(2) "fridge"        zone    None        2
#   _uid(3) "Freezer"       zone    None        3
#   _uid(4) "cellar"        zone    None        4
#   _uid(5) "Top Shelf"     area    _uid(1)     5
#   _uid(6) "bottom shelf"  area    _uid(2)     6
#
# StockItem — for Boolean / DateTime / UUID-FK coercion:
#   _uid(101) "Milk"      is_essential=True   location _uid(1)  updated 2026-01-10
#   _uid(102) "Bread"     is_essential=False  location _uid(2)  updated 2026-02-10
#   _uid(103) "Ice Cream" is_essential=False  location None     updated 2026-03-10

_ALL_LOCATION_NAMES = {"Pantry", "fridge", "Freezer", "cellar", "Top Shelf", "bottom shelf"}
_ID_ORDER = ["Pantry", "fridge", "Freezer", "cellar", "Top Shelf", "bottom shelf"]
_NOCASE_NAME_ASC = ["bottom shelf", "cellar", "Freezer", "fridge", "Pantry", "Top Shelf"]

_NAME = EntityField(StockLocation, StockLocation.Fields.NAME)
_KIND = EntityField(StockLocation, StockLocation.Fields.KIND)
_SEQ = EntityField(StockLocation, StockLocation.Fields.SEQUENCE)
_PARENT = EntityField(StockLocation, StockLocation.Fields.PARENT_ID)
_LOC_ID = EntityField(StockLocation, StockLocation.Fields.ID)

# Mirrors the canonical shape of the routers' field maps (e.g.
# get_stock_items._FIELD_MAP): API/DTO name → EntityField, including an
# underscore-prefixed FK column property.
_LOCATION_FIELD_MAP = {
    "location_name": EntityField(StockLocation, StockLocation.Fields.NAME),
}
_STOCK_ITEM_FIELD_MAP = {
    "stock_location_id": EntityField(StockItem, "_stock_location_id"),
    "is_essential": EntityField(StockItem, StockItem.Fields.IS_ESSENTIAL),
}


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("repo-db") / "repo_tests.db"
    eng = create_engine(f"sqlite:///{db_path.as_posix()}")
    # The project's full table metadata, reached through the mapper (avoids
    # importing dora_api.app directly).
    metadata = sa_inspect(StockLocation).local_table.metadata
    metadata.create_all(eng)

    with Session(eng) as seed:
        zones = [
            StockLocation(name="Pantry", kind="zone", sequence=1, id=_uid(1)),
            StockLocation(name="fridge", kind="zone", sequence=2, id=_uid(2)),
            StockLocation(name="Freezer", kind="zone", sequence=3, id=_uid(3)),
            StockLocation(name="cellar", kind="zone", sequence=4, id=_uid(4)),
        ]
        seed.add_all(zones)
        # Flush zones before areas: parent_id has no mapped relationship, so
        # the unit of work can't order self-referential inserts on its own
        # and the FK pragma is on.
        seed.flush()
        seed.add_all([
            StockLocation(name="Top Shelf", kind="area", parent_id=_uid(1), sequence=5, id=_uid(5)),
            StockLocation(name="bottom shelf", kind="area", parent_id=_uid(2), sequence=6, id=_uid(6)),
        ])
        level = StockLevel(name="Full", sequence=3, id=_uid(201))
        seed.add(level)
        seed.flush()
        seed.add_all([
            StockItem(
                name="Milk", notes=None, stock_group=None,
                stock_level_last_updated=datetime(2026, 1, 10, 8, 0, 0),
                stock_level=level, stock_location=zones[0],
                stocktake_alerts_are_enabled=True, is_essential=True, id=_uid(101),
            ),
            StockItem(
                name="Bread", notes=None, stock_group=None,
                stock_level_last_updated=datetime(2026, 2, 10, 8, 0, 0),
                stock_level=level, stock_location=zones[1],
                stocktake_alerts_are_enabled=True, is_essential=False, id=_uid(102),
            ),
            StockItem(
                name="Ice Cream", notes=None, stock_group=None,
                stock_level_last_updated=datetime(2026, 3, 10, 8, 0, 0),
                stock_level=level, stock_location=None,
                stocktake_alerts_are_enabled=False, is_essential=False, id=_uid(103),
            ),
        ])
        seed.commit()

    yield eng
    eng.dispose()


@pytest.fixture()
def repo(engine, monkeypatch):
    """A SqlAlchemyRepository whose module-level `db` handle is swapped for a
    stub bound to the private test engine — the production code path is
    unchanged, only the session provenance differs."""
    session = Session(engine)
    monkeypatch.setattr(repo_module, "db", SimpleNamespace(session=session))
    yield SqlAlchemyRepository()
    session.rollback()
    session.close()


def _names(entities_or_page) -> list[str]:
    items = getattr(entities_or_page, "items", entities_or_page)
    return [getattr(e, "name", e) for e in items]


def _options(page=1, limit=50, filters=(), sort=None) -> QueryOptions:
    return QueryOptions(filters=tuple(filters), sort=sort, page=page, limit=limit)


_SEQ_ASC = SortClause(field="sequence", direction="asc")


# ── 1. paginate — slicing math / totals ──────────────────────────────────────

@pytest.mark.parametrize(("page", "expected"), [
    pytest.param(1, ["Pantry", "fridge"], id="first-page"),
    pytest.param(2, ["Freezer", "cellar"], id="middle-page"),
    pytest.param(3, ["Top Shelf", "bottom shelf"], id="last-page"),
])
def test__paginate__page_slices_of_two__return_expected_rows_and_total(repo, page, expected):
    result = repo.get(StockLocation).paginate(
        _options(page=page, limit=2, sort=_SEQ_ASC), lambda e: e.name)

    assert _names(result) == expected
    assert result.total == 6


def test__paginate__partial_last_page__returns_remainder_only(repo):
    result = repo.get(StockLocation).paginate(
        _options(page=2, limit=4, sort=_SEQ_ASC), lambda e: e.name)

    assert _names(result) == ["Top Shelf", "bottom shelf"]
    assert result.total == 6


def test__paginate__page_beyond_range__returns_empty_items_with_true_total(repo):
    # Pins the current contract: an out-of-range page is not an error — it
    # yields an empty page whose metadata echoes the request.
    result = repo.get(StockLocation).paginate(
        _options(page=9, limit=2, sort=_SEQ_ASC), lambda e: e.name)

    assert result.items == []
    assert result.total == 6
    assert result.page == 9
    assert result.limit == 2


def test__paginate__limit_exceeding_total__returns_all_rows(repo):
    result = repo.get(StockLocation).paginate(
        _options(page=1, limit=50, sort=_SEQ_ASC), lambda e: e.name)

    assert result.total == 6
    assert len(result.items) == 6


def test__paginate__no_matching_rows__returns_empty_page_with_zero_total(repo):
    result = repo.get(StockLocation).paginate(
        _options(filters=[FilterClause(field="name", operator="eq", value="attic")]),
        lambda e: e.name)

    assert result.items == []
    assert result.total == 0


def test__paginate__filter_applied__total_counts_filtered_rows_not_page(repo):
    # `sequence` is not in any field_map here → exercises the direct-attribute
    # fallback AND the str→int filter-value coercion.
    result = repo.get(StockLocation).paginate(
        _options(page=1, limit=2, sort=_SEQ_ASC,
                 filters=[FilterClause(field="sequence", operator="gt", value="2")]),
        lambda e: e.name)

    assert _names(result) == ["Freezer", "cellar"]
    assert result.total == 4


def test__paginate__page_metadata__echoes_requested_page_and_limit(repo):
    result = repo.get(StockLocation).paginate(
        _options(page=2, limit=3, sort=_SEQ_ASC), lambda e: e.name)

    assert (result.page, result.limit) == (2, 3)


def test__query_options__offset__derives_from_one_based_page_and_limit():
    assert _options(page=1, limit=10).offset == 0
    assert _options(page=3, limit=25).offset == 50


# ── 2. Filter operators — bool_operation matrix ──────────────────────────────

_OPERATOR_CASES = [
    # eq / ne — case_sensitive=False is the default: String columns and str
    # values are both lowered.
    pytest.param(_NAME.eq("pantry"), {"Pantry"}, id="eq-default-case-insensitive"),
    pytest.param(_NAME.eq("PANTRY"), {"Pantry"}, id="eq-default-upper-value-still-matches"),
    pytest.param(_NAME.eq("Pantry", case_sensitive=True), {"Pantry"}, id="eq-case-sensitive-exact-hit"),
    pytest.param(_NAME.eq("pantry", case_sensitive=True), set(), id="eq-case-sensitive-wrong-case-miss"),
    pytest.param(_NAME.ne("pantry"),
                 {"fridge", "Freezer", "cellar", "Top Shelf", "bottom shelf"},
                 id="ne-default-case-insensitive"),
    pytest.param(_NAME.ne("pantry", case_sensitive=True), _ALL_LOCATION_NAMES,
                 id="ne-case-sensitive-wrong-case-excludes-nothing"),
    # Ordering comparisons on an Integer column.
    pytest.param(_SEQ.gt(4), {"Top Shelf", "bottom shelf"}, id="gt"),
    pytest.param(_SEQ.gte(5), {"Top Shelf", "bottom shelf"}, id="gte-inclusive"),
    pytest.param(_SEQ.lt(3), {"Pantry", "fridge"}, id="lt"),
    pytest.param(_SEQ.lte(2), {"Pantry", "fridge"}, id="lte-inclusive"),
    pytest.param(_SEQ.between(2, 4), {"fridge", "Freezer", "cellar"}, id="between-inclusive-both-ends"),
    # Membership.
    pytest.param(_SEQ.in_([1, 4]), {"Pantry", "cellar"}, id="in"),
    pytest.param(_SEQ.not_in([1, 2, 3, 4]), {"Top Shelf", "bottom shelf"}, id="not-in"),
    # Null checks on a nullable UUID FK column.
    pytest.param(_PARENT.is_null(), {"Pantry", "fridge", "Freezer", "cellar"}, id="is-null"),
    pytest.param(_PARENT.is_not_null(), {"Top Shelf", "bottom shelf"}, id="is-not-null"),
    # LIKE operators — always case-insensitive (FU-523). Both column and value
    # are lowered, so an upper-case value matches identically on SQLite (LIKE is
    # ASCII-insensitive) AND Postgres (LIKE is case-sensitive); the two no longer
    # diverge. Compiled-SQL proof of the value-lowering is the separate
    # `test__contains__lowers_both_sides__portable` below.
    pytest.param(_NAME.contains("shelf"), {"Top Shelf", "bottom shelf"}, id="contains-default"),
    pytest.param(_NAME.contains("SHELF"), {"Top Shelf", "bottom shelf"},
                 id="contains-upper-value-still-matches"),
    pytest.param(_NAME.starts_with("fr"), {"Freezer", "fridge"}, id="starts-with-default"),
    pytest.param(_NAME.starts_with("FR"), {"Freezer", "fridge"},
                 id="starts-with-upper-value-still-matches"),
    # LIKE wildcards in the search text match literally, not as wildcards:
    # "op_s" would otherwise match "Top Shelf" via `_` = the space.
    pytest.param(_NAME.contains("%"), set(), id="contains-percent-is-literal"),
    pytest.param(_NAME.contains("op_s"), set(), id="contains-underscore-is-literal"),
    pytest.param(_NAME.contains("op s"), {"Top Shelf"}, id="contains-control-literal-space"),
    pytest.param(_NAME.starts_with("%"), set(), id="starts-with-percent-is-literal"),
    pytest.param(_NAME.starts_with("_ridge"), set(), id="starts-with-underscore-is-literal"),
]


@pytest.mark.parametrize(("condition", "expected"), _OPERATOR_CASES)
def test__where__operator_matrix__returns_expected_rows(repo, condition, expected):
    results = repo.get(StockLocation).all(condition)

    assert set(_names(results)) == expected


def test__contains__lowers_both_sides__portable():
    """FU-523 — Contains/StartsWith are always case-insensitive, and crucially
    the *value* is lowered too (not just the column). SQLite tests can't see the
    difference (its LIKE ignores case), so assert it at the SQL level: the
    compiled clause must lower the column AND emit a lower-cased pattern, so the
    match is identical on Postgres (whose LIKE is case-sensitive)."""
    clause = _NAME.contains("Shelf").to_sqla(None)
    sql = str(clause.compile(compile_kwargs={"literal_binds": True}))

    assert "lower(" in sql.lower()          # column is lowered
    assert "%shelf%" in sql                  # value is lowered into the pattern
    assert "%Shelf%" not in sql              # ...not passed through as-typed


# ── 2b. Not / And / Or composition ───────────────────────────────────────────

def test__where__not__inverts_condition(repo):
    results = repo.get(StockLocation).all(Not(_KIND.eq("zone")))

    assert set(_names(results)) == {"Top Shelf", "bottom shelf"}


def test__where__and__returns_intersection(repo):
    results = repo.get(StockLocation).all(And(_KIND.eq("zone"), _SEQ.gte(3)))

    assert set(_names(results)) == {"Freezer", "cellar"}


def test__where__or__returns_union(repo):
    results = repo.get(StockLocation).all(Or(_NAME.eq("pantry"), _NAME.eq("cellar")))

    assert set(_names(results)) == {"Pantry", "cellar"}


def test__where__operator_overloads__compose_like_combinators(repo):
    condition = (_KIND.eq("area") | _SEQ.lte(1)) & ~_NAME.eq("bottom shelf")

    results = repo.get(StockLocation).all(condition)

    assert set(_names(results)) == {"Top Shelf", "Pantry"}


@pytest.mark.parametrize("combinator", [And, Or])
def test__combinator__fewer_than_two_expressions__raises_value_error(combinator):
    with pytest.raises(ValueError):
        combinator(_NAME.eq("pantry"))


def test__comparison__nested_bool_operation_as_value__raises_value_error():
    condition = Equal(_NAME, _NAME.eq("pantry"))

    with pytest.raises(ValueError):
        condition.to_sqla(_mapper_registry)


# ── 3. field_map resolution ──────────────────────────────────────────────────

def test__paginate__field_map_filter__resolves_api_name_to_entity_field(repo):
    result = repo.get(StockLocation).paginate(
        _options(filters=[FilterClause(field="location_name", operator="ct", value="shelf")]),
        lambda e: e.name,
        field_map=_LOCATION_FIELD_MAP)

    assert set(_names(result)) == {"Top Shelf", "bottom shelf"}
    assert result.total == 2


def test__paginate__field_not_in_map__falls_back_to_direct_attribute(repo):
    # "sequence" is absent from the map but is a mapped column on the root
    # entity → resolved as EntityField(StockLocation, "sequence").
    result = repo.get(StockLocation).paginate(
        _options(filters=[FilterClause(field="sequence", operator="ge", value="5")]),
        lambda e: e.name,
        field_map=_LOCATION_FIELD_MAP)

    assert set(_names(result)) == {"Top Shelf", "bottom shelf"}


def test__paginate__unknown_filter_field__raises_invalid_query_parameter(repo):
    with pytest.raises(InvalidQueryParameter):
        repo.get(StockLocation).paginate(
            _options(filters=[FilterClause(field="bogus", operator="eq", value="x")]),
            lambda e: e.name)


def test__paginate__unknown_sort_field__raises_invalid_query_parameter(repo):
    with pytest.raises(InvalidQueryParameter):
        repo.get(StockLocation).paginate(
            _options(sort=SortClause(field="bogus", direction="asc")),
            lambda e: e.name)


def test__paginate__unsupported_operator__raises_invalid_query_parameter(repo):
    with pytest.raises(InvalidQueryParameter):
        repo.get(StockLocation).paginate(
            _options(filters=[FilterClause(field="name", operator="xx", value="p")]),
            lambda e: e.name)


# ── 3b. Filter-value coercion (str → column python type) ────────────────────

def test__paginate__uuid_string_filter_on_fk_column__matches_binary_uuid(repo):
    # API filter values arrive as strings; the UUIDType column must still
    # match its BINARY(16) storage.
    result = repo.get(StockItem).paginate(
        _options(filters=[FilterClause(
            field="stock_location_id", operator="eq", value=str(_uid(1)))]),
        lambda e: e.name,
        field_map=_STOCK_ITEM_FIELD_MAP)

    assert _names(result) == ["Milk"]
    assert result.total == 1


@pytest.mark.parametrize(("raw", "expected"), [
    pytest.param("true", {"Milk"}, id="true"),
    pytest.param("1", {"Milk"}, id="one"),
    pytest.param("false", {"Bread", "Ice Cream"}, id="false"),
])
def test__paginate__bool_string_filter__coerces_to_boolean(repo, raw, expected):
    result = repo.get(StockItem).paginate(
        _options(filters=[FilterClause(field="is_essential", operator="eq", value=raw)]),
        lambda e: e.name,
        field_map=_STOCK_ITEM_FIELD_MAP)

    assert set(_names(result)) == expected


def test__paginate__datetime_string_filter__coerces_to_datetime(repo):
    result = repo.get(StockItem).paginate(
        _options(filters=[FilterClause(
            field="stock_level_last_updated", operator="gt", value="2026-01-15T00:00:00")]),
        lambda e: e.name)

    assert set(_names(result)) == {"Bread", "Ice Cream"}


# ── 4. Sort ──────────────────────────────────────────────────────────────────

def test__paginate__sort_string_asc__is_case_insensitive(repo):
    # Raw-byte order would be Freezer, Pantry, Top Shelf, bottom shelf,
    # cellar, fridge — so this only passes with the lower() collation.
    result = repo.get(StockLocation).paginate(
        _options(sort=SortClause(field="name", direction="asc")), lambda e: e.name)

    assert _names(result) == _NOCASE_NAME_ASC


def test__paginate__sort_string_desc__reverses_case_insensitive_order(repo):
    result = repo.get(StockLocation).paginate(
        _options(sort=SortClause(field="name", direction="desc")), lambda e: e.name)

    assert _names(result) == list(reversed(_NOCASE_NAME_ASC))


@pytest.mark.parametrize("direction, expected", [
    # Non-null parents first (by parent id), then the four zones with no
    # parent, in id order (the tiebreaker).
    ("asc", ["Top Shelf", "bottom shelf", "Pantry", "fridge", "Freezer", "cellar"]),
    ("desc", ["bottom shelf", "Top Shelf", "Pantry", "fridge", "Freezer", "cellar"]),
])
def test__paginate__sort_nullable_column__puts_nulls_last_both_ways(repo, direction, expected):
    """NULL placement is pinned, not left to the backend (SQLite puts NULL
    first on ASC, Postgres last), so a page reads the same on either."""
    result = repo.get(StockLocation).paginate(
        _options(sort=SortClause(field="parent_id", direction=direction)), lambda e: e.name)
    assert _names(result) == expected


def test__paginate__sort_via_field_map__resolves_mapped_column(repo):
    result = repo.get(StockLocation).paginate(
        _options(sort=SortClause(field="location_name", direction="asc")),
        lambda e: e.name,
        field_map=_LOCATION_FIELD_MAP)

    assert _names(result) == _NOCASE_NAME_ASC


def test__paginate__sort_numeric_desc__orders_by_column_value(repo):
    result = repo.get(StockLocation).paginate(
        _options(sort=SortClause(field="sequence", direction="desc")), lambda e: e.name)

    assert _names(result) == ["bottom shelf", "Top Shelf", "cellar", "Freezer", "fridge", "Pantry"]


def test__paginate__no_sort__orders_by_id_ascending(repo):
    result = repo.get(StockLocation).paginate(_options(), lambda e: e.name)

    assert _names(result) == _ID_ORDER


def test__paginate__equal_sort_keys__tie_broken_by_id_ascending(repo):
    # kind is 'area' for ids 5,6 and 'zone' for ids 1..4 — within each kind
    # the appended id tiebreaker must produce a deterministic order.
    result = repo.get(StockLocation).paginate(
        _options(sort=SortClause(field="kind", direction="asc")), lambda e: e.name)

    assert _names(result) == ["Top Shelf", "bottom shelf", "Pantry", "fridge", "Freezer", "cellar"]


# ── 5. UUID / BINARY(16) round-trip ──────────────────────────────────────────

def test__by_id__uuid_object__round_trips_through_binary_storage(repo):
    entity = repo.get(StockLocation).by_id(_uid(3))

    assert entity is not None
    assert entity.name == "Freezer"
    assert isinstance(entity.id, UUID)
    assert entity.id == _uid(3)


def test__where__eq_uuid_object_on_nullable_fk__matches(repo):
    results = repo.get(StockLocation).all(_PARENT.eq(_uid(1)))

    assert _names(results) == ["Top Shelf"]


def test__where__in_with_uuid_objects__matches_binary_ids(repo):
    results = repo.get(StockLocation).all(_LOC_ID.in_([_uid(2), _uid(4)]))

    assert set(_names(results)) == {"fridge", "cellar"}


# ── count() ──────────────────────────────────────────────────────────────────

def test__count__no_condition__returns_all_rows(repo):
    assert repo.get(StockLocation).count() == 6


def test__count__with_condition__returns_filtered_row_count(repo):
    assert repo.get(StockLocation).count(_KIND.eq("area")) == 2
