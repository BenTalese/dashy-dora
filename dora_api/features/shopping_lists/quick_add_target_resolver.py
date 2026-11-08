"""Server-side resolver for "which list does a quick-add land on?"

There is no list the user marks as their main one — that stored flag was
dropped in P6-01 Chunk 2. The target is inferred from how many active lists
exist. The rule (shared by `/quick-add/lines` and the C-7 cart button):

  - 0 active lists  -> NONE      (the client must create a list first)
  - 1 active list   -> SINGLE    (quick-add lands silently)
  - 2+ active lists -> AMBIGUOUS (the client asks; sessionStorage remembers)

Done lists never count: they are receipts. (Before UX v5 a list mid-shop
didn't count either; with draft and shopping merged there is nothing left to
tell apart.)

The resolver is a pure function over a list of ShoppingList rows so callers can
reuse the same set they already loaded.
"""
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Literal
from uuid import UUID

from dora_api.domain.entities.shopping_list import ShoppingList

QuickAddTargetKind = Literal["none", "single", "ambiguous"]


@dataclass(frozen=True, slots=True)
class QuickAddTargetCandidate:
    shopping_list_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class QuickAddTargetOutcome:
    kind: QuickAddTargetKind
    target_list_id: UUID | None = None
    candidates: List[QuickAddTargetCandidate] = field(default_factory=list)


def resolve_quick_add_target(
    lists: Iterable[ShoppingList], label: Callable[[ShoppingList], str],
) -> QuickAddTargetOutcome:
    active = [l for l in lists if l.is_active]
    if not active:
        return QuickAddTargetOutcome(kind="none")
    if len(active) == 1:
        return QuickAddTargetOutcome(kind="single", target_list_id=active[0].id)
    active.sort(key=lambda l: l.created_at)
    return QuickAddTargetOutcome(
        kind="ambiguous",
        candidates=[
            # The label, not `name`: candidates are shown in a "which list?"
            # picker, so a self-labelled list must read as its date, not None.
            QuickAddTargetCandidate(shopping_list_id=l.id, name=label(l))
            for l in active
        ],
    )
