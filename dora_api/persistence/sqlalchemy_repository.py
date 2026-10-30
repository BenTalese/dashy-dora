from dataclasses import fields
from datetime import date, datetime
from typing import Any, Callable, Generic, List
from uuid import UUID, uuid4

from sqlalchemy import Select, func, inspect as sa_inspect, select
from sqlalchemy.orm import contains_eager, registry

from dora_api.app import db
from dora_api.domain.entities.base_entity import BaseEntity
from dora_api.domain.exceptions import PersistenceError
from dora_api.domain.generics import TEntity
from dora_api.domain.types import EMPTY_UUID
from dora_api.infrastructure.query_options import (FilterClause,
                                                   InvalidQueryParameter,
                                                   QueryOptions)
from dora_api.persistence.bool_operation import BoolOperation
from dora_api.persistence.field import EntityField
from dora_api.persistence.page import Page
from dora_api.persistence.table_mappings import _mapper_registry


class SqlAlchemyRepository:

    @property
    def session(self):
        """Escape hatch for complex queries that the builder can't express cleanly."""
        return db.session

    def add(self, entity: BaseEntity) -> None:
        def is_not_persisted(entity: BaseEntity) -> bool:
            return entity.id == EMPTY_UUID
        # Catch inline-constructed related entities that were never added
        for f in fields(entity):
            value = getattr(entity, f.name)
            if isinstance(value, BaseEntity) and is_not_persisted(value):
                raise PersistenceError(
                    f"{type(entity).__name__}.{f.name} has not been persisted. "
                    f"Call repo.add() on it before adding {type(entity).__name__}."
                )

        entity.id = uuid4()
        db.session.add(entity)

    def get(self, entity_type: type[TEntity]) -> 'SqlAlchemyQueryBuilder[TEntity]':
        return SqlAlchemyQueryBuilder(entity_type, _mapper_registry)

    def reattach_and_save(self, entity: BaseEntity) -> None:
        """Use when an entity was loaded outside the current session.
        Example: Loaded in a previous request, serialised, sent to frontend,
        modified, sent back, deserialised — session has no idea about it"""
        db.session.merge(entity)

    def remove(self, entity: BaseEntity):
        db.session.delete(entity)

    def flush(self):
        """Materialise pending inserts on the wire without committing.
        Use before adding a *child* row (any row with an FK to a pending
        *parent* row added earlier in the same unit of work): the classic
        mapper doesn't know the two entities depend on each other unless
        a ``relationship()`` links them, so SQLite's FK check can fire on
        the child before the parent has hit the DB. The narrower fix
        (a relationship on every event/log mapping) is out of scope for
        the pre-release drift work; ``flush()`` here is the local
        contract."""
        db.session.flush()

    def save_changes(self):
        db.session.commit()


class SqlAlchemyQueryBuilder(Generic[TEntity]):
    '''
    Example usage:
    ```python
    results = (
        self.repository
        .get(ShoppingList)
        .include("items")
            .then_include("stock_level")
            .then_include("stock_location")
        .where(
            And(
                Or(
                    Field(StockItem, "stocktake_alerts_are_enabled").eq(True),
                    Field(StockLevel, "sequence").gte(0),
                ),
                Field(StockItem, "name").contains("a"),
                Not(Field(StockLocation, "name").eq("freezer")),
                Field(StockLevel, "sequence").between(1, 3),
            )
        )
        .all()
    )

    results = (
        self.repository
        .get(Product)
        .include("store")
        .include("current_offer")
        .where(
            Field(Product, "is_active").eq(True)
            & Field(Product, "is_available").eq(True)
            & (
                Field(Store, "name").eq("woolworths") |
                Field(Store, "name").eq("coles")
            )
            & (
                Field(ProductOffer, "price_now").between(1.0, 50.0) |
                Field(ProductOffer, "price_now").lt(Field(ProductOffer, "price_was"))
            )
            & (
                Field(Product, "name").contains("cake") |
                Field(Product, "name").contains("mix")
            )
            & Field(Product, "web_url").is_not_null()
            & ~Field(Product, "brand").eq("cadbury")
        )
        .all()
    )
    ```
    '''
    def __init__(self, entity_type: type[TEntity], mapper_registry: registry):
        self._mapper_registry = mapper_registry
        self.entity_type = entity_type
        self.query: Select = select(entity_type)
        self.join_paths: dict[str, list] = {}
        self._included_entity: type | None = None
        self._included_path: str = ""
        self._included_chain: list = []
        self._is_partial = False

    def all(self, condition: BoolOperation | None = None) -> List[TEntity]:
        if condition:
            return self.where(condition).all()
        return self._execute()

    def by_id(self, entity_id: UUID) -> TEntity | None:
        return self.one(EntityField(self.entity_type, "id").eq(entity_id))

    def count(self, condition: BoolOperation | None = None) -> int:
        """Return the total count of rows matching the current filters.

        Strips includes/joins for an accurate root-entity count.
        """
        if condition:
            return self.where(condition).count()
        count_query = select(func.count()).select_from(
            self.query.with_only_columns(
                getattr(self.entity_type, "id")
            ).order_by(None).subquery()
        )
        return db.session.execute(count_query).scalar_one()

    def exists(self, entity_id: UUID) -> bool:
        return self.by_id(entity_id) is not None

    def include(self, attribute_name: str) -> 'SqlAlchemyQueryBuilder[TEntity]':
        attr = self._resolve_attribute(self.entity_type, attribute_name)

        if attribute_name not in self.join_paths:
            self.join_paths[attribute_name] = [attr]

        self._included_path = attribute_name
        self._included_chain = [attr]
        self._included_entity = self._get_related_entity(self.entity_type, attribute_name)
        return self

    def one(self, condition: BoolOperation | None = None) -> TEntity | None:
        result = self.where(condition)._execute() if condition else self._execute()
        return result[0] if result else None

    def project(self, projection_method: Callable) -> List[Any]:
        '''
        Full entity, project in Python
        repo.get(Product).project(lambda p: p.name)
        repo.get(Store).project(to_dto)

        Column-level, project from dict-like row
        repo.get(Product)\
            .select(Field(Product, "name"), Field(Product, "web_url"))\
            .where(Field(Product, "is_active").eq(True))\
            .project(lambda row: {"name": row["name"], "web_url": row["web_url"]})
        '''
        if self._is_partial:
            results = db.session.execute(self.query).all()
            return [projection_method(row._mapping) for row in results]
        return [projection_method(entity) for entity in self._execute()]

    def select(self, *fields: EntityField) -> 'SqlAlchemyQueryBuilder[TEntity]':
        self.query = self.query.with_only_columns(*[f.to_sqla() for f in fields])
        self._is_partial = True
        return self

    def then_include(self, attribute_name: str) -> 'SqlAlchemyQueryBuilder[TEntity]':
        if not self._included_entity:
            raise PersistenceError("Call include() before then_include().")

        attr = self._resolve_attribute(self._included_entity, attribute_name)
        path_key = f"{self._included_path}.{attribute_name}"
        new_chain = self._included_chain + [attr]

        if path_key not in self.join_paths:
            self.join_paths[path_key] = new_chain

        self._included_path = path_key
        self._included_chain = new_chain
        self._included_entity = self._get_related_entity(self._included_entity, attribute_name)
        return self

    def where(self, condition: BoolOperation) -> 'SqlAlchemyQueryBuilder[TEntity]':
        self.query = self.query.where(condition.to_sqla(self._mapper_registry))
        return self

    def paginate(
        self,
        options: QueryOptions,
        projection: Callable[[TEntity], Any],
        field_map: dict[str, EntityField] | None = None,
    ) -> Page:
        """Apply filter/sort/page/limit at the SQL layer and return a Page of
        projected items plus the total row count.

        `field_map` maps API field names (typically DTO attributes) to the
        EntityField they correspond to. Fields not in the map fall back to a
        column on the root entity with the same name.
        """
        # Apply filters as SQL WHERE clauses.
        for clause in options.filters:
            condition = self._build_filter_condition(clause, field_map)
            self.query = self.query.where(condition.to_sqla(self._mapper_registry))

        # Resolve and apply sort. `id` is always appended as a stable tiebreaker
        # so pagination is deterministic across requests, and so the same
        # ordering can be used on Postgres alongside any DISTINCT clauses.
        id_column = getattr(self.entity_type, "id")
        if options.sort:
            sort_field = self._resolve_field(options.sort.field, field_map)
            column = sort_field._col()
            # Empty values sort last in both directions. Without an explicit
            # rule the order is the backend's: SQLite puts NULL first on ASC,
            # Postgres last, so the same page differed by datastore.
            primary = column.asc() if options.sort.direction == "asc" else column.desc()
            primary = primary.nulls_last()
            self.query = self.query.order_by(primary, id_column.asc())
        else:
            self.query = self.query.order_by(id_column.asc())

        total = self.count()

        # Apply pagination over root-entity ids. No DISTINCT is needed because
        # this query only selects from the root table (joins for eager-loading
        # are applied later to the full-entity reload).
        id_query = (
            self.query
            .with_only_columns(id_column)
            .offset(options.offset)
            .limit(options.limit)
        )
        page_ids: list[UUID] = list(db.session.execute(id_query).scalars())

        if not page_ids:
            return Page(items=[], total=total, page=options.page, limit=options.limit)

        # Reload the full entities (with eager joins) restricted to the page ids.
        full_query: Select = select(self.entity_type).where(
            getattr(self.entity_type, "id").in_(page_ids)
        )
        for chain in self.join_paths.values():
            for attr in chain:
                full_query = full_query.outerjoin(attr)
            option = contains_eager(chain[0])
            for attr in chain[1:]:
                option = option.contains_eager(attr)
            full_query = full_query.options(option)

        # Preserve the order returned by the sorted/paginated id query.
        results = db.session.execute(full_query).unique().all()
        by_id = {row[0].id: row[0] for row in results}
        ordered = [by_id[i] for i in page_ids if i in by_id]

        return Page(
            items=[projection(e) for e in ordered],
            total=total,
            page=options.page,
            limit=options.limit,
        )

    # ── Filter parsing ────────────────────────────────────────────────────────

    def _resolve_field(
        self,
        api_field: str,
        field_map: dict[str, EntityField] | None,
    ) -> EntityField:
        if field_map and api_field in field_map:
            return field_map[api_field]
        # Strict allowlist fallback (FU-546): a field off `field_map` is only
        # usable if it's a genuine mapped COLUMN of this entity. The old
        # `hasattr()` check was a soft allowlist — it admitted ANY attribute,
        # so a dunder (`__class__`) or a relationship/hybrid flowed into the
        # query builder and 500'd (a crash on crafted input + a 400-vs-500 leak
        # fingerprinting internal attributes). Restricting to `column_attrs`
        # means relationships / properties / dunders all become a clean 400.
        # (The `_`-prefix underscore-FK columns aren't public API field names —
        # those are reached via field_map — so excluding them is intended.)
        if not api_field.startswith("_"):
            _column_keys = {a.key for a in sa_inspect(self.entity_type).column_attrs}
            if api_field in _column_keys:
                return EntityField(self.entity_type, api_field)
        raise InvalidQueryParameter(
            f"Field '{api_field}' is not filterable on '{self.entity_type.__name__}'."
        )

    def _build_filter_condition(
        self,
        clause: FilterClause,
        field_map: dict[str, EntityField] | None,
    ) -> BoolOperation:
        ef = self._resolve_field(clause.field, field_map)
        coerced = self._coerce_filter_value(ef, clause.value, clause.operator)
        op = clause.operator
        if op == "eq":
            return ef.eq(coerced)
        if op == "ne":
            return ef.ne(coerced)
        if op == "lt":
            return ef.lt(coerced)
        if op == "gt":
            return ef.gt(coerced)
        if op == "le":
            return ef.lte(coerced)
        if op == "ge":
            return ef.gte(coerced)
        if op == "ct":
            return ef.contains(str(coerced))
        raise InvalidQueryParameter(f"Unsupported filter operator '{op}'.")

    @staticmethod
    def _coerce_filter_value(ef: EntityField, raw: str, operator: str) -> Any:
        # "ct" is always a string LIKE; leave raw.
        if operator == "ct":
            return raw

        try:
            column = getattr(ef.entity_class, ef.attribute_name)
            python_type = column.property.columns[0].type.python_type
        except (AttributeError, NotImplementedError):
            return raw

        if python_type is bool:
            return raw.lower() in ("1", "true", "yes")
        if python_type is int:
            return int(raw)
        if python_type is float:
            return float(raw)
        if python_type is UUID:
            return UUID(raw)
        if python_type is datetime:
            return datetime.fromisoformat(raw)
        if python_type is date:
            return date.fromisoformat(raw)
        return raw

    def _execute(self) -> List[Any]:
        for chain in self.join_paths.values():
            # Add the joins
            for attr in chain:
                self.query = self.query.outerjoin(attr)

            # Build contains_eager chain
            # contains_eager(A).contains_eager(B).contains_eager(C)
            option = contains_eager(chain[0])
            for attr in chain[1:]:
                option = option.contains_eager(attr)

            self.query = self.query.options(option)

        results = db.session.execute(self.query).unique().all()
        return [row[0] for row in results]

    def _resolve_attribute(self, entity_type: type, attribute_name: str):
        if not hasattr(entity_type, attribute_name):
            raise PersistenceError(f"'{attribute_name}' not found on '{entity_type.__name__}'.")

        attr = getattr(entity_type, attribute_name)

        if not hasattr(attr, "property"):
            raise PersistenceError(f"'{attribute_name}' on '{entity_type.__name__}' is not a mapped relationship.")

        return attr

    def _get_related_entity(self, entity_type: type, attribute_name: str) -> type | None:
        attr = getattr(entity_type, attribute_name)
        if hasattr(attr, "property") and hasattr(attr.property, "mapper"):
            return attr.property.mapper.class_
        return None
