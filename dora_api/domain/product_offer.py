"""Product-offer pricing rules (server side).

`discount_percent` is the server's single source for "how good is this deal",
used to rank the weekly deals email and the price-history card. Mirrors the
client `discountPercent` (`helpers/offerLogic.ts`): the client keeps its copy
for *display* (the accepted Type-C carve-out), the server owns the *ranking*.
"""
from __future__ import annotations

from typing import Optional


def discount_percent(price_now: Optional[float], price_was: Optional[float]) -> Optional[int]:
    """Whole-percent discount (0–100) when the offer is genuinely on special,
    else ``None`` (no RRP, no price, or not actually cheaper)."""
    if not price_was or not price_now:
        return None
    if price_was <= 0 or price_now <= 0 or price_now >= price_was:
        return None
    return round((price_was - price_now) / price_was * 100)
