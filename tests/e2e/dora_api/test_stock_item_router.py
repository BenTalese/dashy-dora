from uuid import uuid4

import pytest
import requests

from dora_api.features.stock_items.create_stock_item import \
    CreateStockItemRequest
from dora_api.features.stock_items.update_stock_item import \
    UpdateStockItemRequest
from tests.e2e.dora_api._error_assertions import domain_err, validation_err
from tests.support import is_valid_datetime, is_valid_uuid

#region ---------------- setup ----------------

# list endpoints take query options on the query string and return a
# `{items, total, page, limit}` envelope; datetimes serialise as ISO 8601
# (ADR-007); the StockItem DTO grew to the server-owned status fields; query-
# option errors come back via `bad_request(str(exc))` (message in `title`);
# create echoes the created resource's DTO (so `stock_item_id`, not `id`).
# The seed is now a ~20-item pantry. Seed-coupled assertions check invariants
# (sortedness, stable alphabetical extremes, known seeded items) rather than a
# brittle full golden ordering that breaks whenever the seed grows.

base_route = 'http://localhost:5170/api/stock-items'

# The full server-owned DTO for a stock item.
EXPECTED_KEYS = {
    'name',
    'stock_item_id',
    'stock_level_id',
    'stock_level_sequence',
    'is_out_of_stock',
    'is_low_stock',
    'needs_restock',
    'stock_location_id',
    'stock_group_id',
    'stock_level_last_updated',
    'expiry_date',
    'is_essential',
    'is_open',
    'opened_on',
    'needs_attention',
    'attention_severity',
    'attention_kinds',
    'attention_rank',
    'linked_product_count',
}


def _items(query: str = ''):
    return requests.get(f'{base_route}{query}').json()['items']


def _first(query: str):
    return _items(query)[0]


@pytest.fixture
def stock_level_id():
    return requests.get('http://localhost:5170/api/stock-levels').json()['items'][0]['stock_level_id']


@pytest.fixture
def stock_location_id():
    return requests.get('http://localhost:5170/api/stock-locations').json()['items'][0]['stock_location_id']

#endregion setup

#region ---------------- create_stock_item tests ----------------


def test__create_stock_item__CreatingStockItemWithAllAttributes__StockItemCreated(api, stock_level_id, stock_location_id):
    _StockItemRequest = CreateStockItemRequest(
        name = 'Peters Neopolitan Ice Cream',
        stock_level_id = stock_level_id,
        stock_location_id = stock_location_id
    )

    _Response = requests.post(base_route, json = _StockItemRequest.model_dump(mode="json"))

    assert _Response.status_code == 201
    assert _Response.headers['Content-Type'] == 'application/json'
    assert '/api/stock-items?filter=stock_item_id:eq:' in _Response.headers['location']
    # The create response now echoes the created resource's DTO.
    assert is_valid_uuid(_Response.json()['stock_item_id'])
    assert _Response.json()['name'] == 'Peters Neopolitan Ice Cream'


def test__create_stock_item__CreatingStockItemWithIncorrectDataTypes__CannotBeDeserialised(api):
    _Request = {
        "name": True,
        "stock_level_id": 5,
        "stock_location_id": "aaa"
    }

    _Response = requests.post(base_route, json = _Request)
    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "name": [validation_err("string_type", "Input should be a valid string")],
            "stock_level_id": [validation_err("uuid_type", "UUID input should be a string, bytes or UUID object")],
            "stock_location_id": [validation_err("uuid_parsing", "Input should be a valid UUID, invalid length: expected length 32 for simple format, found 3")]
        },
        "status": 400,
        "title": "Malformed request.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1"
    }


def test__create_stock_item__CreatingStockItemWithOnlyRequiredAttributes__StockItemCreated(api, stock_level_id):
    _StockItemRequest = CreateStockItemRequest(
        name = "Freddo Brownie Ice Cream",
        stock_level_id = stock_level_id
    )

    _Response = requests.post(base_route, json = _StockItemRequest.model_dump(mode='json'))

    assert _Response.status_code == 201
    assert _Response.headers['Content-Type'] == 'application/json'
    assert is_valid_uuid(_Response.json()['stock_item_id'])


def test__create_stock_item__StockItemAlreadyExists__IsBusinessRuleViolation(api, stock_level_id, stock_location_id):
    # FU-169 Phase 2 — self-contained after per-test DB rollback: seed the
    # duplicate before testing the duplicate-detection response.
    requests.post(base_route, json=CreateStockItemRequest(
        name='Peters Neopolitan Ice Cream',
        stock_level_id=stock_level_id,
        stock_location_id=stock_location_id,
    ).model_dump(mode='json'))
    _StockItemRequest = CreateStockItemRequest(
        name = 'PeTers NeoPOLitan IcE CrEam',
        stock_level_id = stock_level_id,
        stock_location_id = stock_location_id
    )

    _Response = requests.post(base_route, json = _StockItemRequest.model_dump(mode='json'))

    assert _Response.status_code == 422
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {
            '': [domain_err("A stock item with the name 'PeTers NeoPOLitan IcE CrEam' already exists.")],
        },
       'status': 422,
       'title': 'Business rule violation.',
       'type': 'https://datatracker.ietf.org/doc/html/rfc4918#section-11.2',
    }


def test__create_stock_item__EmptyRequest__IsRequiredInputsValidationFailure(api):
    _Response = requests.post(base_route, json = {})

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {
            'name': [validation_err("missing", "Field required")],
            'stock_level_id': [validation_err("missing", "Field required")]
        },
       'status': 400,
       'title': 'Malformed request.',
       'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__create_stock_item__StockLevelDoesNotExist__IsEntityExistenceFailure(api):
    _FakeID = uuid4()
    _StockItemRequest = CreateStockItemRequest(
        name = 'Halo Top Ice Cream',
        stock_level_id = _FakeID
    )

    _Response = requests.post(base_route, json = _StockItemRequest.model_dump(mode='json'))

    assert _Response.status_code == 422
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {
            'stock_level_id': [domain_err(f"StockLevel with the ID '{_FakeID}' was not found.")]
        },
       'status': 422,
       'title': 'Entity was not found.',
       'type': 'https://datatracker.ietf.org/doc/html/rfc4918#section-11.2',
    }


def test__create_stock_item__StockLocationDoesNotExist__IsEntityExistenceFailure(api, stock_level_id):
    _FakeID = uuid4()
    _StockItemRequest = CreateStockItemRequest(
        name = 'Halo Top Ice Cream',
        stock_level_id = stock_level_id,
        stock_location_id = _FakeID
    )

    _Response = requests.post(base_route, json = _StockItemRequest.model_dump(mode='json'))

    assert _Response.status_code == 422
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {
            'stock_location_id': [domain_err(f"StockLocation with the ID '{_FakeID}' was not found.")]
        },
       'status': 422,
       'title': 'Entity was not found.',
       'type': 'https://datatracker.ietf.org/doc/html/rfc4918#section-11.2',
    }


def test__create_stock_item__EmptyName__IsBadRequest(api, stock_level_id):
    _Request = {
        "name": "",
        "stock_level_id": str(stock_level_id)
    }

    _Response = requests.post(base_route, json=_Request)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert 'name' in _Response.json()['errors']


def test__create_stock_item__NameExceedsMaxLength__IsBadRequest(api, stock_level_id):
    # Codex P1 — a 256+ char name must be a clean validation failure
    # (max_length=255 mirrors the String(255) column), not a DB-layer 500 on
    # Postgres (SQLite would silently accept it).
    _Request = {"name": "x" * 256, "stock_level_id": str(stock_level_id)}

    _Response = requests.post(base_route, json=_Request)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert 'name' in _Response.json()['errors']


def test__create_stock_item__WhitespaceOnlyName__IsBadRequest(api, stock_level_id):
    # Codex P2 — "   " must not be storable; it strips to "" at the request
    # boundary and fails min_length.
    _Request = {"name": "   ", "stock_level_id": str(stock_level_id)}

    _Response = requests.post(base_route, json=_Request)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert 'name' in _Response.json()['errors']


def test__create_stock_item__NameWithSurroundingWhitespace__IsTrimmedAndDeduped(api, stock_level_id):
    # Codex P2 — "  Milk  " must be trimmed server-side AND collide with an
    # existing "Milk" via the case-insensitive duplicate check, rather than
    # slipping through as a visually-identical duplicate. The 422 proves the
    # trim happened (without it, the leading/trailing spaces would dodge the
    # match and create a 201).
    _First = requests.post(base_route, json={
        "name": "Milk", "stock_level_id": str(stock_level_id),
    })
    assert _First.status_code == 201

    _Second = requests.post(base_route, json={
        "name": "  Milk  ", "stock_level_id": str(stock_level_id),
    })

    assert _Second.status_code == 422


def test__create_stock_item__ExtraAttributes__IsBadRequest(api, stock_level_id):
    _Request = {
        "name": "Some Stock Item",
        "stock_level_id": str(stock_level_id),
        "poopusgoopus": "aaaa"
    }

    _Response = requests.post(base_route, json=_Request)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "poopusgoopus": [validation_err("extra_forbidden", "Extra inputs are not permitted")]
        },
        "status": 400,
        "title": "Malformed request.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1"
    }


def test__create_stock_item__NullStockLocationId__StockItemCreatedWithNoLocation(api, stock_level_id):
    _StockItemRequest = CreateStockItemRequest(
        name="Null Location Stock Item",
        stock_level_id=stock_level_id,
        stock_location_id=None
    )

    _Response = requests.post(base_route, json=_StockItemRequest.model_dump(mode="json"))

    assert _Response.status_code == 201
    _CreatedItem = _first('?filter=name:ct:Null Location')
    assert _CreatedItem['stock_location_id'] is None


#endregion create_stock_item tests

#region ---------------- get_stock_items tests ----------------


def test__get_stock_items__GettingStockItem__GetsAllExpectedAttributes(api):
    _StockItem = _first('?filter=name:ct:Brazil')

    assert _StockItem['name'] == 'Brazil Nuts'
    assert is_valid_uuid(_StockItem['stock_item_id']) is True
    assert is_valid_uuid(_StockItem['stock_level_id']) is True
    assert is_valid_datetime(_StockItem['stock_level_last_updated']) is True
    assert _StockItem.keys() == EXPECTED_KEYS


def test__get_stock_items__GettingAllStockItems__GetsAllStockItems(api):
    _Response = requests.get(f'{base_route}?limit=500')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    _Body = _Response.json()
    # Under a generous limit, every row is returned, so total == page size.
    assert _Body['total'] == len(_Body['items'])
    # At least the full seed (20 items); more if create tests ran first.
    assert _Body['total'] >= 20
    _Names = {i['name'] for i in _Body['items']}
    assert {'Brazil Nuts', 'Vanilla Ice Cream', 'Barilla Pasta'} <= _Names


def test__get_stock_items__FilteringByName__GetsSingleMatchingStockItem(api):
    _Response = requests.get(f'{base_route}?filter=name:ct:Kensington')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    _Items = _Response.json()['items']
    assert len(_Items) == 1
    assert 'Kensington' in _Items[0]['name']


def test__get_stock_items__FilteringOnNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?filter=stock_item_name:eq:Brazil')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Field 'stock_item_name' is not filterable on 'StockItem'.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_stock_items__FilteringForStockItemThatDoesNotExist__EmptyResult(api):
    _Response = requests.get(f'{base_route}?filter=stock_item_id:eq:{uuid4()}')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'] == []
    assert _Response.json()['total'] == 0


def test__get_stock_items__FilteringWithUnsupportedOperator__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?filter=stock_item_id:xx:{uuid4()}')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Unsupported filter operator 'xx'. Supported: ct, eq, ge, gt, le, lt, ne.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_stock_items__SortingByNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?sort=stockcode:desc')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Field 'stockcode' is not filterable on 'StockItem'.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_stock_items__SortingByNameAscending__StockItemsSortedByNameAscending(api):
    _Names = [i['name'] for i in _items('?sort=name:asc&limit=500')]

    # Sortedness is the robust invariant — exact positions aren't, because
    # other suites create stock items into the shared DB. The API sorts
    # case-insensitively (NOCASE collation), so compare with `key=str.lower`.
    assert _Names == sorted(_Names, key=str.lower)
    assert 'Brazil Nuts' in _Names


def test__get_stock_items__SortingByNameDescending__StockItemsSortedByNameDescending(api):
    _Names = [i['name'] for i in _items('?sort=name:desc&limit=500')]

    assert _Names == sorted(_Names, key=str.lower, reverse=True)
    assert 'Brazil Nuts' in _Names


def test__get_stock_items__GettingTwoStockItemsPerPage__GetsPageOfTwoStockItems(api):
    _Response = requests.get(f'{base_route}?sort=name:asc&page=1&limit=2')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    _Items = _Response.json()['items']
    assert len(_Items) == 2
    # Exact names aren't stable — other suites create stock items into the
    # shared DB (and the API sorts case-insensitively, NOCASE collation) — so
    # assert page 1 is the first two of the full ascending sort, not specific
    # seeded names. Same robustness rationale as the sort tests above.
    _AllNames = [i['name'] for i in _items('?sort=name:asc&limit=500')]
    assert [i['name'] for i in _Items] == _AllNames[:2]


def test__get_stock_items__GettingSecondPage__GetsSecondPageOfStockItems(api):
    _Page1 = _items('?sort=name:asc&page=1&limit=2')
    _Page2 = _items('?sort=name:asc&page=2&limit=2')

    assert len(_Page2) == 2
    # Pages don't overlap and continue the ascending order.
    _Page1Ids = {i['stock_item_id'] for i in _Page1}
    _Page2Ids = {i['stock_item_id'] for i in _Page2}
    assert _Page1Ids.isdisjoint(_Page2Ids)
    assert _Page2[0]['name'] >= _Page1[-1]['name']


# FU-169 Phase 2 — parametrized pagination-validation matrix.
@pytest.mark.parametrize(
    "query,invalid_field",
    [
        ("page=true&limit=2", "page"),
        ("page=1&limit=true", "limit"),
    ],
    ids=["page-is-not-integer", "limit-is-not-integer"],
)
def test__get_stock_items__pagination_value_is_not_integer__IsBadRequest(api, query, invalid_field):
    _Response = requests.get(f'{base_route}?{query}')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': f"'{invalid_field}' must be an integer.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_stock_items__PageWithoutLimit__DefaultsLimit(api):
    # page/limit are now independently optional (limit defaults to 50).
    _Response = requests.get(f'{base_route}?page=1')

    assert _Response.status_code == 200
    assert _Response.json()['page'] == 1
    assert _Response.json()['limit'] == 50


def test__get_stock_items__LimitWithoutPage__DefaultsPage(api):
    _Response = requests.get(f'{base_route}?limit=1')

    assert _Response.status_code == 200
    assert _Response.json()['page'] == 1
    assert _Response.json()['limit'] == 1
    assert len(_Response.json()['items']) == 1


def test__get_stock_items__FilteringSortingAndPagingStockItems__GetsMatchingStockItems(api):
    _Response = requests.get(f'{base_route}?filter=name:ct:Brazil&sort=name:asc&page=1&limit=1')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    _Items = _Response.json()['items']
    assert _Items[0]['name'] == 'Brazil Nuts'
    assert len(_Items) == 1


#endregion get_stock_items tests

#region ---------------- update_stock_item tests ----------------


def test__update_stock_item__EmptyUpdate__StockItemUnaffected(api):
    _StockItemToUpdate = _first('?filter=name:ct:Crispy')
    _PatchResponse = requests.patch(f"{base_route}/{_StockItemToUpdate['stock_item_id']}", json = {})
    _StockItemAfterPatchOperation = _first(f"?filter=stock_item_id:eq:{_StockItemToUpdate['stock_item_id']}")

    assert _PatchResponse.status_code == 204
    assert _PatchResponse.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert _StockItemToUpdate == _StockItemAfterPatchOperation


def test__update_stock_item__UpdatingAllAttributes__AllAttributesUpdated(api, stock_level_id, stock_location_id):
    _StockItemToUpdate = _first('?filter=name:ct:Crispy')
    _OriginalLastUpdated = _StockItemToUpdate['stock_level_last_updated']

    _StockItemRequest = UpdateStockItemRequest(
        name = "Old Soggy Chips",
        stock_level_id = stock_level_id,
        stock_location_id = stock_location_id
    ).model_dump(mode = "json")

    _PatchResponse = requests.patch(f"{base_route}/{_StockItemToUpdate['stock_item_id']}", json = _StockItemRequest)
    _After = _first(f"?filter=stock_item_id:eq:{_StockItemToUpdate['stock_item_id']}")

    assert _PatchResponse.status_code == 204
    assert _PatchResponse.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert _After['name'] == 'Old Soggy Chips'
    assert _After['stock_level_id'] == str(stock_level_id)
    assert _After['stock_location_id'] == str(stock_location_id)
    assert _After['stock_level_last_updated'] != _OriginalLastUpdated


def test__update_stock_item__StockItemDoesNotExist__StockItemNotFound(api):
    _RandomID = uuid4()
    _Response = requests.patch(f"{base_route}/{_RandomID}", json = {})

    assert _Response.status_code == 404
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": f"StockItem with the ID '{_RandomID}' was not found.",
        "errors": {},
        "status": 404,
        "title": "Entity was not found.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4"
    }


def test__update_stock_item__OtherStockItemHasSameName__CannotUpdateToDuplicateName(api):
    _StockItemToUpdate = _first('?filter=name:ct:Kensington')

    _StockItemRequest = UpdateStockItemRequest(name = 'super AWESOME pizza').model_dump(exclude_unset=True)

    _PatchResponse = requests.patch(f"{base_route}/{_StockItemToUpdate['stock_item_id']}", json = _StockItemRequest)

    assert _PatchResponse.status_code == 422
    assert _PatchResponse.headers['Content-Type'] == 'application/problem+json'
    assert _PatchResponse.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            '': [domain_err("A stock item with the name 'super AWESOME pizza' already exists.")]
        },
        "status": 422,
        "title": "Business rule violation.",
        "type": "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2"
    }


def test__update_stock_item__UpdatingNameOnly__OnlyNameChanges(api):
    _StockItemToUpdate = _first('?filter=name:ct:Kensington')
    _OriginalStockLevelId = _StockItemToUpdate['stock_level_id']
    _OriginalStockLevelLastUpdated = _StockItemToUpdate['stock_level_last_updated']

    _PatchRequest = UpdateStockItemRequest(name="Kensington Pride Mangoes Renamed").model_dump(exclude_unset=True)
    _PatchResponse = requests.patch(f"{base_route}/{_StockItemToUpdate['stock_item_id']}", json=_PatchRequest)
    _After = _first(f"?filter=stock_item_id:eq:{_StockItemToUpdate['stock_item_id']}")

    assert _PatchResponse.status_code == 204
    assert _After['name'] == 'Kensington Pride Mangoes Renamed'
    assert _After['stock_level_id'] == _OriginalStockLevelId
    assert _After['stock_level_last_updated'] == _OriginalStockLevelLastUpdated


def test__update_stock_item__UpdatingStockLevelOnly__StockLevelLastUpdatedChanges(api, stock_level_id):
    _StockItemToUpdate = _first('?filter=name:ct:Brazil')
    _OriginalStockLevelLastUpdated = _StockItemToUpdate['stock_level_last_updated']

    _PatchRequest = UpdateStockItemRequest(stock_level_id=stock_level_id).model_dump(mode="json", exclude_unset=True)
    _PatchResponse = requests.patch(f"{base_route}/{_StockItemToUpdate['stock_item_id']}", json=_PatchRequest)
    _After = _first(f"?filter=stock_item_id:eq:{_StockItemToUpdate['stock_item_id']}")

    assert _PatchResponse.status_code == 204
    assert _After['stock_level_id'] == str(stock_level_id)
    assert _After['stock_level_last_updated'] != _OriginalStockLevelLastUpdated
    assert _After['name'] == _StockItemToUpdate['name']


def test__update_stock_item__EmptyName__IsBadRequest(api):
    _StockItemToUpdate = _first('?filter=name:ct:Brazil')

    _PatchRequest = {"name": ""}
    _PatchResponse = requests.patch(f"{base_route}/{_StockItemToUpdate['stock_item_id']}", json=_PatchRequest)

    assert _PatchResponse.status_code == 400
    assert _PatchResponse.headers['Content-Type'] == 'application/problem+json'
    assert 'name' in _PatchResponse.json()['errors']


def test__update_stock_item__ExtraAttributes__IsBadRequest(api):
    _StockItemToUpdate = _first('?filter=name:ct:Brazil')

    _PatchResponse = requests.patch(
        f"{base_route}/{_StockItemToUpdate['stock_item_id']}",
        json={"name": "Brazil Nuts", "poopusgoopus": "aaaa"}
    )

    assert _PatchResponse.status_code == 400
    assert _PatchResponse.headers['Content-Type'] == 'application/problem+json'
    assert _PatchResponse.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "poopusgoopus": [validation_err("extra_forbidden", "Extra inputs are not permitted")]
        },
        "status": 400,
        "title": "Malformed request.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1"
    }


#endregion update_stock_item tests

#region ---------------- delete_stock_item tests ----------------


def test__delete_stock_item__DeletingStockItem__StockItemDeleted(api):
    _StockItemID = _first('?filter=name:ct:Pizza')['stock_item_id']
    _Response = requests.delete(f"{base_route}/{_StockItemID}")

    assert _Response.status_code == 204
    assert _Response.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert _items(f'?filter=stock_item_id:eq:{_StockItemID}') == []


def test__delete_stock_item__StockItemDoesNotExist__StockItemNotFound(api):
    _RandomID = uuid4()
    _Response = requests.delete(f"{base_route}/{_RandomID}")

    assert _Response.status_code == 404
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": f"StockItem with the ID '{_RandomID}' was not found.",
        "errors": {},
        "status": 404,
        "title": "Entity was not found.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4"
    }


def test__delete_stock_item__DeletingAlreadyDeletedStockItem__StockItemNotFound(api):
    """Deleting the same item twice should return 404 on the second attempt."""
    _StockItemRequest = CreateStockItemRequest(
        name="Item To Delete Twice",
        stock_level_id=requests.get('http://localhost:5170/api/stock-levels').json()['items'][0]['stock_level_id']
    )
    _CreateResponse = requests.post(base_route, json=_StockItemRequest.model_dump(mode="json"))
    _StockItemId = _CreateResponse.json()['stock_item_id']

    requests.delete(f"{base_route}/{_StockItemId}")
    _SecondDeleteResponse = requests.delete(f"{base_route}/{_StockItemId}")

    assert _SecondDeleteResponse.status_code == 404
    assert _SecondDeleteResponse.headers['Content-Type'] == 'application/problem+json'
    assert _SecondDeleteResponse.json() == {
        "detail": f"StockItem with the ID '{_StockItemId}' was not found.",
        "errors": {},
        "status": 404,
        "title": "Entity was not found.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4"
    }


# ── C-1b.5 — detail DTO surfaces lifecycle inputs (INV-7) ───────────


def test__get_stock_item_detail__exposes_lifecycle_keys(api):
    # Pins the History-timeline contract: every DTO surface must be
    # present (lists may be empty) and last_checked_at must serialise
    # (null is fine when the item has never been checked).
    _AnyItem = _items('?limit=1')[0]

    _Detail = requests.get(f'{base_route}/{_AnyItem["stock_item_id"]}/detail').json()

    assert isinstance(_Detail.get('waste_events'), list)
    assert isinstance(_Detail.get('recent_list_adds'), list)
    # 2026-06-30 — three new event feeds added to the detail DTO.
    assert isinstance(_Detail.get('purchase_events'), list)
    assert isinstance(_Detail.get('cook_events'), list)
    assert isinstance(_Detail.get('expiry_events'), list)
    assert 'last_checked_at' in _Detail


def test__expiry_event__emitted_on_set_push_and_clear(api, stock_level_id):
    """2026-06-30 — every mutation of `StockItem.expiry_date` appends
    a StockItemExpiryEvent with the right `kind`. Create-with-expiry
    emits `set`, a PATCH to a later date emits `pushed` with a
    positive `delta_days`, a PATCH to null emits `cleared` with the
    previous date preserved."""
    _CreatedResp = requests.post(base_route, json=CreateStockItemRequest(
        name=f'Expiry Event Item {uuid4().hex[:8]}',
        stock_level_id=stock_level_id,
        expiry_date='2026-07-05',
    ).model_dump(mode='json'))
    assert _CreatedResp.status_code == 201, _CreatedResp.text
    _ItemId = _CreatedResp.json()['stock_item_id']

    # Set on create → `set` event.
    _Detail = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert len(_Detail['expiry_events']) == 1
    _First = _Detail['expiry_events'][0]
    assert _First['kind'] == 'set'
    assert _First['previous_expiry_date'] is None
    assert _First['new_expiry_date'] == '2026-07-05'
    assert _First['delta_days'] is None

    # Push +7 days → `pushed` event with delta 7.
    _PushResp = requests.patch(
        f'{base_route}/{_ItemId}',
        json={'expiry_date': '2026-07-12'},
    )
    assert _PushResp.status_code == 204, _PushResp.text
    _Detail = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert len(_Detail['expiry_events']) == 2
    _Pushed = _Detail['expiry_events'][0]  # newest first
    assert _Pushed['kind'] == 'pushed'
    assert _Pushed['previous_expiry_date'] == '2026-07-05'
    assert _Pushed['new_expiry_date'] == '2026-07-12'
    assert _Pushed['delta_days'] == 7

    # Clear → `cleared` event.
    _ClearResp = requests.patch(
        f'{base_route}/{_ItemId}',
        json={'expiry_date': None},
    )
    assert _ClearResp.status_code == 204, _ClearResp.text
    _Detail = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert len(_Detail['expiry_events']) == 3
    _Cleared = _Detail['expiry_events'][0]
    assert _Cleared['kind'] == 'cleared'
    assert _Cleared['previous_expiry_date'] == '2026-07-12'
    assert _Cleared['new_expiry_date'] is None
    assert _Cleared['delta_days'] is None


def test__history_older_count__caps_at_per_kind_limit(api, stock_level_id):
    """2026-06-30 — the detail projection caps each event kind at
    `HISTORY_PER_KIND_CAP` (50) and reports the sum of what got
    dropped as `history_older_count`. Trip the cap with 52 expiry
    transitions on a single item and verify the count is 2."""
    from dora_api.features.stock_items.get_stock_item_detail import (
        HISTORY_PER_KIND_CAP,
    )
    _CreatedResp = requests.post(base_route, json=CreateStockItemRequest(
        name=f'Cap Test Item {uuid4().hex[:8]}',
        stock_level_id=stock_level_id,
        expiry_date='2026-07-01',
    ).model_dump(mode='json'))
    _ItemId = _CreatedResp.json()['stock_item_id']

    # Chain N-1 additional PATCH-to-later transitions (each moves the
    # date one day forward), so total events = HISTORY_PER_KIND_CAP + 2
    # (1 set from create + HISTORY_PER_KIND_CAP + 1 pushes).
    _target_transitions = HISTORY_PER_KIND_CAP + 1  # extra pushes
    for _i in range(_target_transitions):
        _new = f'2026-07-{2 + _i:02d}' if (2 + _i) <= 31 else f'2026-08-{(2 + _i) - 31:02d}'
        _resp = requests.patch(
            f'{base_route}/{_ItemId}',
            json={'expiry_date': _new},
        )
        assert _resp.status_code == 204, _resp.text

    _Detail = requests.get(f'{base_route}/{_ItemId}/detail').json()
    # 52 total events, cap 50 → returns 50 in the list, drops 2 past
    # the cap.
    assert len(_Detail['expiry_events']) == HISTORY_PER_KIND_CAP
    assert _Detail['history_older_count'] == 2


def test__expiry_event__no_change_no_event(api, stock_level_id):
    """A PATCH that leaves `expiry_date` the same value must not
    emit a new event — the timeline is for transitions, not saves."""
    _CreatedResp = requests.post(base_route, json=CreateStockItemRequest(
        name=f'Expiry NoOp Item {uuid4().hex[:8]}',
        stock_level_id=stock_level_id,
        expiry_date='2026-08-01',
    ).model_dump(mode='json'))
    _ItemId = _CreatedResp.json()['stock_item_id']

    # Same-value PATCH → no new event.
    _NoOp = requests.patch(
        f'{base_route}/{_ItemId}',
        json={'expiry_date': '2026-08-01'},
    )
    assert _NoOp.status_code == 204, _NoOp.text
    _Detail = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert len(_Detail['expiry_events']) == 1  # only the `set` from create


# ── C-1b.1 — detail DTO threads stock_group_id/name ─────────────────


def test__get_stock_item_detail__exposes_stock_group_keys(api):
    # Both fields must be on the DTO so the inline picker has something to
    # render (populated or empty). The roundtrip test below covers the
    # populated path; this one pins the shape contract.
    _AnyItem = _items('?limit=1')[0]

    _Detail = requests.get(f'{base_route}/{_AnyItem["stock_item_id"]}/detail').json()

    assert 'stock_group_id' in _Detail


def test__get_stock_item_detail__null_stock_group_serialises_as_null(api, stock_level_id):
    # An item created without a stock group must return a null id — the
    # detail page reads it to render the inline picker's "Set group" empty
    # state.
    _Created = requests.post(base_route, json=CreateStockItemRequest(
        name='C1b1 Detail Group Null',
        stock_level_id=stock_level_id,
    ).model_dump(mode="json")).json()

    _Detail = requests.get(f'{base_route}/{_Created["stock_item_id"]}/detail').json()

    assert _Detail['stock_group_id'] is None


def test__get_stock_item_detail__stock_group_roundtrips_via_patch(api, stock_level_id):
    # Setting + clearing stock_group_id through the existing partial PATCH
    # is reflected on the next detail read (the inline picker's contract).
    _Created = requests.post(base_route, json=CreateStockItemRequest(
        name='C1b1 Detail Group Roundtrip',
        stock_level_id=stock_level_id,
    ).model_dump(mode="json")).json()
    _ItemId = _Created["stock_item_id"]
    _Groups = requests.get('http://localhost:5170/api/stock-groups').json()
    assert _Groups, "seed DB has at least one stock group"
    _GroupId = _Groups[0]['stock_group_id']

    assert requests.patch(
        f'{base_route}/{_ItemId}', json={'stock_group_id': _GroupId},
    ).status_code == 204
    _DetailWithGroup = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert _DetailWithGroup['stock_group_id'] == _GroupId

    # Null clears it back to "no group set".
    assert requests.patch(
        f'{base_route}/{_ItemId}', json={'stock_group_id': None},
    ).status_code == 204
    _DetailCleared = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert _DetailCleared['stock_group_id'] is None


def test__get_stock_item_detail__stock_location_roundtrips_via_patch(api, stock_level_id, stock_location_id):
    # `stock_location` relationship is mapped lazy="noload",
    # so a bare `stock_location = None` doesn't dirty the FK column. The handler
    # has to set `_stock_location_id` directly when clearing. Mirrors the
    # stock_group roundtrip test above; same trap, same fix shape.
    _Created = requests.post(base_route, json=CreateStockItemRequest(
        name='FU-203 Detail Location Roundtrip',
        stock_level_id=stock_level_id,
        stock_location_id=stock_location_id,
    ).model_dump(mode="json")).json()
    _ItemId = _Created["stock_item_id"]

    _DetailWithLocation = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert _DetailWithLocation['stock_location_id'] == stock_location_id

    assert requests.patch(
        f'{base_route}/{_ItemId}', json={'stock_location_id': None},
    ).status_code == 204
    _DetailCleared = requests.get(f'{base_route}/{_ItemId}/detail').json()
    assert _DetailCleared['stock_location_id'] is None


def test__delete_stock_item__DeletedItemNoLongerReturnedInGetAll(api):
    _StockItemRequest = CreateStockItemRequest(
        name="Item To Verify Gone",
        stock_level_id=requests.get('http://localhost:5170/api/stock-levels').json()['items'][0]['stock_level_id']
    )
    requests.post(base_route, json=_StockItemRequest.model_dump(mode="json"))
    _StockItemId = _first('?filter=name:ct:Item To Verify Gone')['stock_item_id']

    requests.delete(f"{base_route}/{_StockItemId}")
    _GetResponse = requests.get(f'{base_route}?filter=stock_item_id:eq:{_StockItemId}')

    assert _GetResponse.status_code == 200
    assert _GetResponse.json()['items'] == []


#endregion delete_stock_item tests
