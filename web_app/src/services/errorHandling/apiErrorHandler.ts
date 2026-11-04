import { NormalisedApiError } from 'src/services/api/axiosHttpClient';

/**
 * FU-099 wire shape — every entry in `errors[field]` is
 * `{ msg, code, raw }`: friendly copy for the user, structured Pydantic
 * code (or "domain" for our own errors) for grouping / dev grep, and
 * the raw Pydantic message preserved for debug. The client ONLY shows
 * `msg`; `code` + `raw` live in console.warn / DevTools.
 */
export interface ApiErrorEntry {
    msg: string;
    code: string;
    raw: string | null;
}

export type ApiErrorsMap = Record<string, ApiErrorEntry[]>;

export type ExtractedErrors = {
    fieldErrors: Record<string, string>;
    generalError: string | null;
};

const EMPTY: ExtractedErrors = { fieldErrors: {}, generalError: null };

// Backend RFC7807-ish payloads carry `{ errors: { fieldName: [entry, ...] } }`.
// Anything with an empty/sentinel key is treated as a form-level message.
const GENERAL_KEYS = new Set(['', '_', 'noKey', 'general']);

// Old wire shape (string per entry) still flows through for any endpoint
// that hasn't been migrated yet — extractEntryMsg accepts either shape so
// the transition is incremental.
function extractEntryMsg(entry: ApiErrorEntry | string): string {
    if (typeof entry === 'string') return entry;
    return entry?.msg ?? '';
}

/**
 * True when the http client has already put up its global "Something on the
 * server tripped" toast for this error (every 5xx outside `/auth/me`), so a
 * caller's own failure toast would be the second one for the same click
 * (FU-976: two error toasts for one price-save failure). A catch block that
 * toasts should skip its own toast when this is true.
 */
export function isAlreadyNotified(err: unknown): boolean {
    return err instanceof NormalisedApiError && err.status >= 500;
}

export function extractFieldErrors(err: unknown): ExtractedErrors {
    if (!(err instanceof NormalisedApiError)) {
        return {
            fieldErrors: {},
            generalError: 'Something went wrong. Please try again.',
        };
    }

    // 5xx already triggers a global Notify in the http client — leave the
    // form's general slot blank so users aren't told twice.
    if (isAlreadyNotified(err)) return EMPTY;

    if (err.isNetworkError) {
        return {
            fieldErrors: {},
            generalError: "Can't reach the server. Check your connection and try again.",
        };
    }

    const serverErrors = (err.details?.errors ?? {}) as Record<
        string,
        Array<ApiErrorEntry | string> | ApiErrorEntry | string
    >;
    const fieldErrors: Record<string, string> = {};
    const generalParts: string[] = [];

    for (const [key, value] of Object.entries(serverErrors)) {
        const entries = Array.isArray(value) ? value : [value];
        const text = entries.map(extractEntryMsg).filter(Boolean).join(' ');
        if (!text) continue;
        if (GENERAL_KEYS.has(key)) {
            generalParts.push(text);
        } else {
            fieldErrors[key] = text;
        }
    }

    let generalError: string | null = generalParts.join(' ') || null;
    // 4xx with no errors map at all → fall back to the http-level message so
    // the user gets *something* rather than silent failure.
    if (!generalError && Object.keys(fieldErrors).length === 0) {
        generalError = err.message || 'Request failed.';
    }

    return { fieldErrors, generalError };
}

/**
 * FU-099 — toast caption for a save failure. When the response carries
 * field-keyed errors, we *don't* paste them into the caption (those
 * belong inline next to the offending input); we return the standard
 * "check the highlighted fields" prompt and let `useFormErrors` /
 * `extractFieldErrors` route the per-field copy to the form. Non-field
 * errors (network, general, unknown) still come through as a one-liner.
 *
 * Returns empty string if nothing useful is available so callers can
 * fall back to their own copy.
 */
export function describeApiError(err: unknown): string {
    const extracted = extractFieldErrors(err);
    if (Object.keys(extracted.fieldErrors).length > 0) {
        return "Couldn't save. Check the highlighted fields.";
    }
    return extracted.generalError || '';
}

/**
 * FU-099 — a small "ref:" tag appended to negative-toast captions so
 * any bug report / screenshot carries the X-Request-Id of the failing
 * call. Pairs with the server-side request-id logging
 * (`dora_api/infrastructure/log_context.py`) so support can grep the
 * exact request line.
 *
 * Returns `""` when no correlation id is available (e.g. errors that
 * never reached the network, or non-NormalisedApiError shapes).
 */
export function correlationSuffix(err: unknown): string {
    if (!(err instanceof NormalisedApiError)) return '';
    if (!err.correlationId) return '';
    return ` · ref: ${err.correlationId.slice(0, 8)}`;
}

/**
 * FU-099 — the standard caption for a negative toast on an API failure.
 *
 * Combines the friendly message from `describeApiError` with the
 * `ref: <id>` correlation suffix so every error toast in the app
 * carries the request-id any bug report needs. Returns `''` only when
 * we have nothing useful to say at all (caller decides whether to omit
 * the caption or fall back to its own copy).
 *
 * Replaces the old `describeApiError(err) || ''` idiom across catch
 * blocks — one helper per site, one place to evolve the format.
 */
export function toastCaption(err: unknown): string {
    const main = describeApiError(err);
    const ref = correlationSuffix(err);
    if (!main && !ref) return '';
    if (!main) return ref.replace(/^\s·\s/, '');
    return main + ref;
}
