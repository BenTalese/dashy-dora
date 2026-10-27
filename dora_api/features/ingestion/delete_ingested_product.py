"""`DELETE /api/ingest/products/<id>` — the companion's "unsave".

PF-4 says unsaving deletes through the same path Dora's own UI uses, and it
does: this route is a thin bearer-authenticated front door onto
`products.delete_product.DeleteProductHandler`. There is exactly one delete
*behaviour* — cascade rules, shopping-line retention, all of it — and two ways
in, because the two callers authenticate differently:

* Dora's SPA holds a `dora_session` cookie → `DELETE /api/products/<id>`
* an ingestion source holds a bearer key → this route

An ingestion source is an ordinary external client (PF-9), so it gets no
privilege the SPA lacks; it just can't present a session cookie. The same split
already exists on the read side — `/api/ingest/link-status` is the bearer-authed
door onto product lookups.

The caller supplies Dora's own `product_id`, which is what
`/api/ingest/link-status` hands back for a product Dora already holds — so the
companion decorates its search results, then unsaves by the id it was given. No
new identity scheme.
"""
from __future__ import annotations

import logging
from uuid import UUID

from dora_api.domain.entities.product import Product
from dora_api.features.products.delete_product import DeleteProductHandler
from dora_api.features.routers import INGEST_ROUTER
from dora_api.infrastructure.api_response import forbidden, no_content, not_found
from dora_api.infrastructure.ingestion_auth import (
    authenticate_ingestion_request, stamp_used)
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


_LOGGER = logging.getLogger(__name__)


@INGEST_ROUTER.route(
    "/products/<uuid:product_id>", methods=["DELETE"],
    endpoint="ingest_delete_product",
)
def ingest_delete_product(product_id: UUID):
    # FU-866 — one shared check: authenticate, then honour the
    # install-wide ingestion switch. Both live in `ingestion_auth` so a
    # new ingest route cannot quietly skip the gate.
    source, auth_error = authenticate_ingestion_request()
    if auth_error is not None:
        return auth_error

    repository = SqlAlchemyRepository()

    # OD-2 defence in depth — a hand-entered product is the user's own and is
    # removed from Dora itself, never by a producer. `link-status` no longer
    # hands a custom product's id out (finalisation 16-R8), but a producer may
    # still hold one from before, or guess; refuse rather than delete.
    target = repository.get(Product).by_id(product_id)
    if target is not None and target.is_custom:
        _LOGGER.warning(
            "Source %s asked to delete custom product %s; refused.", source.id, product_id,
        )
        return forbidden("A hand-entered product can only be removed from Dora itself.")

    response = DeleteProductHandler(repository).handle(product_id)

    if response.product_not_found:
        _LOGGER.warning(
            "Source %s asked to delete unknown product %s.", source.id, product_id,
        )
        return not_found(Product.__name__, product_id)

    stamp_used(source)
    repository.save_changes()

    _LOGGER.info("Source %s deleted product %s.", source.id, product_id)
    return no_content()
