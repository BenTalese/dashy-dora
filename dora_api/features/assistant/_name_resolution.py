"""How the assistant turns a spoken name into a row: an exact
(case-insensitive) match wins outright, else a substring match, so "milk"
finds "Full cream milk". One rule for every tool and proposer (finalisation
11-R9/R10/R36; it was written eight times with three return shapes)."""
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from dora_api.domain.entities.stock_item import StockItem
from dora_api.persistence.field import EntityField

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class NameResolution(Generic[T]):
    matches: list[T]
    exact: bool

    @property
    def single(self) -> T | None:
        """The one match, or None when there are none or several."""
        return self.matches[0] if len(self.matches) == 1 else None


def resolve_by_name(query: Callable[[], Any], entity: type, name: str) -> NameResolution:
    """`query` builds a fresh repository query each call: the builder keeps
    its conditions, so reusing one across both lookups would AND them."""
    field = EntityField(entity, "name")
    exact = query().all(field.eq(name))
    if exact:
        return NameResolution(matches=exact, exact=True)
    return NameResolution(matches=query().all(field.contains(name)), exact=False)


def stock_item_candidate(item: StockItem) -> dict[str, Any]:
    """A stock item offered back when a name matched more than one."""
    return {
        "stock_item_id": str(item.id),
        "name": item.name,
        "location": item.stock_location.name if item.stock_location else None,
        "stock_level": item.stock_level.name if item.stock_level else None,
    }
