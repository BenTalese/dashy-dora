"""Regression test for the budget's definition of "spent".

`period_spent` used to sum *every* line on an archived list. That looks safe —
surely an unbought line has no price? — but it isn't, because
`picked_offer_price` was snapshotted when a line was **added** (State-ownership
Chunk 6; that writer is gone since 2026-09-17, but old lines still carry it), not
when it was ticked. So any line with a
selected product carries a price from the moment it lands on the list, and
finishing a shop with leftovers billed all of them to the household budget.

The visible symptom was two numbers disagreeing about the same shop: the list's
own receipt applies `spent_only` (`compute_list_totals`) and reported $60, while
the budget card and budget history reported $100 — and `period_headroom` fed
that inflated figure to the trim-to-budget optimiser, so the app would trim a
future list to fit money that was never spent.

This is exactly the bar `DORA_VERIFY_TRIAGE.md` sets for writing a test at all:
a stable money-correctness contract, cheap to pin, and expensive to re-check by
hand (you'd have to build a part-picked shop and cross-read two surfaces).

Isolation follows `test_daily_brief_repo.py` / `test_sqlalchemy_repository.py`:
DB env vars are pinned to a throwaway path *before* any dora_api import, and the
repository module's `db` handle is swapped for a stub bound to a private temp
engine — so this never touches the shared e2e database. It uses a real
repository rather than a fake precisely because the thing under test *is* the
query filter; a fake that ignored the predicate would pass with the bug intact.
"""
import os
import tempfile
from pathlib import Path

# Must run before any dora_api import — dora_api.app resolves the DB URL at
# import time. DORA_DB_URL wins over DORA_DB_PATH, so pin both.
_ISOLATION_DIR = Path(tempfile.mkdtemp(prefix="dora-budget-tests-"))
os.environ["DORA_DB_PATH"] = str(_ISOLATION_DIR / "never-opened.db")
os.environ["DORA_DB_URL"] = f"sqlite:///{(_ISOLATION_DIR / 'never-opened.db').as_posix()}"

from datetime import date, datetime, timezone  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from uuid import UUID  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy import inspect as sa_inspect  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import dora_api.persistence.sqlalchemy_repository as repo_module  # noqa: E402
from dora_api.domain.entities.shopping_list import (  # noqa: E402
    SHOPPING_LIST_STATUS_DONE, ShoppingList, ShoppingListLine)
from dora_api.domain.entities.stock_item import StockItem  # noqa: E402
from dora_api.features.budget.budget import period_spent  # noqa: E402
from dora_api.features.reports.spend import (  # noqa: E402
    SavingsCapturedHandler, SpendByCategoryHandler, SpendByStoreHandler)
from dora_api.persistence.sqlalchemy_repository import \
    SqlAlchemyRepository  # noqa: E402


_PERIOD_START = date(2026, 8, 24)
_PERIOD_END = date(2026, 8, 31)
_COMPLETED_AT = datetime(2026, 8, 26, 9, 30, tzinfo=timezone.utc)

_LIST_ID = UUID(int=800)


def _uid(n: int) -> UUID:
    return UUID(int=n)


def _line(
    n: int,
    *,
    is_ticked: bool,
    actual_unit_price: float | None = None,
    picked_offer_price: float | None = None,
    quantity: int = 1,
    deferred_by_budget: bool = False,
) -> ShoppingListLine:
    return ShoppingListLine(
        id=_uid(n),
        shopping_list_id=_LIST_ID,
        stock_item_id=_uid(500 + n),
        quantity=quantity,
        is_ticked=is_ticked,
        actual_unit_price=actual_unit_price,
        picked_offer_price=picked_offer_price,
        deferred_by_budget=deferred_by_budget,
    )


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("budget-db") / "budget_tests.db"
    eng = create_engine(f"sqlite:///{db_path.as_posix()}")
    sa_inspect(ShoppingListLine).local_table.metadata.create_all(eng)

    with Session(eng) as seed:
        # `ShoppingListLine.stock_item_id` is a real FK and SQLite enforces it
        # (app.py sets `PRAGMA foreign_keys=ON` on every connection), so the
        # anchors have to exist. Bare items: this suite is about one money
        # query, and StockItem's own relationships are all nullable.
        seed.add_all([
            StockItem(
                id=_uid(500 + n), name=f"Budget item {n}", notes=None,
                stock_group=None, stock_level=None, stock_location=None,
                stock_level_last_updated=datetime(2026, 8, 20, tzinfo=timezone.utc),
                stocktake_alerts_are_enabled=False,
            )
            for n in range(1, 6)
        ])
        seed.add(ShoppingList(
            id=_LIST_ID,
            name="Part-picked shop",
            created_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
            status=SHOPPING_LIST_STATUS_DONE,
            completed_at=_COMPLETED_AT,
        ))
        seed.flush()
        seed.add_all([
            # Bought, till price typed: $10.
            _line(1, is_ticked=True, actual_unit_price=10.0),
            # Bought, no till price — falls back to the offer snapshot: $20.
            _line(2, is_ticked=True, picked_offer_price=20.0),
            # NOT bought, but carries an add-time offer snapshot. This is the
            # line the old query billed to the budget.
            _line(3, is_ticked=False, picked_offer_price=40.0),
            # NOT bought, and set aside by the trim optimiser — doubly excluded.
            _line(4, is_ticked=False, picked_offer_price=25.0,
                  deferred_by_budget=True),
        ])
        seed.commit()

    yield eng
    eng.dispose()


@pytest.fixture()
def repo(engine, monkeypatch):
    session = Session(engine)
    monkeypatch.setattr(repo_module, "db", SimpleNamespace(session=session))
    yield SqlAlchemyRepository()
    session.rollback()
    session.close()


def test__period_spent__counts_only_ticked_lines(repo):
    """$10 + $20. The unticked $40 line has a price — that's the whole trap —
    and it must not be spend."""
    assert period_spent(_PERIOD_START, _PERIOD_END, repo) == pytest.approx(30.0)


def test__period_spent__multiplies_by_quantity(repo, engine):
    """Guards the arithmetic the filter sits in front of, so a future edit
    can't quietly drop the quantity factor while still passing the filter
    test above."""
    with Session(engine) as extra:
        extra.add(_line(5, is_ticked=True, actual_unit_price=3.0, quantity=4))
        extra.commit()
    try:
        assert period_spent(_PERIOD_START, _PERIOD_END, repo) == pytest.approx(42.0)
    finally:
        with Session(engine) as cleanup:
            cleanup.query(ShoppingListLine).filter(
                ShoppingListLine.id == _uid(5)
            ).delete()
            cleanup.commit()


def test__period_spent__ignores_shops_completed_outside_the_window(repo):
    """The window is half-open: a shop completed on the period's end date
    belongs to the *next* period, not this one."""
    assert period_spent(date(2026, 8, 31), date(2026, 9, 7), repo) == 0.0


def test__spend_totals_agree_across_budget_and_reports(repo, engine):
    """Finalisation 12-R10: the budget and every Reports spend card read one
    definition of "bought" (`_line_price.spend_lines`), so on one window they
    report one total. A ticked line the trim optimiser deferred is not spend
    on any of them."""
    deferred = ShoppingListLine(
        id=_uid(6), shopping_list_id=_LIST_ID, stock_item_id=_uid(505),
        quantity=1, is_ticked=True, actual_unit_price=7.0, deferred_by_budget=True,
    )
    with Session(engine) as extra:
        extra.add(deferred)
        extra.commit()
    try:
        since = datetime(2026, 8, 24, tzinfo=timezone.utc)
        budget_total = period_spent(_PERIOD_START, _PERIOD_END, repo)
        by_store = SpendByStoreHandler(repo).handle(since)
        _rows, by_category = SpendByCategoryHandler(repo).handle(since)
        savings = SavingsCapturedHandler(repo).handle(since)

        assert budget_total == pytest.approx(30.0)
        assert sum(r.spend for r in by_store.rows) == pytest.approx(budget_total)
        assert by_category == pytest.approx(budget_total)
        assert savings["total_spent"] == pytest.approx(budget_total)
    finally:
        with Session(engine) as cleanup:
            cleanup.query(ShoppingListLine).filter(
                ShoppingListLine.id == _uid(6)
            ).delete()
            cleanup.commit()
