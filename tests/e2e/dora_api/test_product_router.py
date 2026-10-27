import uuid
from unittest.mock import ANY

import pytest
import requests

from dora_api.features.products.create_product import CreateProductRequest
from dora_api.features.products.update_product import UpdateProductRequest
from tests.e2e.dora_api._error_assertions import domain_err, validation_err
from tests.support import is_valid_uuid

#region ---------------- setup ----------------

base_route = 'http://localhost:5170/api/products'
_STORE_ROUTE = 'http://localhost:5170/api/stores'


@pytest.fixture(autouse=True)
def _seed_stores_and_product(request):
    """FU-169 Phase 2 — shared preconditions this file's non-create tests
    assume. Was module-scoped; became function-scoped once the per-test
    DB rollback landed. Two independent bits:

    * Stores `Woolworths` + `ReuseMerchant` — the products API refuses
      unknown store names, so tests that POST products against fixed
      names need these rows to exist.
    * The `Banana Mangoes` (stockcode `50332BA`) product — the GET /
      UPDATE tests query for it by stockcode / merchant.

    Skip the product-seed via `@pytest.mark.no_seed_product` on the
    single create test whose *act* is to create that same product.
    Store rows are always seeded — the create tests need them.
    """
    for _Name in ("Woolworths", "ReuseMerchant"):
        requests.post(_STORE_ROUTE, json={"name": _Name})
    if request.node.get_closest_marker("no_seed_product"):
        return
    requests.post(base_route, json=CreateProductRequest(
        brand="Test",
        image=None,
        is_active=True,
        is_available=True,
        store_name="Woolworths",
        merchant_stockcode="50332BA",
        name="Banana Mangoes",
        price_now=4.5,
        price_was=10.5,
        size="500g",
        size_unit="g",
        size_value=5.0,
        web_url="www",
    ).model_dump())

#endregion setup

#region ---------------- create_product tests ----------------


# TODO: Write test for optional fields (brand, stockcode, etc)
@pytest.mark.no_seed_product
def test__create_product__CreatingProductWithAllAttributes__ProductCreated(api):
    _ProductRequest = CreateProductRequest(
        brand = "Test",
        image = None,  # TODO: Grab a random image, maybe dora icon from repo
        is_active = True,
        is_available = True,
        store_name = "Woolworths",
        merchant_stockcode = "50332BA",
        name = "Banana Mangoes",
        price_now = 4.5,
        price_was = 10.5,
        size = "500g",
        size_unit = "g",
        size_value = 5.0,
        web_url = "www"
    )

    _Response = requests.post(base_route, json = _ProductRequest.model_dump())

    assert _Response.status_code == 201
    assert _Response.headers['Content-Type'] == 'application/json'
    assert '/api/products?filter=product_id:eq:' in _Response.headers['location']
    assert _Response.json()['id'] == ANY


def test__create_product__CreatingProductWithIncorrectDataTypes__CannotBeDeserialised(api):
    _Request = {
        "brand": 555,
        "image": 234,
        "is_active": "AAA",
        "is_available": "BBB",
        "store_name": True,
        "merchant_stockcode": 2.3,
        "name": 2.4,
        "price_now": "CCC",
        "price_was": "DDD",
        "size": 555,
        "size_unit": 2.5,
        "size_value": "EEE",
        "web_url": False
    }

    _Response = requests.post(base_route, json = _Request)
    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "brand": [validation_err("string_type", "Input should be a valid string")],
            "image": [validation_err("string_type", "Input should be a valid string")],
            "is_active": [validation_err("bool_parsing", "Input should be a valid boolean, unable to interpret input")],
            "is_available": [validation_err("bool_parsing", "Input should be a valid boolean, unable to interpret input")],
            "store_name": [validation_err("string_type", "Input should be a valid string")],
            "merchant_stockcode": [validation_err("string_type", "Input should be a valid string")],
            "name": [validation_err("string_type", "Input should be a valid string")],
            "price_now": [validation_err("float_parsing", "Input should be a valid number, unable to parse string as a number")],
            "price_was": [validation_err("float_parsing", "Input should be a valid number, unable to parse string as a number")],
            "size": [validation_err("string_type", "Input should be a valid string")],
            "size_unit": [validation_err("string_type", "Input should be a valid string")],
            "size_value": [validation_err("float_parsing", "Input should be a valid number, unable to parse string as a number")],
            "web_url": [validation_err("string_type", "Input should be a valid string")]
        },
        "status": 400,
        "title": "Malformed request.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1"
    }


def test__create_product__CreatingProductWithOnlyRequiredAttributes__ProductCreated(api):
    _ProductRequest = CreateProductRequest(
        is_active = True,
        is_available = True,
        store_name = "Woolworths",
        name = "Milo Chocolate Powder",
        price_now = 4.5,
        price_was = 10.5,
        size = "500g",
        size_unit = "g",
        size_value = 5.0
    )

    _Response = requests.post(base_route, json = _ProductRequest.model_dump())

    assert _Response.status_code == 201
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['id'] == ANY


def test__create_product__PriceNowAtZeroBoundary__IsBadRequest(api):
    _ProductRequest = {
        "is_active": True,
        "is_available": True,
        "store_name": "Woolworths",
        "name": "Boundary Price Product",
        "price_now": 0,
        "price_was": 10.5,
        "size": "500g",
        "size_unit": "g",
        "size_value": 5.0
    }

    _Response = requests.post(base_route, json=_ProductRequest)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json()['errors']['price_now'] == [validation_err("greater_than", "Input should be greater than 0")]


def test__create_product__PriceWasAtZeroBoundary__IsBadRequest(api):
    _ProductRequest = {
        "is_active": True,
        "is_available": True,
        "store_name": "Woolworths",
        "name": "Boundary Price Product",
        "price_now": 4.5,
        "price_was": 0,
        "size": "500g",
        "size_unit": "g",
        "size_value": 5.0
    }

    _Response = requests.post(base_route, json=_ProductRequest)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json()['errors']['price_was'] == [validation_err("greater_than", "Input should be greater than 0")]


def test__create_product__PriceNowJustAboveZeroBoundary__ProductCreated(api):
    _ProductRequest = CreateProductRequest(
        is_active=True,
        is_available=True,
        store_name="Woolworths",
        name="Boundary Price Product Above Zero",
        price_now=0.001,
        price_was=10.5,
        size="500g",
        size_unit="g",
        size_value=5.0
    )

    _Response = requests.post(base_route, json=_ProductRequest.model_dump())

    assert _Response.status_code == 201


def test__create_product__SizeValueAtZeroBoundary__IsBadRequest(api):
    _ProductRequest = {
        "is_active": True,
        "is_available": True,
        "store_name": "Woolworths",
        "name": "Boundary Size Product",
        "price_now": 4.5,
        "price_was": 10.5,
        "size": "500g",
        "size_unit": "g",
        "size_value": 0
    }

    _Response = requests.post(base_route, json=_ProductRequest)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json()['errors']['size_value'] == [validation_err("greater_than", "Input should be greater than 0")]


def test__create_product__EmptyStringOnRequiredField__IsBadRequest(api):
    _ProductRequest = {
        "is_active": True,
        "is_available": True,
        "store_name": "",
        "name": "Some Product",
        "price_now": 4.5,
        "price_was": 10.5,
        "size": "500g",
        "size_unit": "g",
        "size_value": 5.0
    }

    _Response = requests.post(base_route, json=_ProductRequest)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert 'store_name' in _Response.json()['errors']


def test__create_product__EmptyStringOnOptionalField__IsBadRequest(api):
    _ProductRequest = {
        "is_active": True,
        "is_available": True,
        "store_name": "Woolworths",
        "name": "Some Product",
        "price_now": 4.5,
        "price_was": 10.5,
        "size": "500g",
        "size_unit": "g",
        "size_value": 5.0,
        "brand": ""
    }

    _Response = requests.post(base_route, json=_ProductRequest)

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert 'brand' in _Response.json()['errors']


def test__create_product__StoreAlreadyExists__StoreIsReused(api):
    _FirstProductRequest = CreateProductRequest(
        is_active=True,
        is_available=True,
        store_name="ReuseMerchant",
        name="First Product",
        price_now=4.5,
        price_was=10.5,
        size="500g",
        size_unit="g",
        size_value=5.0
    )
    _SecondProductRequest = CreateProductRequest(
        is_active=True,
        is_available=True,
        store_name="ReuseMerchant",
        name="Second Product",
        price_now=3.0,
        price_was=6.0,
        size="250g",
        size_unit="g",
        size_value=2.5
    )

    requests.post(base_route, json=_FirstProductRequest.model_dump())
    requests.post(base_route, json=_SecondProductRequest.model_dump())

    _FirstProduct = requests.get(f'{base_route}?filter=name:eq:First Product').json()['items'][0]
    _SecondProduct = requests.get(f'{base_route}?filter=name:eq:Second Product').json()['items'][0]

    assert _FirstProduct['store_id'] == _SecondProduct['store_id']
    assert _FirstProduct['store_name'] == 'ReuseMerchant'
    assert _SecondProduct['store_name'] == 'ReuseMerchant'


def test__create_product__UnknownStoreName__IsBusinessRuleViolation(api):
    """FU-189a — manual product-add no longer auto-creates a Store. An
    unknown `store_name` is rejected with a 422 + a "create it in
    Settings → Stores first" hint, matching the strict no-auto-create
    posture the ingestion API enforces (FU-190)."""
    _ProductRequest = CreateProductRequest(
        is_active=True,
        is_available=True,
        store_name="NoSuchStoreXYZ",
        name="Unknown-Store Product",
        price_now=4.5,
        price_was=10.5,
        size="500g",
        size_unit="g",
        size_value=5.0,
    )

    _Response = requests.post(base_route, json=_ProductRequest.model_dump())

    assert _Response.status_code == 422
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "": [domain_err(
                "Store 'NoSuchStoreXYZ' does not exist. "
                "Create it in Settings → Stores first."
            )]
        },
        "status": 422,
        "title": "Business rule violation.",
        "type": "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2",
    }


def test__create_product__MissingRequiredFields__AllMissingFieldsReported(api):
    _Response = requests.post(base_route, json={"brand": "Test"})

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {
            'is_active': [validation_err("missing", "Field required")],
            'is_available': [validation_err("missing", "Field required")],
            'store_name': [validation_err("missing", "Field required")],
            'name': [validation_err("missing", "Field required")],
            'price_now': [validation_err("missing", "Field required")],
            'size': [validation_err("missing", "Field required")],
            'size_unit': [validation_err("missing", "Field required")],
            'size_value': [validation_err("missing", "Field required")],
        },
        'status': 400,
        'title': 'Malformed request.',
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__create_product__ProductAlreadyExists__AppendsHistoricOffer(api):
    """FU-217 / R-003 — the second POST for the same product no longer
    422s; it appends a new historic point + moves current_offer (the
    same offer-append mapping `/api/ingest` uses)."""
    import uuid
    unique_stockcode = uuid.uuid4().hex[:8]
    payload = {
        "brand": "Test",
        "image": None,
        "is_active": True,
        "is_available": True,
        "store_name": "Woolworths",
        "merchant_stockcode": unique_stockcode,
        "name": f"FU217-{uuid.uuid4().hex[:6]}",
        "price_now": 4.5,
        "price_was": 10.5,
        "size": "500g",
        "size_unit": "g",
        "size_value": 5.0,
        "web_url": "www",
    }

    first = requests.post(base_route, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["created"] is True
    product_id = first.json()["id"]

    # Same product, new price → 201, not created, offer appended.
    payload["price_now"] = 3.0
    payload["price_was"] = 5.0
    second = requests.post(base_route, json=payload)
    assert second.status_code == 201, second.text
    assert second.json()["created"] is False
    assert second.json()["offer_appended"] is True
    assert second.json()["id"] == product_id


def test__create_product__ExtraAttributes__IsBadRequest(api):
    _ProductRequest = {
        "brand": "Test",
        "image": None,
        "is_active": True,
        "is_available": True,
        "store_name": "WoolWorThS",
        "merchant_stockcode": "50332ba",
        "name": "Banana Mangoes",
        "price_now": 4.5,
        "price_was": 10.5,
        "size": "500g",
        "size_unit": "g",
        "size_value": 5.0,
        "web_url": "www",
        "poopusgoopus": "aaaa"
    }

    _Response = requests.post(base_route, json = _ProductRequest)

    assert _Response.status_code == 400
    assert _Response.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "poopusgoopus": [validation_err("extra_forbidden", "Extra inputs are not permitted")]
        },
        "status": 400,
        "title": "Malformed request.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1"
    }


def test__create_product__EmptyRequest__IsRequiredInputsValidationFailure(api):
    _Response = requests.post(base_route, json = {})

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {
            'is_active': [validation_err("missing", "Field required")],
            'is_available': [validation_err("missing", "Field required")],
            'store_name': [validation_err("missing", "Field required")],
            'name': [validation_err("missing", "Field required")],
            'price_now': [validation_err("missing", "Field required")],
            'size': [validation_err("missing", "Field required")],
            'size_unit': [validation_err("missing", "Field required")],
            'size_value': [validation_err("missing", "Field required")],
        },
       'status': 400,
       'title': 'Malformed request.',
       'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


#endregion create_product tests

#region ---------------- get_products tests ----------------


def test__get_products__GettingProduct__GetsAllExpectedAttributes(api):
    _Product = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    assert _Product['brand'] == 'Test'
    assert _Product['has_image'] is False
    assert _Product['is_active'] is True
    assert _Product['is_available'] is True
    # OD-2 — this product was created through `POST /products`, which IS the
    # hand-entry path, so it is custom. Ingested products (the seed's) are not;
    # `test_custom_products.py` pins both sides.
    assert _Product['is_custom'] is True
    assert is_valid_uuid(_Product['store_id'])
    assert _Product['store_name'] == 'Woolworths'
    assert _Product['merchant_stockcode'] == '50332BA'
    assert _Product['name'] == 'Banana Mangoes'
    assert _Product['pack_count'] is None
    assert _Product['price_now'] == 4.5
    assert _Product['price_was'] == 10.5
    assert is_valid_uuid(_Product['product_id'])
    assert _Product['size'] == '500g'
    assert _Product['size_unit'] == 'g'
    assert _Product['size_value'] == 5.0
    assert _Product['web_url'] == 'www'
    assert _Product.keys() == {
        'brand',
        'has_image',
        'is_active',
        'is_available',
        'store_id',
        'store_name',
        'merchant_stockcode',
        'name',
        'pack_count',
        'price_now',
        'price_was',
        'product_id',
        'size',
        'size_unit',
        'size_value',
        'web_url',
        'linked_stock_item_id',
        'linked_stock_item_name',
        'is_custom'
    }


def test__get_products__GettingAllProducts__GetsAllProducts(api):
    _Response = requests.get(f'{base_route}?limit=500')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    _Body = _Response.json()
    # Under a generous limit, every row is returned, so total == page size.
    assert _Body['total'] == len(_Body['items'])
    # At least the full seed (9 products); more once create tests have run.
    assert _Body['total'] >= 9


def test__get_products__FilteringByStockcode__GetsSingleMatchingProduct(api):
    _Response = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'][0]['merchant_stockcode'] == '50332BA'
    assert len(_Response.json()['items']) == 1


def test__get_products__FilteringOnNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?filter=stockcode:eq:50332BA')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Field 'stockcode' is not filterable on 'Product'.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_products__FilteringForProductThatDoesNotExist__EmptyResult(api):
    _Response = requests.get(f'{base_route}?filter=product_id:eq:{uuid.uuid4()}')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'] == []


def test__get_products__FilteringWithUnsupportedOperator__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?filter=product_id:xx:{uuid.uuid4()}')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Unsupported filter operator 'xx'. Supported: ct, eq, ge, gt, le, lt, ne.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_products__SortingByNonExistentAttribute__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?sort=stockcode:desc')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": "See errors property for more details.",
        "status": 400,
        "errors": {},
        "title": "Field 'stockcode' is not filterable on 'Product'.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1"
    }


def test__get_products__NoProductsMatchFilter__ReturnsEmptyList(api):
    _Response = requests.get(f'{base_route}?filter=name:eq:NonExistentProductName')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'] == []


def test__get_products__SortByNameAscending__ProductsInAscendingOrder(api):
    _Response = requests.get(f'{base_route}?sort=name:asc&limit=500')

    assert _Response.status_code == 200
    _Names = [p['name'] for p in _Response.json()['items']]
    # API sorts case-insensitively (NOCASE collation).
    assert _Names == sorted(_Names, key=str.lower)


def test__get_products__SortByNameDescending__ProductsInDescendingOrder(api):
    _Response = requests.get(f'{base_route}?sort=name:desc&limit=500')

    assert _Response.status_code == 200
    _Names = [p['name'] for p in _Response.json()['items']]
    assert _Names == sorted(_Names, key=str.lower, reverse=True)


def test__get_products__SortWithUnsupportedOrder__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?sort=name:random')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "Sort direction 'random' is not supported. Use 'asc' or 'desc'.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_products__PaginationFirstPage__ReturnsCorrectSlice(api):
    _AllProducts = requests.get(f'{base_route}?sort=name:asc&limit=500').json()['items']
    _Response = requests.get(f'{base_route}?sort=name:asc&page=1&limit=2')

    assert _Response.status_code == 200
    assert _Response.headers['Content-Type'] == 'application/json'
    assert _Response.json()['items'] == _AllProducts[:2]


def test__get_products__PaginationSecondPage__ReturnsCorrectSlice(api):
    _AllProducts = requests.get(f'{base_route}?sort=name:asc&limit=500').json()['items']
    _Response = requests.get(f'{base_route}?sort=name:asc&page=2&limit=2')

    assert _Response.status_code == 200
    assert _Response.json()['items'] == _AllProducts[2:4]


def test__get_products__PageWithoutLimit__DefaultsLimit(api):
    # page/limit are now independently optional (limit defaults to 50).
    _Response = requests.get(f'{base_route}?page=1')

    assert _Response.status_code == 200
    assert _Response.json()['page'] == 1
    assert _Response.json()['limit'] == 50


def test__get_products__LimitWithoutPage__DefaultsPage(api):
    _Response = requests.get(f'{base_route}?limit=2')

    assert _Response.status_code == 200
    assert _Response.json()['page'] == 1
    assert _Response.json()['limit'] == 2
    assert len(_Response.json()['items']) == 2


def test__get_products__PageBelowOne__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?page=0&limit=2')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "'page' must be 1 or greater.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_products__LimitBelowOne__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?page=1&limit=0')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "'limit' must be 1 or greater.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_products__NonIntegerPageOrLimit__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?page=one&limit=two')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        'detail': 'See errors property for more details.',
        'errors': {},
        'status': 400,
        'title': "'page' must be an integer.",
        'type': 'https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.1',
    }


def test__get_products__MalformedFilter__IsBadRequest(api):
    _Response = requests.get(f'{base_route}?filter=name:eq')

    assert _Response.status_code == 400
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert "Malformed filter" in _Response.json()['title']


#endregion get_products tests

#region ---------------- update_product tests ----------------


def test__update_product__EmptyUpdate__ProductUnaffected(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]
    _PatchResponse = requests.patch(f"{base_route}/{_ProductToUpdate['product_id']}", json = {})
    _ProductAfterPatchOperation = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    assert _PatchResponse.status_code == 204
    assert _PatchResponse.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert _ProductToUpdate == _ProductAfterPatchOperation


def test__update_product__UpdatingAllAttributes__AllAttributesUpdated(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:51741').json()['items'][0]

    _ProductRequest = UpdateProductRequest(
        is_active = False,
        is_available = False,
        price_now = 1.0,
        price_was = 12.8
    )

    _PatchResponse = requests.patch(f"{base_route}/{_ProductToUpdate['product_id']}", json = _ProductRequest.model_dump())
    _ProductAfterPatchOperation = requests.get(f'{base_route}?filter=merchant_stockcode:eq:51741').json()['items'][0]

    assert _PatchResponse.status_code == 204
    assert _PatchResponse.headers['Content-Type'] == 'text/html; charset=utf-8'
    # Before: the seeded Cadbury product is active/available.
    assert _ProductToUpdate['name'] == 'Cadbury Freddo Cake'
    assert _ProductToUpdate['is_active'] is True
    assert _ProductToUpdate['is_available'] is True
    # After: only the four patched fields change; identity fields are stable.
    assert _ProductAfterPatchOperation['is_active'] is False
    assert _ProductAfterPatchOperation['is_available'] is False
    assert _ProductAfterPatchOperation['price_now'] == 1.0
    assert _ProductAfterPatchOperation['price_was'] == 12.8
    assert _ProductAfterPatchOperation['name'] == 'Cadbury Freddo Cake'
    assert _ProductAfterPatchOperation['merchant_stockcode'] == '51741'
    assert _ProductAfterPatchOperation['product_id'] == _ProductToUpdate['product_id']


def test__update_product__ProductDoesNotExist__ProductNotFound(api):
    _RandomID = uuid.uuid4()
    _Response = requests.patch(f"{base_route}/{_RandomID}", json = {})

    assert _Response.status_code == 404
    assert _Response.headers['Content-Type'] == 'application/problem+json'
    assert _Response.json() == {
        "detail": f"Product with the ID '{_RandomID}' was not found.",
        "errors": {},
        "status": 404,
        "title": "Entity was not found.",
        "type": "https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.4"
    }


def test__update_product__UpdatingPriceNowWithoutPriceWas__IsValidationFailure(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    _ProductRequest = UpdateProductRequest(price_now = 1.0).model_dump(exclude_unset=True)

    _PatchResponse = requests.patch(f"{base_route}/{_ProductToUpdate['product_id']}", json = _ProductRequest)
    _ProductAfterPatchOperation = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    assert _ProductToUpdate == _ProductAfterPatchOperation
    assert _PatchResponse.status_code == 422
    assert _PatchResponse.headers['Content-Type'] == 'application/problem+json'
    assert _PatchResponse.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "": [domain_err("price_now and price_was must both be set.")]
        },
        "status": 422,
        "title": "Business rule violation.",
        "type": "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2"
    }


def test__update_product__UpdatingPriceWasWithoutPriceNow__IsValidationFailure(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    _ProductRequest = UpdateProductRequest(price_was = 1.0).model_dump(exclude_unset=True)

    _PatchResponse = requests.patch(f"{base_route}/{_ProductToUpdate['product_id']}", json = _ProductRequest)
    _ProductAfterPatchOperation = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    assert _ProductToUpdate == _ProductAfterPatchOperation
    assert _PatchResponse.status_code == 422
    assert _PatchResponse.headers['Content-Type'] == 'application/problem+json'
    assert _PatchResponse.json() == {
        "detail": "See errors property for more details.",
        "errors": {
            "": [domain_err("price_now and price_was must both be set.")]
        },
        "status": 422,
        "title": "Business rule violation.",
        "type": "https://datatracker.ietf.org/doc/html/rfc4918#section-11.2"
    }


def test__update_product__UpdatingIsActiveOnly__OnlyIsActiveChanges(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    _ProductRequest = UpdateProductRequest(is_active=False).model_dump(exclude_unset=True)
    _PatchResponse = requests.patch(f"{base_route}/{_ProductToUpdate['product_id']}", json=_ProductRequest)
    _ProductAfterPatch = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    assert _PatchResponse.status_code == 204
    assert _ProductAfterPatch['is_active'] is False
    assert _ProductAfterPatch['is_available'] == _ProductToUpdate['is_available']
    assert _ProductAfterPatch['price_now'] == _ProductToUpdate['price_now']
    assert _ProductAfterPatch['price_was'] == _ProductToUpdate['price_was']


def test__update_product__UpdatingIsAvailableOnly__OnlyIsAvailableChanges(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    _ProductRequest = UpdateProductRequest(is_available=False).model_dump(exclude_unset=True)
    _PatchResponse = requests.patch(f"{base_route}/{_ProductToUpdate['product_id']}", json=_ProductRequest)
    _ProductAfterPatch = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    assert _PatchResponse.status_code == 204
    assert _ProductAfterPatch['is_available'] is False
    assert _ProductAfterPatch['is_active'] == _ProductToUpdate['is_active']
    assert _ProductAfterPatch['price_now'] == _ProductToUpdate['price_now']
    assert _ProductAfterPatch['price_was'] == _ProductToUpdate['price_was']


def _historic_offers(product_id: str) -> list:
    from dora_api.app import app
    from dora_api.domain.entities.product_historic_offer import ProductHistoricOffer
    from dora_api.persistence.field import EntityField
    from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

    with app.app_context():
        return SqlAlchemyRepository().get(ProductHistoricOffer).all(
            EntityField(ProductHistoricOffer, "_product_id").eq(uuid.UUID(product_id))
        )


def test__update_product__UpdatingPrices__RecordsOneManualObservation(api):
    """Finalisation 10-R5: the edit path appends through the shared offer rule
    (`source == "manual"`), and restating the current price records nothing."""
    _Product = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]
    _Before = len(_historic_offers(_Product['product_id']))

    _Patch = requests.patch(f"{base_route}/{_Product['product_id']}", json={"price_now": 9.99, "price_was": 14.99})
    assert _Patch.status_code == 204
    _After = _historic_offers(_Product['product_id'])
    assert len(_After) == _Before + 1
    assert [o for o in _After if o.price_now == 9.99][0].source == "manual"

    _Again = requests.patch(f"{base_route}/{_Product['product_id']}", json={"price_now": 9.99, "price_was": 14.99})
    assert _Again.status_code == 204
    assert len(_historic_offers(_Product['product_id'])) == _Before + 1


def test__update_product__PriceNowAtZeroBoundary__IsBadRequest(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    _ProductRequest = {"price_now": 0, "price_was": 10.5}
    _PatchResponse = requests.patch(f"{base_route}/{_ProductToUpdate['product_id']}", json=_ProductRequest)

    assert _PatchResponse.status_code == 400
    assert _PatchResponse.headers['Content-Type'] == 'application/problem+json'
    assert _PatchResponse.json()['errors']['price_now'] == [validation_err("greater_than", "Input should be greater than 0")]


def test__update_product__ExtraAttributes__IsBadRequest(api):
    _ProductToUpdate = requests.get(f'{base_route}?filter=merchant_stockcode:eq:50332BA').json()['items'][0]

    _PatchResponse = requests.patch(
        f"{base_route}/{_ProductToUpdate['product_id']}",
        json={"is_active": True, "poopusgoopus": "aaaa"}
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


#endregion update_product tests
