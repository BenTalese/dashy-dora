/**
 * The number an author typed at the start of a free-text step — "1. ",
 * "2) ", "3: ", "Step 4 — ", "(5) ". Both faces that draw their own numerals
 * (the recipe page's method and cook mode) drop it for display, so a step
 * doesn't read "(1) 1. Render the pancetta" (FU-857). The stored text is the
 * author's and is left alone.
 *
 * Deliberately narrow: bare digits must be followed by punctuation and a space,
 * so "2 eggs, beaten" keeps its 2 and "1.5 cups of stock" its 1.5.
 */
const LEADING_ORDINAL = /^(?:step\s*\d{1,3}\s*[.):\-–—]?\s+|\(\s*\d{1,3}\s*\)\s+|\d{1,3}\s*[.):\-–—]\s+)/i;

export function stripLeadingOrdinal(line: string): string {
    const stripped = line.replace(LEADING_ORDINAL, '');
    // Never strip a line down to nothing: a lone "1." is all that line has.
    return stripped.length > 0 ? stripped : line;
}
