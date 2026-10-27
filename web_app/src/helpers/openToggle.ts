/**
 * DR-5 (D-008) — the stock-item "open / in-use" toggle.
 *
 * Marking an item *open* opens an expiry-prompt dialog (opened milk goes off
 * fast, opened jam barely moves — a universal rule is wrong per-item, so we
 * ask). The old flow PATCHed `is_open=true` *first* and let the dialog govern
 * only the expiry, so backdrop/Escape/Skip all left the item open with no way
 * to abort (FU-578 #2). This module makes the mutation a *product* of the
 * dialog's outcome: nothing is written until the user confirms.
 *
 * `buildOpenTogglePatch` is the pure decision → patch mapping, kept free of
 * Quasar/store imports so the "dismiss ⇒ no mutation" contract can be unit-
 * pinned cheaply. The dialog + orchestration live in `useStockItemActions`.
 */

/** The minimal shape of the stock item the toggle acts on. */
export interface OpenToggleTarget {
    stock_item_id: string;
    name: string;
    is_open?: boolean;
    expiry_date?: string | null;
}

/**
 * The user's answer to the mark-open dialog.
 *   • `open:false`            → dismissed/cancelled: do not open the item.
 *   • `open:true, expiry:undefined` → Skip: open, leave expiry unchanged.
 *   • `open:true, expiry:<val|null>` → Update: open and set this expiry.
 */
export interface OpenExpiryDecision {
    open: boolean;
    expiry?: string | null | undefined;
}

/** A ready-to-send subset of `UpdateStockItemCommand` (or `null` = no-op). */
export interface OpenTogglePatch {
    stock_item_id: string;
    is_open: boolean;
    expiry_date?: string | null;
}

/**
 * Resolve the toggle into a PATCH body, or `null` when nothing should be
 * written.
 *
 *   • Sealing (item currently open) never prompts — pass `decision = null`.
 *   • Opening requires a confirming `decision`; a missing or `open:false`
 *     decision (backdrop / Escape / Cancel) returns `null` so the caller
 *     performs no mutation — the DR-5 guarantee.
 *   • An expiry is only included when the user picked one that differs from
 *     the item's current value (preserves the pre-DR-5 "unchanged ⇒ omit"
 *     behaviour, where a bare current expiry is treated as the empty string).
 */
export function buildOpenTogglePatch(
    target: OpenToggleTarget,
    decision: OpenExpiryDecision | null,
): OpenTogglePatch | null {
    const next = !target.is_open;
    if (!next) {
        // Sealing: a single unconditional write, no dialog involved.
        return { stock_item_id: target.stock_item_id, is_open: false };
    }
    // Opening: only proceed on an explicit confirmation.
    if (!decision || !decision.open) return null;
    const patch: OpenTogglePatch = { stock_item_id: target.stock_item_id, is_open: true };
    const currentExpiry = target.expiry_date ?? '';
    if (decision.expiry !== undefined && decision.expiry !== currentExpiry) {
        patch.expiry_date = decision.expiry;
    }
    return patch;
}
