/**
 * Tiny SPA-side logger. Mirrors the standard log levels and ships
 * `warn` + `error` to the backend so client crashes land in the same
 * log stream as server errors. `debug` and `info` stay in DevTools.
 *
 * Client-side rate limit (max 10 sent / 60 s) shadows the server's
 * limit so a broken page doesn't generate a thundering herd of POSTs
 * while we're already in trouble.
 *
 * This module is the logger only. The global error wiring (window.onerror,
 * unhandledrejection, app.config.errorHandler) lives in
 * `boot/globalErrorHandler.ts`, which toasts, rolls back and calls
 * `clientLog.error` — a second installer here had no caller and would have
 * shipped every error twice (finalisation 20-R1).
 */
import { csrfHeader, resolveBaseURL } from 'src/services/api/axiosHttpClient';

type Level = 'debug' | 'info' | 'warn' | 'error';

const WINDOW_MS = 60_000;
const MAX_SENDS = 10;
const sendTimes: number[] = [];

function allowSend(): boolean {
    const now = Date.now();
    // Drop stale timestamps so the array stays small.
    while (sendTimes.length && sendTimes[0]! < now - WINDOW_MS) {
        sendTimes.shift();
    }
    if (sendTimes.length >= MAX_SENDS) return false;
    sendTimes.push(now);
    return true;
}

function buildContext(extra?: Record<string, unknown>): Record<string, unknown> {
    return {
        url: typeof window !== 'undefined' ? window.location.href : null,
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
        ...(extra ?? {}),
    };
}

async function ship(level: Level, message: string, context?: Record<string, unknown>): Promise<void> {
    if (level !== 'warn' && level !== 'error') return;
    if (!allowSend()) return;
    try {
        const baseUrl = resolveBaseURL();
        // Plain fetch (not the shared http client) to avoid re-entering
        // the axios interceptor if the failure originated there.
        await fetch(`${baseUrl}/client-logs`, {
            method: 'POST',
            credentials: 'include',
            // FU-571: raw fetch bypasses the axios CSRF interceptor.
            headers: { 'Content-Type': 'application/json', ...csrfHeader() },
            body: JSON.stringify({
                level,
                message: message.slice(0, 2048),
                context: buildContext(context),
            }),
            // Best-effort: don't await long if the network's down.
            keepalive: true,
        });
    } catch {
        // Ignored — logging failures must never break the page.
    }
}

export const clientLog = {
    debug(message: string, context?: Record<string, unknown>) {
        console.debug('[dora]', message, context ?? '');
    },
    info(message: string, context?: Record<string, unknown>) {
        console.info('[dora]', message, context ?? '');
    },
    warn(message: string, context?: Record<string, unknown>) {
        console.warn('[dora]', message, context ?? '');
        void ship('warn', message, context);
    },
    error(message: string, context?: Record<string, unknown>) {
        console.error('[dora]', message, context ?? '');
        void ship('error', message, context);
    },
};

export function useClientLogger() {
    return clientLog;
}
