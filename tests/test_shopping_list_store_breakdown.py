"""Store breakdown + money-ladder aggregation on the shopping-list totals.

`compute_list_totals` is pure over line DTOs, so the whole plan-face store card
is testable without a database. These pin the rules that are easy to break
silently later: that an unpriced line still counts as an item but contributes
no money, that the catch-all bucket sorts last, and that a breakdown with no
real store in it is suppressed rather than rendered as a single useless row.
"""
from uuid import uuid4

from dora_api.features.shopping_lists.get_shopping_list_detail import (
    ShoppingListLineDto, compute_list_totals)


def _line(
    *,
    price: float | None = None,
    source: str = "historic",
    qty: int | None = 1,
    store_id=None,
    store_name: str | None = None,
    ticked: bool = False,
    deferred: bool = False,
) -> ShoppingListLineDto:
    return ShoppingListLineDto(
        line_id = uuid4(),
        stock_item_id = uuid4(),
        product_id = None,
        stock_item_name = "Item",
        stock_location_id = None,
        stock_location_breadcrumb = [],
        quantity = qty,
        is_ticked = ticked,
        selected_product_id = None,
        sequence = 0,
        is_auto_added = False,
        actual_unit_price = None,
        purchased_store_id = None,
        purchased_store_name = None,
        deferred_by_budget = deferred,
        estimated_unit_price = price,
        estimate_source = source if price is not None else "none",
        resolved_store_id = store_id,
        resolved_store_name = store_name,
    )


def test_subtotals_group_by_resolved_store():
    coles, aldi = uuid4(), uuid4()
    totals = compute_list_totals([
        _line(price = 5.50, qty = 2, store_id = coles, store_name = "Coles"),
        _line(price = 6.50, store_id = coles, store_name = "Coles"),
        _line(price = 9.90, store_id = aldi, store_name = "Aldi"),
    ])

    assert totals.total_price == 27.40
    by_id = {s.store_id: s for s in totals.by_store}
    assert by_id[coles].subtotal == 17.50
    assert by_id[coles].line_count == 2
    assert by_id[aldi].subtotal == 9.90


def test_unpriced_line_counts_as_an_item_but_adds_no_money():
    coles = uuid4()
    totals = compute_list_totals([
        _line(price = 5.00, store_id = coles, store_name = "Coles"),
        _line(price = None, store_id = coles, store_name = "Coles"),
    ])

    bucket = totals.by_store[0]
    assert bucket.line_count == 2, "an unpriced item is still part of that shop"
    assert bucket.priced_line_count == 1, "but the UI must be able to admit the gap"
    assert bucket.subtotal == 5.00


def test_no_store_bucket_sorts_last_even_when_it_is_the_biggest():
    coles = uuid4()
    totals = compute_list_totals([
        _line(price = 1.00, store_id = coles, store_name = "Coles"),
        _line(price = 99.00, store_id = None),
    ])

    assert [s.store_name for s in totals.by_store] == ["Coles", "No store set"]


def test_real_stores_sort_by_spend_descending():
    a, b, c = uuid4(), uuid4(), uuid4()
    totals = compute_list_totals([
        _line(price = 5.00, store_id = a, store_name = "Aldi"),
        _line(price = 50.00, store_id = b, store_name = "Coles"),
        _line(price = 20.00, store_id = c, store_name = "Woolies"),
    ])

    assert [s.store_name for s in totals.by_store] == ["Coles", "Woolies", "Aldi"]


def test_breakdown_is_suppressed_when_no_line_resolved_a_real_store():
    totals = compute_list_totals([
        _line(price = 4.00, store_id = None),
        _line(price = 6.00, store_id = None),
    ])

    assert totals.by_store == [], "a lone 'No store set' row tells the user nothing"
    assert totals.total_price == 10.00, "totals still work without any store data"


def test_deferred_lines_stay_out_of_the_breakdown():
    coles = uuid4()
    totals = compute_list_totals([
        _line(price = 5.00, store_id = coles, store_name = "Coles"),
        _line(price = 99.00, store_id = coles, store_name = "Coles", deferred = True),
    ])

    assert totals.by_store[0].line_count == 1
    assert totals.by_store[0].subtotal == 5.00
    assert totals.line_count == 1


def test_ticked_lines_leave_remaining_but_stay_in_the_store_total():
    coles = uuid4()
    totals = compute_list_totals([
        _line(price = 5.00, store_id = coles, store_name = "Coles", ticked = True),
        _line(price = 7.00, store_id = coles, store_name = "Coles"),
    ])

    assert totals.remaining_price == 7.00
    assert totals.by_store[0].subtotal == 12.00, (
        "the store card answers 'what is this shop worth', not 'what is left'"
    )



# ───── A finished list's money is a record, not a projection ─────────────────
# The receipt face reads these numbers, so an unticked line on a done list must
# not appear in the total or the store split — it is money that was never spent.

def _pair():
    aldi, coles = uuid4(), uuid4()
    return [
        _line(price = 4.00, store_id = aldi, store_name = "Aldi", ticked = True),
        _line(price = 10.00, store_id = coles, store_name = "Coles", ticked = False),
    ]


def test__spent_only__excludes_unticked_lines_from_the_total():
    totals = compute_list_totals(_pair(), spent_only = True)
    assert totals.total_price == 4.00
    # The counts still describe the whole list — the receipt needs to be able to
    # say what it skipped.
    assert totals.line_count == 2 and totals.unticked_count == 1


def test__spent_only__keeps_unbought_stores_out_of_the_breakdown():
    totals = compute_list_totals(_pair(), spent_only = True)
    assert [(b.store_name, b.subtotal, b.line_count) for b in totals.by_store] == [
        ("Aldi", 4.00, 1),
    ]


def test__without_spent_only__an_unticked_line_still_counts():
    # A draft or in-progress list is a projection: the unticked line is money
    # you are still expected to spend.
    totals = compute_list_totals(_pair())
    assert totals.total_price == 14.00
    assert len(totals.by_store) == 2
