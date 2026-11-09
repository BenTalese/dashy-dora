/**
 * Stock-overview row geometry — the single source for "how tall is a row".
 *
 * The overview's windowed branch (`useFixedRowWindow`) places rows by
 * arithmetic, so every row must render at exactly this height: a *fixed*
 * height, not a min-height, with the number in exactly one place, here. The
 * page binds it to the list as a CSS custom property (`--stock-row-height`)
 * and hands the same value to the window, so the two can never drift.
 *
 * Two values because phones let the item name wrap to two lines (DR-9), which
 * genuinely needs the extra room; every row within a breakpoint is uniform.
 * Both include the row's 8px bottom gap.
 */
export const STOCK_ROW_HEIGHT_DESKTOP = 64;
export const STOCK_ROW_HEIGHT_MOBILE = 76;
