from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy.orm import registry


class BoolOperation:
    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        raise NotImplementedError

    def _resolve(self, expression, case_sensitive: bool = True) -> ColumnElement | Any:
        from dora_api.persistence.field import EntityField

        if isinstance(expression, EntityField):
            return expression.to_sqla(case_sensitive)
        if isinstance(expression, BoolOperation):
            raise ValueError("Nested BoolOperation passed where a value was expected — wrap with And/Or instead.")
        if isinstance(expression, str):
            return expression.lower() if not case_sensitive else expression
        return expression  # int, float, bool, datetime, etc.

    # Operator overloads so BoolOperations compose naturally
    def __and__(self, other: 'BoolOperation') -> 'And':
        return And(self, other)

    def __or__(self, other: 'BoolOperation') -> 'Or':
        return Or(self, other)

    def __invert__(self) -> 'Not':
        return Not(self)


# ── Comparison operations ──────────────────────────────────────────────────────

# LIKE wildcards in a user's search text must match literally ("100%" is not
# "100 then anything"). Escaped with an explicit ESCAPE char so it behaves the
# same on SQLite and Postgres (R-005).
_LIKE_ESCAPE = "\\"


def _escape_like(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return (
        value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE + _LIKE_ESCAPE)
        .replace("%", _LIKE_ESCAPE + "%")
        .replace("_", _LIKE_ESCAPE + "_")
    )


class Equal(BoolOperation):
    def __init__(self, field, value, case_sensitive: bool = False):
        self.field = field
        self.value = value
        self.case_sensitive = case_sensitive

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field, self.case_sensitive) == self._resolve(self.value, self.case_sensitive)


class NotEqual(BoolOperation):
    def __init__(self, field, value, case_sensitive: bool = False):
        self.field = field
        self.value = value
        self.case_sensitive = case_sensitive

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field, self.case_sensitive) != self._resolve(self.value, self.case_sensitive)


class Greater(BoolOperation):
    def __init__(self, field, value):
        self.field = field
        self.value = value

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field) > self._resolve(self.value)


class Less(BoolOperation):
    def __init__(self, field, value):
        self.field = field
        self.value = value

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field) < self._resolve(self.value)


class GreaterOrEqual(BoolOperation):
    def __init__(self, field, value):
        self.field = field
        self.value = value

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field) >= self._resolve(self.value)


class LessOrEqual(BoolOperation):
    def __init__(self, field, value):
        self.field = field
        self.value = value

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field) <= self._resolve(self.value)


class IsNull(BoolOperation):
    def __init__(self, field):
        self.field = field

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field).is_(None)


class IsNotNull(BoolOperation):
    def __init__(self, field):
        self.field = field

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field).is_not(None)


class In(BoolOperation):
    def __init__(self, field, values: list):
        self.field = field
        self.values = values

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field).in_(self.values)


class NotIn(BoolOperation):
    def __init__(self, field, values: list):
        self.field = field
        self.values = values

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field).not_in(self.values)


class Between(BoolOperation):
    def __init__(self, field, lower, upper):
        self.field = field
        self.lower = lower
        self.upper = upper

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return self._resolve(self.field).between(self.lower, self.upper)


class Contains(BoolOperation):
    """Case-insensitive substring match (`LIKE '%value%'`).

    Always case-insensitive (FU-523): SQLite's `LIKE` is ASCII-case-insensitive
    regardless of the value, so a *case-sensitive* LIKE can't be expressed
    portably across SQLite + Postgres. Both the column and the value are lowered
    (via `_resolve`, the single source of casing) so the match is identical on
    either backend (R-005) — the old code lowered only the column and, worse,
    inverted the value-side flag, so an upper-case value silently missed on
    Postgres (whose LIKE is case-sensitive).
    """
    def __init__(self, field, value: str):
        self.field = field
        self.value = value

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        col = self._resolve(self.field, case_sensitive=False)
        val = _escape_like(self._resolve(self.value, case_sensitive=False))
        return col.like(f"%{val}%", escape=_LIKE_ESCAPE)


class StartsWith(BoolOperation):
    """Case-insensitive prefix match (`LIKE 'value%'`). Always case-insensitive
    for the same portability reason as `Contains` (FU-523); both column and
    value are lowered."""
    def __init__(self, field, value: str):
        self.field = field
        self.value = value

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        col = self._resolve(self.field, case_sensitive=False)
        val = _escape_like(self._resolve(self.value, case_sensitive=False))
        return col.like(f"{val}%", escape=_LIKE_ESCAPE)


# ── Logical operations ─────────────────────────────────────────────────────────

class Not(BoolOperation):
    def __init__(self, expression: BoolOperation):
        self.expression = expression

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        return ~self.expression.to_sqla(mapper_registry)


class And(BoolOperation):
    def __init__(self, *expressions: BoolOperation):
        if len(expressions) < 2:
            raise ValueError("And requires at least two expressions.")
        self.expressions = expressions

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        from sqlalchemy import and_
        return and_(*[e.to_sqla(mapper_registry) for e in self.expressions])


class Or(BoolOperation):
    def __init__(self, *expressions: BoolOperation):
        if len(expressions) < 2:
            raise ValueError("Or requires at least two expressions.")
        self.expressions = expressions

    def to_sqla(self, mapper_registry: registry) -> ColumnElement:
        from sqlalchemy import or_
        return or_(*[e.to_sqla(mapper_registry) for e in self.expressions])
