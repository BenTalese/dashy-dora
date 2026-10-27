export type StockItem = {
    name: string;
    stock_group_id: string | null;
    stock_item_id: string;
    stock_level_id: string;
    stock_location_id: string | null;
    expiry_date?: string | null;
    is_essential?: boolean;
    is_open?: boolean;
    opened_on?: string | null;
    stock_level_last_updated?: string | null;
    // Server-derived stock status (§3.1 contract). The client reads these
    // instead of matching a level name against "Out of Stock" / "Low Stock";
    // the name itself comes from `stockLevelStore.levelById`.
    stock_level_sequence?: number | null;
    is_out_of_stock?: boolean;
    is_low_stock?: boolean;
    needs_restock?: boolean;
    /** Server-owned attention (Chunk 3b, `stock_attention.py`). The single
     *  rule behind the row outline, the "Needs attention" chip + count, and
     *  the bell's per-item kinds. **Do not re-derive any of this client-side**
     *  — the copy that used to live in `useStockFilters.hasAlert` disagreed
     *  with the server in four separate ways (B1–B4 in the impl plan).
     *  `attention_rank` orders the outlined band; `attention_kinds` says
     *  which conditions fired, for chips that narrow to one of them. */
    needs_attention?: boolean;
    attention_severity?: 'high' | 'medium' | 'low' | null;
    attention_kinds?: readonly string[];
    /** Urgency ORDER inside the outlined band, most urgent first:
     *  0 expired · 1 essential-out · 2 expiring-soon · 3 essential-low ·
     *  9 nothing fired. Severity can't order these — expired and
     *  essential_low are both `high` — so this is what the "Needs attention"
     *  sort reads. The meaning lives in `stock_attention.py`; the client only
     *  compares the number. */
    attention_rank?: number;
    /** C-7 Chunk 2 — count of linked products. Drives the combined
     *  modal decision in `AddToListButton`: 2+ → open QuickAddSheet
     *  (one combined surface) instead of stacking two prompts. */
    linked_product_count?: number;
};
