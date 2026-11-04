"""Server-side resolver for "which list does a quick-add land on?"

There is no list the user marks as their main one — that stored flag was
dropped in P6-01 Chunk 2. The target is inferred from how many DRAFT lists
exist. The rule (shared by `/quick-add/lines` and the C-7 cart button):

  - 0 draft lists  -> NONE      (the client must create a list first)
  - 1 draft list   -> SINGLE    (quick-add lands silently)
  - 2+ draft lists -> AMBIGUOUS (the client asks; sessionStorage remembers)

SHOPPING and DONE lists never count as quick-add targets — quick-add is the
"add it to my next shop" flow, not the in-store ticking flow.

The resolver is a pure function over a list of ShoppingList rows so callers can
reuse the same draft set they already loaded.
"""
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Literal
from uuid import UUID

from dora_api.domain.entities.shopping_list import (SHOPPING_LIST_STATUS_DRAFT,
                                                    ShoppingList)

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
    drafts = [l for l in lists if l.status == SHOPPING_LIST_STATUS_DRAFT]
    if not drafts:
        return QuickAddTargetOutcome(kind="none")
    if len(drafts) == 1:
        return QuickAddTargetOutcome(kind="single", target_list_id=drafts[0].id)
    drafts.sort(key=lambda l: l.created_at)
    return QuickAddTargetOutcome(
        kind="ambiguous",
        candidates=[
            # The label, not `name`: candidates are shown in a "which list?"
            # picker, so a self-labelled list must read as its date, not None.
            QuickAddTargetCandidate(shopping_list_id=l.id, name=label(l))
            for l in drafts
        ],
    )
