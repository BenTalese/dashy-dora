import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dora_api.domain.entities.store import Store
from dora_api.domain.entities.product import Product
from dora_api.domain.entities.product_offer import ProductOffer
from dora_api.domain.types import EMPTY_UUID
from dora_api.features.products.offer_mapping import (OFFER_SOURCE_MANUAL,
                                                       OfferOutcome,
                                                       apply_offer_to_product)
from dora_api.features.products.get_products import get_products
from dora_api.features.products.web_url import check_web_url
from dora_api.features.routers import PRODUCT_ROUTER
from dora_api.infrastructure.api_response import business_rule_violation, created
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.field import EntityField
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.features.stores.find_store import find_store_by_name
from dora_api.infrastructure.data_url import image_field

_LOGGER = logging.getLogger(__name__)


class CreateProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # String caps match the `Product` columns (all `String(255)`); Postgres
    # enforces them, so an over-long value used to 500 instead of 400.
    brand: str | None = Field(default = None, min_length = 1, max_length = 255)
    # image is a data-URL string ("data:image/...;base64,..."), stored
    # as UTF-8 bytes on the entity; served back via GET /products/<id>/image.
    # Matches the stock-item/recipe convention. The old `Base64Bytes` decoded
    # arbitrary base64 strings to raw bytes that the read path then tried to
    # `decode('utf-8','ignore')` — corrupting every saved image.
    image: str | None = image_field()
    is_active: bool
    is_available: bool
    store_name: str = Field(min_length = 1)
    # `merchant_stockcode` is the producer's SKU on the
    # offer, retained verbatim per the rename runbook.
    merchant_stockcode: str | None = Field(default = None, min_length = 1, max_length = 255)
    name: str = Field(min_length = 1, max_length = 255)
    # How many countable things the pack holds ("12" eggs in a 700 g carton).
    # `size_value` stays the total measure; this is what lets a recipe's bare
    # "3 eggs" be priced off the pack (ADR-073, FU-856).
    pack_count: int | None = Field(default = None, gt = 0)
    price_now: float = Field(gt = 0)
    # Optional (OD-2). A hand-entered product usually has no "was" price —
    # the user knows what the butcher charges, not what it charged last month.
    # Defaults to `price_now`, which reads as "no markdown"; 0.0 would read as
    # "was free" and make every custom product look permanently discounted.
    price_was: float | None = Field(default = None, gt = 0)
    size: str = Field(min_length = 1, max_length = 255)
    size_unit: str = Field(min_length = 1, max_length = 255)
    size_value: float = Field(gt = 0)
    web_url: str | None = Field(default = None, min_length = 1)

    @field_validator("web_url")
    @classmethod
    def _web_url(cls, value: str | None) -> str | None:
        return check_web_url(value)


# the manual product-add reuses the C-10 shared
# `apply_offer_to_product` so duplicates append a historic point + move
# `current_offer` (one offer-append path across `/api/products` and
# `/api/ingest`), stamped `OFFER_SOURCE_MANUAL`.


@dataclass(slots=True)
class CreateProductResponse:
    product_id: UUID = EMPTY_UUID
    created: bool = False
    offer_appended: bool = False
    store_not_found: bool = False


class CreateProductHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: CreateProductRequest) -> CreateProductResponse:
        _StoreName = EntityField(Store, Store.Fields.NAME)
        _ProductName = EntityField(Product, Product.Fields.NAME)
        _ProductStockcode = EntityField(Product, Product.Fields.MERCHANT_STOCKCODE)

        # strict no-auto-create. Stores are user-curated (managed
        # in Settings → Stores); the manual product-add path must reject
        # unknown store names, mirroring what `/api/ingest` already does via
        # the quarantine queue (FU-190). The same trimmed, case-insensitive
        # match store create/rename use, so callers aren't surprised by casing.
        _Store: Store | None = find_store_by_name(self.repository, request.store_name)
        if _Store is None:
            return CreateProductResponse(store_not_found=True)

        _ExistingProduct: Product | None = (
            self.repository
            .get(Product)
            .include(Product.Fields.STORE)
            .include(Product.Fields.CURRENT_OFFER)
            .one(_ProductStockcode.eq(request.merchant_stockcode)
                 & _StoreName.eq(_Store.name)
                 & _ProductName.eq(request.name))
        )

        observed_at = datetime.now(UTC)

        if _ExistingProduct is not None:
            outcome = apply_offer_to_product(
                self.repository,
                _ExistingProduct,
                price_now=request.price_now,
                price_was=request.price_was or request.price_now,
                observed_at=observed_at,
                source=OFFER_SOURCE_MANUAL,
            )
            self.repository.save_changes()
            return CreateProductResponse(
                product_id=_ExistingProduct.id,
                created=False,
                offer_appended=outcome.outcome == OfferOutcome.APPENDED,
            )

        _Offer = ProductOffer(
            offered_on=observed_at,
            price_now=request.price_now,
            price_was=request.price_was or request.price_now,
        )
        _NewProduct = Product(
            brand=request.brand,
            current_offer=_Offer,
            historic_offers=[],
            image=request.image.encode("utf-8") if request.image else None,
            is_active=request.is_active,
            is_available=request.is_available,
            store=_Store,
            merchant_stockcode=request.merchant_stockcode,
            name=request.name,
            pack_count=request.pack_count,
            size=request.size,
            size_unit=request.size_unit,
            size_value=request.size_value,
            web_url=request.web_url,
            # OD-2 — this route IS the hand-entry path (its own docstring calls
            # it "the manual product-add"), so anything created here is custom
            # by definition. That marking is what keeps the scheduled sync from
            # trying to refresh it and ingestion from overwriting it.
            is_custom=True,
        )

        self.repository.add(_Offer)
        self.repository.add(_NewProduct)
        # The first price is an observation too, as on the ingest path: the
        # history holds every price seen, so a later edit has a prior to beat.
        apply_offer_to_product(
            self.repository,
            _NewProduct,
            price_now=_Offer.price_now,
            price_was=_Offer.price_was,
            observed_at=observed_at,
            source=OFFER_SOURCE_MANUAL,
        )
        self.repository.save_changes()

        return CreateProductResponse(
            product_id=_NewProduct.id,
            created=True,
            offer_appended=False,
        )


@PRODUCT_ROUTER.route("", methods=["POST"])
@has_request_body(CreateProductRequest)
def create_product():
    _Handler = CreateProductHandler(SqlAlchemyRepository())
    _Request: CreateProductRequest = get_request_body()
    _Response = _Handler.handle(_Request)

    if _Response.store_not_found:
        _LOGGER.warning(
            f"Rejected product create — unknown store '{_Request.store_name}'."
        )
        return business_rule_violation(
            f"Store '{_Request.store_name}' does not exist. "
            "Create it in Settings → Stores first."
        )

    if _Response.created:
        _LOGGER.info(f"Created product {_Response.product_id}")
    elif _Response.offer_appended:
        _LOGGER.info(
            f"Appended new offer to existing product {_Response.product_id}"
        )
    else:
        _LOGGER.info(
            f"Existing product {_Response.product_id} already has this offer; no-op."
        )

    return created(
        _Response.product_id,
        f"{PRODUCT_ROUTER.name}.{get_products.__name__}",
        "product_id",
        body={
            "id": _Response.product_id,
            "created": _Response.created,
            "offer_appended": _Response.offer_appended,
        },
    )
