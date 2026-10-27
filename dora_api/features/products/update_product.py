from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dora_api.domain.entities.product import Product
from dora_api.features.products.offer_mapping import (OFFER_SOURCE_MANUAL,
                                                       apply_offer_to_product)
from dora_api.features.routers import PRODUCT_ROUTER
from dora_api.infrastructure.api_response import business_rule_violation, no_content, not_found
from dora_api.infrastructure.decorators import has_request_body
from dora_api.infrastructure.utils import get_request_body
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository
from dora_api.infrastructure.data_url import image_field

_LOGGER = logging.getLogger(__name__)


class UpdateProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    is_available: bool | None = None
    price_now: float | None = Field(default = None, gt = 0)
    price_was: float | None = Field(default = None, gt = 0)
    # Photo — custom products only (owner 2026-10-17: "are we able to set
    # images for custom products? Should only be able to for those."). Same
    # contract as Store / User: a `data:image/...;base64,...` string (already
    # resized + re-encoded by the client's `processImageFile` under the install
    # image policy, R-003), stored as UTF-8 bytes and served by
    # `GET /products/<id>/image`; `clear_image=True` removes it and wins over
    # `image`; `image=None` without the flag leaves the photo untouched.
    #
    # An ingested product's picture belongs to its source — the producer
    # supplies it and the next ingest may restate it — so a hand-set photo
    # there would be either silently overwritten or silently diverge from the
    # source. The handler refuses rather than guessing which.
    image: str | None = image_field()
    clear_image: bool = False
    # Settable on any product, ingested or custom: a scraper rarely knows how
    # many eggs are in the carton, and ingest only restates it when its source
    # does (a null push never clobbers). Sending `null` clears it (FU-856).
    pack_count: int | None = Field(default = None, gt = 0)


@dataclass(slots=True)
class UpdateProductResponse:
    product_not_found: bool = False
    incomplete_price_info: bool = False
    image_not_custom: bool = False
    invalid_image: bool = False


class UpdateProductHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, request: UpdateProductRequest, product_id: UUID) -> UpdateProductResponse:
        _Product: Product | None = (
            self.repository
            .get(Product)
            .include(Product.Fields.CURRENT_OFFER)
            .include(Product.Fields.HISTORIC_OFFERS)
            .by_id(product_id)
        )

        if not _Product:
            return UpdateProductResponse(product_not_found=True)

        _SetFields = request.model_fields_set
        _PriceNowSet = "price_now" in _SetFields and request.price_now is not None
        _PriceWasSet = "price_was" in _SetFields and request.price_was is not None

        if _PriceNowSet ^ _PriceWasSet:
            return UpdateProductResponse(incomplete_price_info=True)

        _ImageSet = "image" in _SetFields and request.image is not None
        if (_ImageSet or request.clear_image) and not _Product.is_custom:
            return UpdateProductResponse(image_not_custom=True)
        if _ImageSet and not request.image.startswith("data:image/"):
            return UpdateProductResponse(invalid_image=True)

        if "is_active" in _SetFields and request.is_active is not None:
            _Product.is_active = request.is_active

        if "is_available" in _SetFields and request.is_available is not None:
            _Product.is_available = request.is_available

        if "pack_count" in _SetFields:
            _Product.pack_count = request.pack_count

        if request.clear_image:
            _Product.image = None
        elif _ImageSet:
            _Product.image = request.image.encode("utf-8")

        # One offer-append rule for create, edit and ingest (R-003): an edit
        # that changes the price records it as a manual observation; one that
        # restates the current price records nothing.
        _Current = _Product.current_offer
        _PriceChanged = _Current is None or (
            _Current.price_now != request.price_now or _Current.price_was != request.price_was
        )
        if _PriceNowSet and _PriceWasSet and _PriceChanged:
            apply_offer_to_product(
                self.repository, _Product,
                price_now=request.price_now,
                price_was=request.price_was,
                observed_at=datetime.now(UTC),
                source=OFFER_SOURCE_MANUAL,
            )

        self.repository.save_changes()
        return UpdateProductResponse()


@PRODUCT_ROUTER.route("<uuid:product_id>", methods=["PATCH"])
@has_request_body(UpdateProductRequest)
def update_product(product_id: UUID):
    _LOGGER.info("Received request to update product.")
    _Handler = UpdateProductHandler(SqlAlchemyRepository())
    _Request: UpdateProductRequest = get_request_body()
    _Response = _Handler.handle(_Request, product_id)

    if _Response.product_not_found:
        _LOGGER.warning(f"Product not found with ID: {product_id}")
        return not_found(Product.__name__, product_id)

    if _Response.incomplete_price_info:
        _LOGGER.warning("price_now or price_was was set without the other.")
        return business_rule_violation("price_now and price_was must both be set.")

    if _Response.image_not_custom:
        _LOGGER.warning(f"Refused a photo change on non-custom product {product_id}.")
        return business_rule_violation(
            "Only products you added yourself can have their photo changed."
        )

    if _Response.invalid_image:
        return business_rule_violation(
            "The photo must be a 'data:image/<type>;base64,...' data URL."
        )

    _LOGGER.info(f"Successfully updated product with ID: {product_id}")
    return no_content()
