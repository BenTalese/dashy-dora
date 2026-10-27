import { ICONS } from 'src/style/icons';
// Mirrors AlertDto/AlertsDto from dora_api/features/alerts/get_alerts.py.

export type AlertSeverity = 'high' | 'medium' | 'low';

// which count bucket an alert falls in: 'actionable' drives the bell
// badge, 'fyi' is shown but never counted into it.
export type AlertTier = 'actionable' | 'fyi';

// Eight kinds. `out_of_stock`, `low_stock` and `stocktake_overdue` were cut in
// the Step-0 alerts assessment (IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md) —
// they fired constantly on conditions already legible on the stock row or in
// the stocktake runner. `shopping_overdue` and `price_drop` joined 2026-10-15.
export type AlertKind =
    // per-item — these three ARE the stock-overview attention rule.
    | 'expired'
    | 'expiring_soon'
    | 'essential_low'
    // household-level nudges (no stock item).
    | 'no_planned_meals'
    | 'shopping_day'
    | 'shopping_overdue'
    | 'meal_reconcile_overdue'
    // per-user: a watched product reached its price.
    | 'price_drop';

export type Alert = {
    // Stable scoped key `<scope>:<id>:<variant>:<episode>` — opaque to the
    // client; posted back to the snooze/dismiss endpoints.
    alert_id: string;
    kind: AlertKind;
    severity: AlertSeverity;
    // Stock-scoped alerts carry the owning item; C-9.4 non-stock kinds null these.
    stock_item_id: string | null;
    stock_item_name: string | null;
    // Deep-link target id for non-stock kinds (the shopping list uuid, or the
    // product for `price_drop`).
    target_id: string | null;
    message: string;
    detail: string | null;
    related_date: string | null;
    /** ISO date the condition began. What the discard window measures. */
    started_on: string | null;
    /** A raw money amount the alert is about (price_drop's price). */
    amount: number | null;
    // Per-user interaction overlay (C-9.1, server-derived).
    snoozed_until: string | null;
    // Derived from `severity` server-side: high/medium → 'actionable' (badge),
    // low → 'fyi'. A label, not a second source — don't recompute it here.
    tier: AlertTier;
};

export type Alerts = {
    items: Alert[];          // active (not snoozed, not dismissed)
    snoozed: Alert[];        // snoozed by this user
    high_count: number;      // active severity counts
    medium_count: number;
    low_count: number;        // also the FYI tier (tier derives from severity)
    actionable_count: number; // active high+medium — the bell badge
    snoozed_count: number;
};

/** How long the bell's snooze hides an alert. The server's `SnoozeRequest`
 *  carries the same default for callers that omit `days`. */
export const DEFAULT_SNOOZE_DAYS = 7;

// Per-user, per-kind preference (C-9.2). Mirrors AlertPrefDto from
// dora_api/features/alerts/manage_alert_prefs.py.
export type AlertPref = {
    kind: AlertKind;
    enabled: boolean;
    // Read-only context for the manage panel: a kind's weight is fixed by the
    // server. Only `enabled` is user-settable (Step-0 Q2/Q3).
    severity: AlertSeverity;
    tier: AlertTier;
    /** False when this install can never raise the kind (server-derived). */
    available: boolean;
};

export type AlertPrefs = {
    prefs: AlertPref[];
};

export type UpdateAlertPrefCommand = {
    kind: AlertKind;
    enabled?: boolean;
};

// Upcoming "this fortnight" timeline (C-9.6) — mirrors UpcomingDto from
// dora_api/features/alerts/get_upcoming.py. A server-owned aggregation (R-003);
// the client only renders the grid + per-category dots.
export type UpcomingCategory = 'expiry' | 'shopping' | 'meal';

export type UpcomingExpiry = { stock_item_id: string; name: string };
export type UpcomingShopping = { list_id: string; name: string };
export type UpcomingMeal = { recipe_id: string; recipe_name: string; slot: string };

export type UpcomingDay = {
    date: string;                 // ISO date
    expiries: UpcomingExpiry[];
    shopping: UpcomingShopping[];
    meals: UpcomingMeal[];
};

export type Upcoming = {
    start: string;                // household-today (first grid cell)
    end: string;                  // last day (inclusive)
    days: number;                 // window length
    dates: UpcomingDay[];         // non-empty days only
};

export type AlertAction =
    | 'reset_expiry'
    | 'extend_expiry';

export type AlertActionOption = { action: AlertAction; label: string; icon: string };

/** A button on an alert's top row that navigates rather than writes. */
export type AlertNavOption = { label: string; icon: string; to: (alert: Alert) => string | null };

// The per-kind presentation contract. Every AlertKind has exactly one row —
// `Record<AlertKind, …>` makes TS reject a new kind that forgets one (FU-521:
// this is what was missing when `meal_reconcile_overdue` was added on the
// backend and five separate switch sites silently fell through). Add a kind =
// extend the union + add one row here; the accessors below need no edit.
//
// An alert card's buttons act on the thing the alert is about; the alert's
// own snooze / dismiss sit as icons down its right edge (owner 2026-10-17).
// The thing's buttons are built from `actions` (server writes), `nav` (a jump
// to where the thing is handled), `stockControls` (the level picker and the
// cart, for a shortage), `logWaste` and `productCart`.
export type AlertKindMeta = {
    icon: string;      // row avatar icon
    theme: string;     // plain-language label, e.g. "expiring soon"
    actions: AlertActionOption[];
    nav?: AlertNavOption;
    /** Offer the stock level picker + add-to-list on the row. */
    stockControls?: boolean;
    /** Offer "Log waste" (the stock row's reason picker) for the item. */
    logWaste?: boolean;
    /** Offer add-to-list for the product in `target_id` (via its linked
     *  stock item when the server sends one, as My products does). */
    productCart?: boolean;
    // Where tapping the row goes. Stock kinds omit it and fall back to the
    // item route in `linkFor`.
    link?: (alert: Alert) => string;
};

// Inline actions, shared by the kinds that offer the same set.
const EXPIRY_ACTIONS: AlertActionOption[] = [
    { action: 'extend_expiry', label: 'Push 7 days', icon: ICONS.event_repeat },
    { action: 'reset_expiry', label: 'Clear expiry', icon: ICONS.event_busy },
];
// Owner 2026-10-15: an expiring ingredient's useful question is "what can I
// cook with it?", so the row jumps to the cookbook filtered to it. Not for an
// expired one (owner 2026-10-17): that is past cooking, and its row offers
// "Log waste" in that slot instead.
const RECIPES_USING: AlertNavOption = {
    label: 'Recipes', icon: ICONS.menu_book,
    to: (a) => (a.stock_item_id ? `/cookbook?usesStockItem=${a.stock_item_id}` : null),
};
const listLink = (a: Alert) => (a.target_id ? `/shopping-lists/${a.target_id}` : '/shopping-lists');
const OPEN_LIST: AlertNavOption = { label: 'Open list', icon: ICONS.shopping_cart, to: listLink };
const priceLink = (a: Alert) => (a.target_id ? `/price-history?product_id=${a.target_id}` : '/price-history');

export const ALERT_KIND_META: Record<AlertKind, AlertKindMeta> = {
    expired:                { icon: ICONS.event_busy,         theme: 'expired',             actions: EXPIRY_ACTIONS, logWaste: true },
    expiring_soon:          { icon: ICONS.schedule,           theme: 'expiring soon',       actions: EXPIRY_ACTIONS, nav: RECIPES_USING },
    essential_low:          { icon: ICONS.priority_high,      theme: 'essential low',       actions: [], stockControls: true },
    no_planned_meals:       { icon: ICONS.restaurant,         theme: 'meals to plan',       actions: [], nav: { label: 'Plan meals', icon: ICONS.restaurant, to: () => '/meal-plans' }, link: () => '/meal-plans' },
    shopping_day:           { icon: ICONS.shopping_cart,      theme: 'shopping day',        actions: [], nav: OPEN_LIST, link: listLink },
    shopping_overdue:       { icon: ICONS.shopping_cart,      theme: 'forgotten shopping',  actions: [], nav: OPEN_LIST, link: listLink },
    meal_reconcile_overdue: { icon: ICONS.playlist_add_check, theme: 'meals to reconcile',  actions: [], nav: { label: 'Reconcile', icon: ICONS.playlist_add_check, to: () => '/meal-plans/reconcile' }, link: () => '/meal-plans/reconcile' },
    price_drop:             { icon: ICONS.trending_down,      theme: 'price drops',         actions: [], productCart: true, nav: { label: 'Price history', icon: ICONS.show_chart, to: priceLink }, link: priceLink },
};

// Icon per kind so the panel rows render consistently. The `?.` fallbacks in
// these accessors are load-bearing: the backend can ship a new AlertKind before
// the frontend knows it (that's the 2026-07-09 crash), so an unmapped kind must
// degrade to a blank/nav-only row, never throw (regression-pinned in
// test/unit/alertRow.spec.ts "unknown alert kind degrades safely").
export function iconFor(kind: AlertKind): string {
    // FU-531: an unmapped kind (backend shipped ahead of the client) falls back
    // to a generic bell rather than an empty circle — "degraded but safe" should
    // still look intentional.
    return ALERT_KIND_META[kind]?.icon ?? ICONS.notifications;
}

// Severity ladder — returned string is the class-suffix Quasar's `color` prop
// consumes (`bg-<name>` / `text-<name>`). Matching utility classes live in
// `web_app/src/css/colours.scss` and read from the tokens in tokens.scss.
// was Quasar numbered palette (red-6/orange-7/amber-7);
// now theme-aware via `light-dark()` tokens.
export function colorFor(severity: AlertSeverity): string {
    if (severity === 'high') return 'severity-critical';
    if (severity === 'medium') return 'severity-medium';
    return 'severity-low';
}

// Plain-language name for a kind, as the Settings toggles list it.
export function kindTheme(kind: AlertKind): string {
    return ALERT_KIND_META[kind]?.theme ?? kind;
}

// Server-side writes the user can take inline. Nav-only nudges return [].
export function actionsFor(kind: AlertKind): AlertActionOption[] {
    return ALERT_KIND_META[kind]?.actions ?? [];
}

// Where tapping an alert row navigates. The C-9.4
// nudges deep-link to their surface via the META `link`; stock kinds fall back
// to the item. Routing lives client-side (presentation); the server only
// supplies the ids.
export function linkFor(alert: Alert): string | null {
    const meta = ALERT_KIND_META[alert.kind];
    if (meta?.link) return meta.link(alert);
    return alert.stock_item_id ? `/stock/${alert.stock_item_id}` : null;
}
