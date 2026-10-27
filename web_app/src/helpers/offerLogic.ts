/** "On special" and "% off" for one offer: a saved Product, a historic offer,
 *  anything with `price_now` / `price_was`. The server's ranking rule is
 *  `domain/product_offer.discount_percent`; this is its display twin (the
 *  accepted Type-C carve-out), the one client copy every surface uses. */
type OfferPrices = { price_now: number | null | undefined; price_was: number | null | undefined };

export function isOnSpecial(offer: OfferPrices): boolean {
    return discountPercent(offer) !== null;
}

/** Whole-percent discount when the offer is genuinely cheaper than its
 *  ticket, else null (no price, no RRP, or not actually cheaper). */
export function discountPercent(offer: OfferPrices): number | null {
    const now = offer.price_now;
    const was = offer.price_was;
    if (now == null || was == null || was <= 0 || now <= 0 || now >= was) return null;
    return Math.round(((was - now) / was) * 100);
}
