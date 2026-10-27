"""`DELETE /api/products/<id>` — remove a saved product for good.

Feedback L197 ("no way to remove a saved product") was left open for months
because a hard delete looked pointless: the companion pushed whatever a bulk
scrape returned, so anything deleted came straight back on the next push. That
is no longer true — the companion now pushes only the offers the user
explicitly saved (products program PF-1/PF-3), so Dora owns what is saved and a
delete means something.

This is the **single** delete path (PF-4). The companion's "unsave" calls this
same endpoint; there is no companion-specific back door.

What goes with the product, per owner decision D-2 — all of it by FK cascade,
already in the schema:

* `ProductOffer` / `ProductHistoricOffer` — the price history *is* the product's
* `PriceAlert` — an alert on a product that no longer exists has nothing to fire
* `Barcode` — the row is deleted outright, not orphaned (its CHECK requires one
  of product/stock item, so nulling the column would be invalid)
* `StockItemProduct` — the link, not the stock item

What survives, per D-4 (FU-883): lines on **finished** shopping lists, which
keep the product's name via the snapshot frozen at `/finish`. Lines on draft or
shopping lists are removed. Both handled by `prepare_lines_for_anchor_delete`,
shared with stock-item delete.

Unlike `delete_stock_item`, nothing blocks: a product is reference data, not
something a recipe can depend on.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from dora_api.domain.entities.product import Product
from dora_api.features.routers import PRODUCT_ROUTER
from dora_api.features.shopping_lists._line_retention import \
    prepare_lines_for_anchor_delete
from dora_api.infrastructure.api_response import no_content, not_found
from dora_api.infrastructure.ports import Repository
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeleteProductResponse:
    product_not_found: bool = False


class DeleteProductHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, product_id: UUID) -> DeleteProductResponse:
        _Product = self.repository.get(Product).by_id(product_id)

        if not _Product:
            return DeleteProductResponse(product_not_found = True)

        # Before the delete, while the product's name is still readable:
        # drop its lines from live lists and make sure every surviving
        # historic line can name itself (FU-883).
        prepare_lines_for_anchor_delete(self.repository, product_id=product_id)

        self.repository.remove(_Product)
        self.repository.save_changes()

        return DeleteProductResponse()


@PRODUCT_ROUTER.route("<uuid:product_id>", methods=["DELETE"])
def delete_product(product_id: UUID):
    _LOGGER.info("Received request to delete product.")
    _Handler = DeleteProductHandler(SqlAlchemyRepository())
    _Response = _Handler.handle(product_id)

    if _Response.product_not_found:
        _LOGGER.warning(f"Product not found with ID: {product_id}")
        return not_found(Product.__name__, product_id)

    _LOGGER.info(f"Successfully deleted product with ID: {product_id}")
    return no_content()
