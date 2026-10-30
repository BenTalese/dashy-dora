// The expiry indicator — one tone/icon/colour answer, shared by every
// surface that shows "when does this go off?".
//
// R-002: this used to live inline in `StockItemRow.vue`. The stock-item
// detail page now shows the same indicator on its Expiry row (feedback
// 2026-08-16 — "use the iconography found on the overview"), and a second
// copy of the 7-day threshold + colour mapping is exactly the drift the rule
// exists to stop. Anything else needing an expiry glyph imports from here.
//
// Note the threshold itself: "soon" is within 7 days. That is a *display*
// band for a date the client already holds, not a domain rule the server
// owns — the alert/attention engine has its own server-side definition, and
// this one only decides which icon to draw.
import { formatDate } from 'src/composables/useDateFormat';
import { ICONS } from 'src/style/icons';
import { daysFromToday } from 'src/helpers/weekDates';

export type ExpiryTone = 'none' | 'ok' | 'soon' | 'expired';

const SOON_WINDOW_DAYS = 7;

export function expiryToneFor(expiryDate: string | null | undefined): ExpiryTone {
    if (!expiryDate) return 'none';
    // Calendar days, not elapsed hours: `new Date('YYYY-MM-DD')` is UTC
    // midnight, which flipped an item expiring today to "Expired" mid-morning
    // east of Greenwich. An item is good through its expiry date.
    const days = daysFromToday(expiryDate.slice(0, 10));
    if (days === null) return 'none';
    if (days < 0) return 'expired';
    if (days <= SOON_WINDOW_DAYS) return 'soon';
    return 'ok';
}

export type ExpiryIndicator = {
    tone: ExpiryTone;
    icon: string;
    /** Quasar palette name, or null for "no colour — use `cssClass`". */
    colour: string | null;
    cssClass: string | null;
    tooltip: string;
};

/** R-002: neutral "no expiry" routes through `dora-text-muted` rather than a
 *  raw colour; the saturated branches stay on Quasar semantic names. */
export function expiryIndicatorFor(
    expiryDate: string | null | undefined,
): ExpiryIndicator {
    const tone = expiryToneFor(expiryDate);
    // D-006: the date is user-facing here (tooltip, and the expiry menu's
    // header reuses this same string), so it goes through the one formatting
    // authority rather than echoing the raw ISO value.
    const when = formatDate(expiryDate);
    switch (tone) {
        case 'expired':
            return {
                tone,
                icon: ICONS.error,
                colour: 'negative',
                cssClass: null,
                tooltip: `Expired ${when}`,
            };
        case 'soon':
            return {
                tone,
                icon: ICONS.event_busy,
                colour: 'warning',
                cssClass: null,
                tooltip: `Expires ${when}`,
            };
        case 'ok':
            return {
                tone,
                icon: ICONS.event_available,
                colour: 'positive',
                cssClass: null,
                tooltip: `Expires ${when}`,
            };
        case 'none':
        default:
            return {
                // An *empty* calendar, not the ticked one. `ok` and `none`
                // used to share `event_available` and differ only by colour,
                // so a far-future expiry and no-expiry-at-all read the same
                // at a glance (owner feedback 2026-08-27).
                tone,
                icon: ICONS.event_blank,
                colour: null,
                cssClass: 'dora-text-muted',
                tooltip: 'No expiry set',
            };
    }
}
