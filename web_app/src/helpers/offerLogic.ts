/** "On special" and "% off" for one offer: a saved Product, a historic offer,
 *  anything with `price_now` / `price_was`. The server's ranking rule is
 *  `domain/product_offer.discount_percent`; this is its display twin (the
 *  accepted Type-C carve-out), the one client copy every surface uses. */
type OfferPrices = { price_now: number | null | undefined; price_was: number | null | undefined };

/** Whether the offer carries a real price. A product the producer pushed
 *  with no offer (out of stock, price unknown) holds a $0 placeholder, which
 *  must read as "No price yet", never as free (16-D2). */
export function hasPrice(offer: OfferPrices): boolean {
    return offer.price_now != null && offer.price_now > 0;
}

export const NO_PRICE_YET = 'No price yet';

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
