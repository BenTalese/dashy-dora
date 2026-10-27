"""FU-014 — product image route.

  GET /api/products/<id>/image

Returns the product's stored image as raw bytes with the correct mimetype.
Images are stored as data-URL strings on the entity
(`data:image/jpeg;base64,...`) so the SPA can use a plain `<img src>` against
this route without inlining megabytes of base64 in every list/detail JSON.
Same pattern as the stock-item-image and recipe-image routes.
"""
from dora_api.domain.entities.product import Product
from dora_api.features.routers import PRODUCT_ROUTER
from dora_api.infrastructure.api_response import not_found
from dora_api.infrastructure.data_url import data_url_response
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


@PRODUCT_ROUTER.route("/<uuid:product_id>/image", methods=["GET"])
def get_product_image(product_id):
    repository = SqlAlchemyRepository()
    product = repository.get(Product).by_id(product_id)
    if product is None:
        return not_found(Product.__name__, product_id)

    return data_url_response(product.image, lambda: not_found(Product.__name__, product_id))
