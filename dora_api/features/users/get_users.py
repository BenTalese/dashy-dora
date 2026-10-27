import logging
from dataclasses import dataclass
from uuid import UUID

from flask import request
from sqlalchemy import select

from dora_api.app import db
from dora_api.domain.entities.user import User
from dora_api.features.routers import USER_ROUTER
from dora_api.infrastructure.api_response import bad_request, paginated
from dora_api.infrastructure.query_options import (InvalidQueryParameter,
                                                   parse_query_options)
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.infrastructure.ports import Repository

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UserDto:
    email: str | None
    send_deals_on_day: int
    username: str
    user_id: UUID
    is_admin: bool
    # Deactivate-instead-of-delete. The admin list is the only surface that
    # renders it — everywhere else an inactive user simply can't sign in.
    is_active: bool
    deals_email_enabled: bool
    # Settings rebuild Phase 4 — bulk-stamped from an IS-NOT-NULL select (see
    # `_stamp_has_image`) so the user list never triggers the deferred
    # profile-picture blob per row. Mirrors StoreDto / StockItemDto.
    has_image: bool = False

    @classmethod
    def from_entity(cls, user: User) -> 'UserDto':
        return UserDto(
            email = user.email,
            send_deals_on_day = user.send_deals_on_day,
            username = user.username,
            user_id = user.id,
            is_admin = bool(user.is_admin),
            is_active = bool(user.is_active),
            deals_email_enabled = bool(user.deals_email_enabled),
            has_image = False,
        )


_FIELD_MAP: dict[str, EntityField] = {
    "user_id": EntityField(User, "id"),
}


def _stamp_has_image(repository, dtos: list[UserDto]) -> None:
    """Bulk-derive `has_image` from a single IS-NOT-NULL select so the list
    never loads the deferred image blob per row (mirrors StoreDto)."""
    if not dtos:
        return
    user_ids = [d.user_id for d in dtos]
    user_table = db.metadata.tables["User"]
    rows = repository.session.execute(
        select(user_table.c.id, user_table.c.image.isnot(None))
        .where(user_table.c.id.in_(user_ids))
    ).all()
    flag_by_id = {row[0]: bool(row[1]) for row in rows}
    # Frozen dataclass — write through object.__setattr__ rather than rebuild.
    for dto in dtos:
        object.__setattr__(dto, "has_image", flag_by_id.get(dto.user_id, False))


class GetUsersHandler:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def handle(self, options) -> Page[UserDto]:
        page = self.repository.get(User).paginate(
            options, UserDto.from_entity, field_map=_FIELD_MAP
        )
        _stamp_has_image(self.repository, page.items)
        return page


@USER_ROUTER.route("")
def get_users():
    # Admin-only — non-admin users shouldn't be able to enumerate accounts.
    from dora_api.features.auth.admin_gate import require_admin
    _, err = require_admin()
    if err is not None:
        return err
    try:
        _Options = parse_query_options(request.args)
        _Page = GetUsersHandler(SqlAlchemyRepository()).handle(_Options)
    except InvalidQueryParameter as exc:
        return bad_request(str(exc))
    _LOGGER.info("Retrieved %d of %d users.", len(_Page.items), _Page.total)
    return paginated(_Page.items, _Page.total, _Page.page, _Page.limit)
