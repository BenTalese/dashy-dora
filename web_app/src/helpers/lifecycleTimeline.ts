/**
 * The stock-item History tab's lifecycle timeline (C-1b.5 / INV-7 / L139).
 *
 * Merges the per-kind event lists on a `StockItemDetail` — level changes,
 * waste, list adds, purchases, cooks, expiry edits — plus the synthetic
 * Opened / Checked rows derived from current state into one date-sorted,
 * newest-first timeline. Each entry carries its own colour + icon so the user
 * can scan an item's purchase → use → waste → restock loop at a glance (P5).
 *
 * Pure: lifted out of `StockItemDetailPage.vue` when the page split into tabs
 * (FU-934 / finalisation 06-R32), so the merge and sort can be pinned by a
 * vitest. Truncation is server-owned (per-kind cap in
 * `get_stock_item_detail.py`, reported as `history_older_count`), so every
 * event the server sends is rendered.
 */
import { formatDate, formatDateTime as formatLocaleDateTime } from 'src/composables/useDateFormat';
import { formatMoney } from 'src/composables/useMoney';
import { LOW_STOCK_SEQUENCE } from 'src/helpers/stockStatus';
import { humaniseWasteReason } from 'src/helpers/wasteReasons';
import { isDateOnly, parseLocalIso } from 'src/helpers/weekDates';
import type { StockItemDetail } from 'src/models/stockItemDetail';
import { ICONS } from 'src/style/icons';

/** The History tab's filter buckets (DR-13). */
export type LifecycleKind = 'bought' | 'cooked' | 'level' | 'expiry' | 'listed' | 'waste';

export const LIFECYCLE_KIND_LABELS: Record<LifecycleKind, string> = {
    bought: 'Bought',
    cooked: 'Used',
    level: 'Levels',
    expiry: 'Expiry',
    listed: 'Lists',
    waste: 'Waste',
};

export type LifecycleEvent = {
    id: string;
    kind: LifecycleKind;
    /** Events with the same key next to each other collapse into one run. */
    runKey: string;
    /** The run's title, e.g. "Pushed expiry" for "Pushed expiry ×12". */
    runTitle: string;
    at: string;
    title: string;
    body?: string;
    icon: string;
    color: string;
};

/** Sort key for a timeline entry: date-only values sit at local midnight. */
export function eventTime(at: string): number {
    return (parseLocalIso(at) ?? new Date(at)).getTime();
}

/** Timeline subtitle: a calendar date renders as a date, an instant as
 *  date + time. */
export function formatEventAt(at: string): string {
    return isDateOnly(at) ? formatDate(at, { dateStyle: 'medium' }) : formatLocaleDateTime(at);
}

export function buildLifecycleTimeline(d: StockItemDetail): LifecycleEvent[] {
    const out: LifecycleEvent[] = [];

    // Level history — newest level at top of `level_history` already.
    // Walk *forwards in time* (older→newer) so we can infer "restocked"
    // vs "dropped to X" by comparing to the previous level's sequence.
    const levels = [...d.level_history].sort(
        (a, b) => new Date(a.changed_at).getTime() - new Date(b.changed_at).getTime(),
    );
    for (let i = 0; i < levels.length; i++) {
        const cur = levels[i]!;
        const prev = i > 0 ? levels[i - 1] : null;
        const name = cur.stock_level_name ?? 'Level changed';
        let title = `Level → ${name}`;
        if (prev && prev.stock_level_sequence != null && cur.stock_level_sequence != null) {
            // A move from low/out to stocked reads as "restocked"; the
            // opposite as "dropped to X". Otherwise just the destination.
            const wasShort = prev.stock_level_sequence >= LOW_STOCK_SEQUENCE;
            const nowShort = cur.stock_level_sequence >= LOW_STOCK_SEQUENCE;
            if (wasShort && !nowShort) title = `Restocked → ${name}`;
            else if (!wasShort && nowShort) title = `Dropped to ${name}`;
        }
        out.push({
            id: `level-${cur.changed_at}-${i}`,
            kind: 'level',
            runKey: 'level',
            runTitle: 'Level changes',
            at: cur.changed_at,
            title,
            icon: ICONS.refresh,
            color: 'primary',
        });
    }

    // Waste events. C-waste slim: reason-only — no quantity / value /
    // note. The timeline entry is a single line.
    for (const w of d.waste_events ?? []) {
        const reason = humaniseWasteReason(w.reason);
        out.push({
            id: `waste-${w.occurred_at}-${reason}`,
            kind: 'waste',
            runKey: 'waste',
            runTitle: 'Wasted',
            at: w.occurred_at,
            title: `Wasted: ${reason}`,
            icon: ICONS.delete_outline,
            color: 'negative',
        });
    }

    // Past list-adds — which list, and when.
    for (const a of d.recent_list_adds ?? []) {
        out.push({
            id: `add-${a.added_at}-${a.shopping_list_id}`,
            kind: 'listed',
            runKey: 'listed',
            runTitle: 'Added to lists',
            at: a.added_at,
            title: `Added to ${a.shopping_list_name}`,
            icon: ICONS.shopping_cart,
            color: 'accent',
        });
    }

    // Purchase events (2026-06-30) — every ticked line on a
    // finished shopping list. Answers "when did I last actually
    // buy this and for how much?" — a question the list-add
    // entries can't. Price + store are both optional; render
    // whichever the /finish flow captured.
    for (const p of d.purchase_events ?? []) {
        const bits: string[] = [];
        if (p.quantity && p.quantity !== 1) bits.push(`${p.quantity}×`);
        if (p.actual_unit_price != null) {
            bits.push(`${formatMoney(p.actual_unit_price)}${p.quantity > 1 ? '/ea' : ''}`);
        }
        if (p.store_name) bits.push(`at ${p.store_name}`);
        const entry: LifecycleEvent = {
            id: `bought-${p.occurred_at}-${p.shopping_list_id}`,
            kind: 'bought',
            runKey: 'bought',
            runTitle: 'Bought',
            at: p.occurred_at,
            title: `Bought · ${p.shopping_list_name}`,
            icon: ICONS.shopping_bag,
            // was 'teal-8'; now theme-aware via --lifecycle-bought.
            color: 'lifecycle-bought',
        };
        if (bits.length > 0) entry.body = bits.join(' · ');
        out.push(entry);
    }

    // Cook events (2026-06-30) — every recipe you cooked that
    // uses this ingredient. `meals_cooked > 1` badges the entry
    // as a batch cook. Recipe id may be null (SET NULL on delete);
    // denormalised name still renders.
    for (const c of d.cook_events ?? []) {
        const badge = c.meals_cooked > 1 ? ` · ${c.meals_cooked} meals` : '';
        out.push({
            id: `cook-${c.occurred_at}-${c.recipe_id ?? 'unknown'}`,
            kind: 'cooked',
            runKey: `cooked-${c.recipe_name}`,
            runTitle: `Used in ${c.recipe_name}`,
            at: c.occurred_at,
            title: `Used in ${c.recipe_name}${badge}`,
            icon: ICONS.local_fire_department,
            // was 'deep-orange-6'; reuses the severity-high
            // token (same visual weight as the essential-low alert kind).
            color: 'severity-high',
        });
    }

    // Expiry events (2026-06-30) — set / pushed / cleared trail.
    // Repeat pushes tell the user "this is stale in your fridge".
    for (const e of d.expiry_events ?? []) {
        let title: string;
        let runTitle: string;
        let body: string | null = null;
        let color: string;
        // D-006 — install-locale dates, not raw ISO (finalisation 06-R2).
        const fmt = (iso: string | null) => (iso ? formatDate(iso) : '–');
        if (e.kind === 'cleared') {
            title = 'Cleared expiry';
            runTitle = title;
            body = e.previous_expiry_date
                ? `Was ${fmt(e.previous_expiry_date)}`
                : null;
            // was 'grey-7'; theme-aware --lifecycle-cleared
            // (a muted neutral, distinct from severity-*). Cleared
            // is a "wound-down" state, not part of the severity ladder.
            color = 'lifecycle-cleared';
        } else if (e.kind === 'pushed') {
            const delta = e.delta_days ?? 0;
            title = delta >= 0 ? `Pushed expiry +${delta} day${delta === 1 ? '' : 's'}`
                               : `Expiry moved ${delta} day${delta === -1 ? '' : 's'}`;
            runTitle = 'Moved expiry';
            body = `${fmt(e.previous_expiry_date)} → ${fmt(e.new_expiry_date)}`;
            // was 'orange-8'; theme-aware --lifecycle-expiry-changed.
            color = 'lifecycle-expiry-changed';
        } else {
            title = 'Set expiry';
            runTitle = title;
            body = fmt(e.new_expiry_date);
            color = 'lifecycle-expiry-changed';
        }
        const entry: LifecycleEvent = {
            id: `expiry-${e.occurred_at}-${e.kind}`,
            kind: 'expiry',
            runKey: `expiry-${e.kind}`,
            runTitle,
            at: e.occurred_at,
            title,
            icon: ICONS.event,
            color,
        };
        if (body) entry.body = body;
        out.push(entry);
    }

    // Synthetic "Opened" — single entry derived from current state.
    // opened_on is a calendar date: kept date-only (never widened to a
    // naive `T00:00:00` instant, which would render in the household zone
    // and shift a day when the device zone differs). `formatEventAt`
    // renders it as a date; `eventTime` orders it at local start-of-day.
    if (d.is_open && d.opened_on) {
        out.push({
            id: `opened-${d.opened_on}`,
            kind: 'expiry',
            runKey: 'opened',
            runTitle: 'Opened',
            at: d.opened_on,
            title: 'Opened',
            icon: ICONS.lock_open,
            // was 'amber-9'; reuses the --severity-attention
            // token (same visual weight as the AddToList "on multiple
            // lists" hint — both grabby-but-not-urgent).
            color: 'severity-attention',
        });
    }

    // Synthetic "Checked" — only if last_checked_at differs from the
    // most recent level change (otherwise it's the same event).
    const lastLevelAt = levels.length > 0
        ? levels[levels.length - 1]!.changed_at
        : null;
    if (d.last_checked_at && d.last_checked_at !== lastLevelAt) {
        out.push({
            id: `checked-${d.last_checked_at}`,
            kind: 'level',
            runKey: 'checked',
            runTitle: 'Checked',
            at: d.last_checked_at,
            title: 'Checked (still correct)',
            icon: ICONS.event,
            color: 'positive',
        });
    }

    // Sort newest first. Truncation is server-owned now (per-kind
    // cap in get_stock_item_detail.py, reported via
    // `history_older_count`); we render everything the server
    // sends and surface the drop count in the timeline footer.
    out.sort((a, b) => eventTime(b.at) - eventTime(a.at));
    return out;
}

/** Fewest same-key neighbours that collapse into one row. */
export const LIFECYCLE_RUN_MIN = 3;

export type LifecycleRow =
    | { type: 'event'; event: LifecycleEvent }
    | { type: 'run'; id: string; title: string; events: LifecycleEvent[] };

/**
 * Collapse runs of the same thing (DR-13): fifty expiry pushes in a row read
 * as one "Moved expiry ×50" row the user can open, not fifty rows. Input is
 * the newest-first timeline; a run keeps that order.
 */
export function groupLifecycleEvents(events: LifecycleEvent[]): LifecycleRow[] {
    const rows: LifecycleRow[] = [];
    let i = 0;
    while (i < events.length) {
        let j = i + 1;
        while (j < events.length && events[j]!.runKey === events[i]!.runKey) j++;
        const run = events.slice(i, j);
        if (run.length >= LIFECYCLE_RUN_MIN) {
            rows.push({ type: 'run', id: `run-${run[0]!.id}`, title: run[0]!.runTitle, events: run });
        } else {
            for (const event of run) rows.push({ type: 'event', event });
        }
        i = j;
    }
    return rows;
}

/** A run's subtitle: oldest to newest, one date each end. */
export function formatRunSpan(events: LifecycleEvent[]): string {
    const newest = formatDate(events[0]!.at, { dateStyle: 'medium' });
    const oldest = formatDate(events[events.length - 1]!.at, { dateStyle: 'medium' });
    return newest === oldest ? newest : `${oldest} – ${newest}`;
}
