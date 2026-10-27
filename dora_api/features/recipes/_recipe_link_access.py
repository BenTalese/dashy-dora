"""Read/write helpers for a recipe vocabulary link table: a pure
(recipe_id, <vocab>_id) association with no standalone entity, matching the
StockItemSubstitute / StockItemProduct pattern (R-005 carve-out: Core SQL over
the mapped tables, portable to SQLite and Postgres).

`RecipeTag` (dietary tags) and `RecipeTool` (kitchen tools) are the same nine
operations over a different pair of tables (finalisation 01-R6), so both
modules are thin instances of `RecipeLinkAccess`. Write helpers validate ids
against the vocabulary table; an unknown id raises `ValueError`, which the
request layer turns into a 400.
"""
from collections import defaultdict
from typing import Iterable
from uuid import UUID

from sqlalchemy import func, select

from dora_api.app import db


def _coerce_uuid(value) -> UUID | None:
    """Best-effort coercion to UUID; None on anything unparseable so filter
    paths can skip junk rather than 500."""
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


class RecipeLinkAccess:
    def __init__(self, link_table: str, vocab_table: str, fk_column: str, unknown_message: str) -> None:
        """`unknown_message` is formatted with the offending raw value as
        `{raw}` for the 400 a bad id gets."""
        self.link_table = link_table
        self.vocab_table = vocab_table
        self.fk_column = fk_column
        self.unknown_message = unknown_message

    def _link(self):
        return db.metadata.tables[self.link_table]

    def _vocab(self):
        return db.metadata.tables[self.vocab_table]

    def _all_ids(self) -> set[UUID]:
        return {row[0] for row in db.session.execute(select(self._vocab().c.id)).all()}

    def _name_to_id(self) -> dict[str, UUID]:
        vocab = self._vocab()
        rows = db.session.execute(select(vocab.c.name, vocab.c.id)).all()
        return {name.strip().lower(): entry_id for name, entry_id in rows}

    def validate_ids(self, ids: Iterable) -> list[UUID]:
        """A deduped list of valid ids; raises ValueError on the first id that
        doesn't exist so the caller can surface a precise error."""
        known = self._all_ids()
        seen: set[UUID] = set()
        out: list[UUID] = []
        for raw in ids:
            coerced = _coerce_uuid(raw)
            if coerced is None or coerced not in known:
                raise ValueError(self.unknown_message.format(raw=raw))
            if coerced not in seen:
                seen.add(coerced)
                out.append(coerced)
        return out

    def resolve_filter_values(self, values: Iterable[str]) -> set[UUID]:
        """Map filter inputs (ids OR human-friendly names) to ids, silently
        dropping anything that matches neither. Lets the SPA pass ids and
        Dora's tools pass names through the same filter path."""
        known = self._all_ids()
        by_name = self._name_to_id()
        out: set[UUID] = set()
        for raw in values:
            coerced = _coerce_uuid(raw)
            if coerced is not None and coerced in known:
                out.add(coerced)
                continue
            named = by_name.get(str(raw).strip().lower())
            if named is not None:
                out.add(named)
        return out

    def ids_for_recipes(self, recipe_ids: Iterable[UUID]) -> dict[UUID, list[UUID]]:
        """`{recipe_id: [id, ...]}`; a missing key means no links."""
        ids = list(recipe_ids)
        if not ids:
            return {}
        link = self._link()
        rows = db.session.execute(
            select(link.c.recipe_id, link.c[self.fk_column])
            .where(link.c.recipe_id.in_(ids))
            .order_by(link.c.recipe_id)
        ).all()
        bucketed: dict[UUID, list[UUID]] = defaultdict(list)
        for recipe_id, entry_id in rows:
            bucketed[recipe_id].append(entry_id)
        return dict(bucketed)

    def ids_for_recipe(self, recipe_id: UUID) -> list[UUID]:
        return self.ids_for_recipes([recipe_id]).get(recipe_id, [])

    def set_ids_for_recipe(self, recipe_id: UUID, ids: Iterable) -> None:
        """Replace the recipe's link set. Idempotent. Validates each id; the
        caller catches ValueError."""
        valid = self.validate_ids(ids)
        link = self._link()
        db.session.execute(link.delete().where(link.c.recipe_id == recipe_id))
        if valid:
            db.session.execute(
                link.insert(),
                [{"recipe_id": recipe_id, self.fk_column: entry_id} for entry_id in valid],
            )

    def recipe_ids_with_all(self, ids: Iterable) -> set[UUID]:
        """Recipes linked to *every* id in the input (a multi-select means
        "fits all of these")."""
        wanted = list(self.resolve_filter_values(ids))
        if not wanted:
            return set()
        link = self._link()
        fk = link.c[self.fk_column]
        rows = db.session.execute(
            select(link.c.recipe_id)
            .where(fk.in_(wanted))
            .group_by(link.c.recipe_id)
            .having(func.count(fk.distinct()) == len(wanted))
        ).all()
        return {row[0] for row in rows}

    def recipe_ids_with_any(self, ids: Iterable) -> set[UUID]:
        """Recipes linked to at least one id (the exclude axis)."""
        wanted = list(self.resolve_filter_values(ids))
        if not wanted:
            return set()
        link = self._link()
        rows = db.session.execute(
            select(link.c.recipe_id.distinct()).where(link.c[self.fk_column].in_(wanted))
        ).all()
        return {row[0] for row in rows}
