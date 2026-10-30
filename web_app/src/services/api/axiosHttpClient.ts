import type { Axios, AxiosError, InternalAxiosRequestConfig } from 'axios';
import axios from 'axios';
import { Notify } from 'quasar';
import { getBackendBaseUrl } from 'src/services/api/backendUrl';
import { parseFilename } from 'src/services/files/downloadHelpers';

class ApiErrorResponse extends Error {
    detail!: string;
    status!: number;
    errors!: Map<string, string>;
    title!: string;
    type!: string;
}

// Normalised error shape every caller sees, regardless of backend response
// shape. Carriers a correlationId so logs/bug-reports can be matched back to
// the request line on the server side.
export class NormalisedApiError extends Error {
    status: number;
    code: string;
    details: Record<string, unknown> | null;
    correlationId: string;
    isNetworkError: boolean;
    method: string;
    url: string;

    constructor(args: {
        status: number;
        code: string;
        message: string;
        details: Record<string, unknown> | null;
        correlationId: string;
        isNetworkError: boolean;
        method: string;
        url: string;
    }) {
        super(args.message);
        this.name = 'NormalisedApiError';
        this.status = args.status;
        this.code = args.code;
        this.details = args.details;
        this.correlationId = args.correlationId;
        this.isNetworkError = args.isNetworkError;
        this.method = args.method;
        this.url = args.url;
    }
}

// Optional callback the auth store registers to react to expired sessions
// (clear user state, redirect to /login). The setter avoids a Pinia circular
// import that would happen if this module imported the store directly.
type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
    unauthorizedHandler = handler;
}

// Endpoints where a 401 is an expected outcome (anonymous boot probe / explicit
// login attempt), so we must NOT trigger the global session-expired handler.
const SUPPRESS_401_PATHS = ['/auth/me', '/auth/login', '/auth/register'];

// Endpoints whose failures are surfaced in-page rather than via toast — the
// boot probe is owned by SplashScreen, so a noisy "server tripped" notify on
// cold-load would race with the splash and look broken.
const SUPPRESS_NOTIFY_PATHS = ['/auth/me'];

// ─── Timeouts ────────────────────────────────────────────────────────
// axios defaults to NO timeout, which is fine on a desktop and wrong on a
// phone: when the OS suspends the app the TCP connection is often already
// dead by the time it resumes, so the request neither succeeds nor errors —
// it hangs forever. Nothing rejects, so no retry fires, no error state is
// set, and the user sits on a pulsing splash (boot probe) or a page that
// never reconnects. Every request now has a ceiling.
//
// The boot probes get a much shorter one. They gate the splash, and the
// splash already owns the recovery affordance (a Retry button) — so failing
// fast and handing the user that button beats a long silent wait. Everything
// else keeps the generous ceiling; some admin calls (dataset import kick-off,
// backup/restore) are legitimately slow and must not be cut off.
const DEFAULT_TIMEOUT_MS = 30_000;
const BOOT_PROBE_TIMEOUT_MS = 8_000;
const BOOT_PROBE_PATHS = ['/auth/me', '/auth/bootstrap-required'];

function isBootProbe(url: string | undefined): boolean {
    if (!url) return false;
    return BOOT_PROBE_PATHS.some((p) => url.endsWith(p));
}

function shouldSuppress401(url: string | undefined): boolean {
    if (!url) return false;
    return SUPPRESS_401_PATHS.some((p) => url.endsWith(p));
}

function shouldSuppressNotify(url: string | undefined): boolean {
    if (!url) return false;
    return SUPPRESS_NOTIFY_PATHS.some((p) => url.endsWith(p));
}

// The API may return either a bare { id } envelope or the full created
// resource as the body. Callers can narrow on entity-specific id fields.
export type CreatedResponse = { id?: string } & Record<string, unknown>;

export type HttpClientResponse<TResponse> = TResponse;

export interface RequestOptions {
    /** Overrides the default ceiling for one call that is legitimately slow
     *  (an 8 MB upload chunk on a slow uplink). */
    timeoutMs?: number;
    /** Opt a POST that is really a read (a download or print view whose
     *  parameters only travel in the body because they'd overflow the
     *  request line) into the GET retry policy. Only for idempotent calls
     *  that change nothing server-side — an ordinary write is never retried. */
    retryAsRead?: true;
}

export interface HttpClient {
    get<TResponse = unknown>(path: string): Promise<HttpClientResponse<TResponse>>;
    /** Binary GET (QR PNGs, future exports). Same interceptors — and so the
     *  same session cookie, CSRF seeding and 401 routing — as every other
     *  call, which a bare <img src> or window.open() does NOT get. */
    getBlob(path: string): Promise<Blob>;
    /** A download: the bytes plus the server's `Content-Disposition` filename. */
    getFile(path: string): Promise<{ blob: Blob; filename: string | null }>;
    /** `getFile` with a JSON body — for a download whose parameters (a large
     *  id selection) would overflow the request line as a query string. */
    postFile<TBody = unknown>(path: string, body: TBody, options?: RequestOptions): Promise<{ blob: Blob; filename: string | null }>;
    post<TResponse = unknown, TBody = unknown>(path: string, body: TBody, options?: RequestOptions): Promise<HttpClientResponse<TResponse>>;
    put<TResponse = unknown, TBody = unknown>(path: string, body: TBody): Promise<HttpClientResponse<TResponse>>;
    patch<TResponse = unknown, TBody = unknown>(path: string, body: TBody): Promise<HttpClientResponse<TResponse>>;
    delete<TResponse = unknown>(path: string): Promise<HttpClientResponse<TResponse>>;
}

// thin adapter kept for the handful of callers that still read the
// base URL synchronously (network-status ping, About settings). New code
// should import `getBackendBaseUrl` from `services/api/backendUrl` directly.
export function resolveBaseURL(): string {
    return getBackendBaseUrl();
}

// ─── Correlation id ──────────────────────────────────────────────────
// Lightweight UUIDv4 generator. We can't rely on `crypto.randomUUID` in
// every target browser (Chrome ≥92, but still); fall back if missing.
function newCorrelationId(): string {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
        return (crypto as Crypto & { randomUUID: () => string }).randomUUID();
    }
    // RFC4122 v4 fallback. Not cryptographically strong, but fine for an
    // id whose only job is to match log lines.
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === 'x' ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
}

// ─── Retry policy ────────────────────────────────────────────────────
// Spec: GET only, max 3 attempts, exponential backoff on network errors
// and 502/503/504. Never retry POST/PUT/PATCH/DELETE — a write that may
// already have landed must not be replayed blind. Offline is read-only
// (2026-08-23), so a failed write is reported to the user, never retried
// behind their back. The one exception is a POST the caller marks
// `retryAsRead` — a read whose parameters ride in the body — which changes
// nothing and so is as safe to replay as a GET.
const RETRYABLE_STATUSES = new Set([502, 503, 504]);
const MAX_RETRIES = 3;
// The boot probes retry once, not three times. Three attempts at the full
// timeout is ~25s of pulsing splash before the user is offered anything to
// press; the splash's Retry button is a better answer than a longer wait,
// and it re-enters the same loop.
const MAX_BOOT_PROBE_RETRIES = 1;

function isRetryable(method: string | undefined, error: AxiosError, retryAsRead = false): boolean {
    const m = (method ?? 'get').toLowerCase();
    if (m !== 'get' && !(retryAsRead && m === 'post')) return false;
    if (!error.response) return true; // network error / no response
    return RETRYABLE_STATUSES.has(error.response.status);
}

function retryCeilingFor(url: string | undefined): number {
    return isBootProbe(url) ? MAX_BOOT_PROBE_RETRIES : MAX_RETRIES;
}

function backoffDelay(attempt: number): number {
    // 1: 200ms, 2: 400ms, 3: 800ms + small jitter
    const base = 200 * 2 ** (attempt - 1);
    const jitter = Math.random() * 100;
    return base + jitter;
}

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

// double-submit CSRF cookie reader. The backend mints
// `dora_csrf` (non-HttpOnly) on the first response that doesn't carry
// it, so this returns null until the SPA has made at least one request
// (the cold-load `getMe` GET happens before any mutating call).
export function readCsrfCookie(): string | null {
    if (typeof document === 'undefined' || !document.cookie) return null;
    for (const part of document.cookie.split(';')) {
        const [name, ...rest] = part.trim().split('=');
        if (name === 'dora_csrf') return rest.join('=') || null;
    }
    return null;
}

// FU-571 — spreadable CSRF header for the handful of callers that bypass
// this client (chunked uploads, import/backup inspect+commit, client logs,
// TTS streaming — all raw `fetch`). The
// interceptor below attaches this automatically; anything not going through
// an AxiosHttpClient instance MUST spread it in or the FU-197 double-submit
// defence 403s every mutating call. See R-047 — keep this list current, and
// pin each bypassing caller with a test (a mocked transport never enforces
// CSRF, so a missing header is invisible otherwise).
export function csrfHeader(): Record<string, string> {
    const token = readCsrfCookie();
    return token ? { 'X-CSRF-Token': token } : {};
}

// Translate the per-call options into axios config. `__retryAsRead` rides on
// the config so the response interceptor sees it on every attempt.
function requestOptionsConfig(options?: RequestOptions): { timeout?: number; __retryAsRead?: boolean } {
    return {
        ...(options?.timeoutMs !== undefined ? { timeout: options.timeoutMs } : {}),
        ...(options?.retryAsRead ? { __retryAsRead: true } : {}),
    };
}

// Augment axios's request config with our retry / correlation-id state
// so the interceptors can pass it across attempts.
type DoraRequestConfig = InternalAxiosRequestConfig & {
    __retryCount?: number;
    __correlationId?: string;
    __retryAsRead?: boolean;
};

export default class AxiosHttpClient implements HttpClient {
    private axios: Axios;

    constructor() {
        this.axios = axios.create({
            headers: { 'Content-Type': 'application/json' },
            // See the timeout block above — without this a request can hang
            // forever after a mobile suspend/resume.
            timeout: DEFAULT_TIMEOUT_MS,
            // withCredentials lets the browser send/receive the dora_session
            // cookie on cross-origin requests (dev: 5174 → 5170).
            withCredentials: true
        });

        // ── Request interceptor: correlation id + CSRF token ───────
        this.axios.interceptors.request.use((config) => {
            const cfg = config as DoraRequestConfig;
            // resolve baseURL per-request so a runtime change
            // (Settings → save new instance URL) takes effect immediately
            // without rebuilding the axios instance. Empty string is a
            // valid answer on native before the setup gate completes; the
            // router prevents API calls in that window.
            cfg.baseURL = getBackendBaseUrl();
            if (isBootProbe(cfg.url)) cfg.timeout = BOOT_PROBE_TIMEOUT_MS;
            if (!cfg.__correlationId) cfg.__correlationId = newCorrelationId();
            cfg.headers.set?.('X-Request-Id', cfg.__correlationId);

            // double-submit CSRF. The backend mints the
            // `dora_csrf` cookie on the first response that doesn't
            // carry one (cold-load GETs seed it), and rejects any
            // mutating request whose `X-CSRF-Token` header doesn't
            // match the cookie. The cookie is non-HttpOnly by design
            // so we can read it here.
            const method = (cfg.method ?? 'get').toLowerCase();
            if (['post', 'put', 'patch', 'delete'].includes(method)) {
                const token = readCsrfCookie();
                if (token) cfg.headers.set?.('X-CSRF-Token', token);
            }
            return cfg;
        });

        // ── Response interceptor: 401 + retry + normalisation ──────
        this.axios.interceptors.response.use(
            (response) => response,
            async (error: AxiosError) => {
                const cfg = (error.config ?? {}) as DoraRequestConfig;

                // 401 — session expired (or never authed). Route to login.
                if (error.response?.status === 401 && !shouldSuppress401(cfg.url)) {
                    unauthorizedHandler?.();
                    return Promise.reject(error);
                }

                // Retry GETs on network errors and 5xx-class transient codes.
                if (isRetryable(cfg.method, error, cfg.__retryAsRead === true)) {
                    const attempt = (cfg.__retryCount ?? 0) + 1;
                    if (attempt <= retryCeilingFor(cfg.url)) {
                        cfg.__retryCount = attempt;
                        await sleep(backoffDelay(attempt));
                        return this.axios.request(cfg);
                    }
                }

                return Promise.reject(error);
            }
        );
    }

    async delete<TResponse = unknown>(path: string): Promise<HttpClientResponse<TResponse>> {
        try {
            return (await this.axios.delete<TResponse>(path)).data;
        } catch (error) {
            return this.handleError(error as AxiosError, 'DELETE', path);
        }
    }

    async get<TResponse = unknown>(path: string): Promise<HttpClientResponse<TResponse>> {
        try {
            return (await this.axios.get<TResponse>(path)).data;
        } catch (error) {
            return this.handleError(error as AxiosError, 'GET', path);
        }
    }

    async getBlob(path: string): Promise<Blob> {
        try {
            return (await this.axios.get<Blob>(path, { responseType: 'blob' })).data;
        } catch (error) {
            // `responseType: 'blob'` applies to the ERROR body too, so a
            // problem-detail JSON arrives here as a Blob and every downstream
            // reader (`details.title`, the notify caption) saw nothing. Read it
            // back into JSON before normalising — this is why a failed QR fetch
            // could only ever report its status (FU-648).
            await this.parseBlobErrorBody(error as AxiosError);
            return this.handleError(error as AxiosError, 'GET', path);
        }
    }

    async getFile(path: string): Promise<{ blob: Blob; filename: string | null }> {
        try {
            const response = await this.axios.get<Blob>(path, { responseType: 'blob' });
            const disposition = response.headers['content-disposition'];
            return {
                blob: response.data,
                filename: parseFilename(typeof disposition === 'string' ? disposition : null),
            };
        } catch (error) {
            await this.parseBlobErrorBody(error as AxiosError);
            return this.handleError(error as AxiosError, 'GET', path);
        }
    }

    async postFile<TBody = unknown>(
        path: string,
        body: TBody,
        options?: RequestOptions,
    ): Promise<{ blob: Blob; filename: string | null }> {
        try {
            const response = await this.axios.post<Blob>(path, body, {
                responseType: 'blob',
                ...requestOptionsConfig(options),
            });
            const disposition = response.headers['content-disposition'];
            return {
                blob: response.data,
                filename: parseFilename(typeof disposition === 'string' ? disposition : null),
            };
        } catch (error) {
            await this.parseBlobErrorBody(error as AxiosError);
            return this.handleError(error as AxiosError, 'POST', path);
        }
    }

    /** Best-effort: swap a JSON error body delivered as a Blob for the parsed
     *  object, in place. Silent on anything that isn't JSON — a binary endpoint
     *  is entitled to fail with a non-JSON body. */
    private async parseBlobErrorBody(error: AxiosError): Promise<void> {
        const response = error.response;
        if (!response || !(response.data instanceof Blob)) return;
        try {
            const text = await response.data.text();
            response.data = JSON.parse(text) as unknown;
        } catch {
            // Leave the Blob in place; handleError falls back to the status.
        }
    }

    /** Map any axios error into a NormalisedApiError, surface 5xx via notify. */
    private handleError(error: AxiosError, method: string, path: string): Promise<never> {
        const cfg = (error.config ?? {}) as DoraRequestConfig;
        const correlationId = cfg.__correlationId ?? '';
        const status = error.response?.status ?? 0;
        const isNetworkError = !error.response;
        const errorData = error.response?.data;

        let code = 'unknown_error';
        let message = error.message || 'Request failed';
        let details: Record<string, unknown> | null = null;

        if (this.isCustomApiErrorResponse(errorData)) {
            const apiError = errorData;
            code = apiError.type || `http_${status}`;
            message =
                apiError.detail ||
                apiError.title ||
                Object.values(apiError.errors ?? {}).join(', ') ||
                message;
            details = {
                title: apiError.title,
                errors: apiError.errors,
                type: apiError.type,
            };
        } else if (isNetworkError) {
            code = 'network_error';
            message = 'Network request failed';
        } else {
            code = `http_${status}`;
        }

        // 5xx → noisy toast so the user knows the server tripped.
        // 4xx is the caller's responsibility to phrase — it might be a
        // benign 404 from a search, etc.
        if (status >= 500 && !shouldSuppressNotify(path)) {
            try {
                Notify.create({
                    type: 'negative',
                    position: 'top',
                    message: 'Something on the server tripped. We logged the error.',
                    ...(correlationId
                        ? { caption: `Ref: ${correlationId.slice(0, 8)}` }
                        : {}),
                    timeout: 5000,
                });
            } catch {
                // Notify isn't available during boot — ignore.
            }
        }

        // every failed API call lands in DevTools with the same
        // shape (method, path, status, code, correlation id, details).
        // The 5xx path used to log; lifted to all non-2xx so a user
        // pasting a toast caption ("ref: 4f8c0312") into a bug report
        // gives a dev one grep to find the request.
        if (status > 0 || isNetworkError) {
            console.warn(
                `[api] ${method} ${path} → ${status || 'network'} ${code} (${correlationId})`,
                details,
            );
        }

        return Promise.reject(
            new NormalisedApiError({
                status,
                code,
                message,
                details,
                correlationId,
                isNetworkError,
                method,
                url: path,
            }),
        );
    }

    isCustomApiErrorResponse = (error: unknown): error is ApiErrorResponse =>
        error !== null &&
        typeof error === 'object' &&
        'detail' in error &&
        'status' in error &&
        'errors' in error &&
        'title' in error &&
        'type' in error;

    async patch<TResponse = unknown, TBody = unknown>(
        path: string,
        body: TBody
    ): Promise<HttpClientResponse<TResponse>> {
        try {
            return (await this.axios.patch<TResponse>(path, body)).data;
        } catch (error) {
            return this.handleError(error as AxiosError, 'PATCH', path);
        }
    }

    async post<TResponse = unknown, TBody = unknown>(
        path: string,
        body: TBody,
        options?: RequestOptions,
    ): Promise<HttpClientResponse<TResponse>> {
        try {
            // The instance-level `Content-Type: application/json` default makes
            // axios serialise a FormData body as JSON (its defaults transform
            // runs before the adapter's multipart check), which broke every
            // chunked upload when the composable moved onto this client. Let
            // the browser mint the multipart boundary for a form body.
            const config = {
                ...(body instanceof FormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : {}),
                ...requestOptionsConfig(options),
            };
            return (await this.axios.post<TResponse>(path, body, config)).data;
        } catch (error) {
            return this.handleError(error as AxiosError, 'POST', path);
        }
    }

    async put<TResponse = unknown, TBody = unknown>(path: string, body: TBody): Promise<HttpClientResponse<TResponse>> {
        try {
            return (await this.axios.put<TResponse>(path, body)).data;
        } catch (error) {
            return this.handleError(error as AxiosError, 'PUT', path);
        }
    }

}
