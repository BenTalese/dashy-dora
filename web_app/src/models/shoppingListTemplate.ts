// Mirrors DTOs in dora_api/features/shopping_list_templates/manage_templates.py.

import type { LinePreferredBuy, LineProductOffer } from 'src/models/shoppingList';

export type TemplateSummary = {
    template_id: string;
    name: string;
    created_at: string;
    updated_at: string;
    line_count: number;
};

export type TemplateLine = {
    line_id: string;
    /** Null on a product-only line, which `product_id` anchors instead. */
    stock_item_id: string | null;
    product_id: string | null;
    /** The stock item's name, or the product's on a product-only line. */
    stock_item_name: string;
    quantity: number | null;
    sequence: number;
    /** The same "which one" choice a list line carries; copied onto the new
     *  list when the template is used. */
    selected_product_id: string | null;
    preferred_buy_id: string | null;
    offers: LineProductOffer[];
    preferred_buys: LinePreferredBuy[];
};

/** Omitted fields are left alone; `null` clears. */
export type UpdateTemplateLineCommand = {
    quantity?: number | null;
    selected_product_id?: string | null;
    preferred_buy_id?: string | null;
};

export type TemplateDetail = {
    template_id: string;
    name: string;
    created_at: string;
    updated_at: string;
    lines: TemplateLine[];
};
