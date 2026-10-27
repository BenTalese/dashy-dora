"""FU-317 Chunk 2 — the one authority for `Recipe.available_meals` mutation.

**One write-site, one floor rule.** Every caller that changes a recipe's
pool count goes through `bump_pool`. The historical drift (a raw SQL
CASE-WHEN in the sweep + inline `_Recipe.available_meals = …` in each
handler) collapses to a single primitive here.

Concretely this closes an R-003 drift called out in the FU-317 proposal
§5.1: the sweep and `cook_recipe`/`adjust_recipe_meals` used to encode
the floor-at-zero rule independently — one in SQL, two in Python. If
one ever changed and the others didn't, the pool would silently disagree
with itself.

`bump_pool` accepts an optional connection so the same code path serves
both worlds:

- **ORM callers** (`cook_recipe`, `adjust_recipe_meals`) pass no
  connection and let the UPDATE run on the current Flask-SQLAlchemy
  session; the `save_changes()` at the end of the handler commits it
  alongside any other ORM work. Any already-loaded `Recipe` entity's
  Python `available_meals` attribute becomes STALE after this call —
  callers should read the returned int, not the entity attribute.

- **The connection-level sweep** (`reconcile_consumed_meals`) passes its
  own decoupled connection so the update participates in the sweep's
  own transaction, not the per-request ORM session.

`RETURNING available_meals` gives us the post-update value in one
round-trip, which lets us honour the floor without a follow-up SELECT.
The SQL is portable to both SQLite ≥ 3.35 and Postgres.
"""
from typing import Any
from uuid import UUID

from sqlalchemy import text

from dora_api.app import db
from dora_api.persistence.uuid_key import uuid_bind


def preview_pool_after(current: int | None, delta: int) -> int:
    """Return the pool value `bump_pool` would land on, without touching
    the DB. Used by preview surfaces (e.g. the assistant's confirm-action
    step) so the number shown to the user matches what the write will
    do, byte-for-byte. Floor rule stays here — same as `bump_pool`'s
    SQL CASE WHEN below.
    """
    return max(0, (current or 0) + delta)


def bump_pool(recipe_id: UUID | bytes | str, delta: int,
              *, connection: Any = None) -> int:
    """Atomically add `delta` to `Recipe.available_meals`, floored at 0.

    Returns the new pool value. Idempotent-friendly: a `delta` of 0 is
    a valid no-op that returns the current value.

    - `recipe_id` may be a `UUID`, a `str`, or SQLite's raw `bytes`;
      `uuid_bind` gives the backend's raw-`text()` bind form.
    - `connection` is a SQLAlchemy `Connection` object; when omitted the
      update runs on `db.session` and is committed by the caller's
      `save_changes()`.
    """
    executor = connection if connection is not None else db.session
    _DialectName = connection.dialect.name if connection is not None \
        else db.engine.dialect.name
    _Bind = uuid_bind(recipe_id, _DialectName)
    stmt = text(
        'UPDATE "Recipe" '
        "SET available_meals = CASE "
        "  WHEN available_meals + :d < 0 THEN 0 "
        "  ELSE available_meals + :d "
        "END "
        "WHERE id = :rid "
        "RETURNING available_meals"
    )
    params = {"d": delta, "rid": _Bind}
    result = executor.execute(stmt, params).scalar_one()
    return int(result)
