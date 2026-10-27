// Where is the SPA running? One answer per question (finalisation 17-R20):
// `isNativePlatform` used to live in `services/api/backendUrl.ts` and was
// imported from there for camera, routing and boot reasons that have nothing
// to do with URLs; `isIosSafari` lived in the PWA lifecycle composable.
import { Capacitor } from '@capacitor/core';

/** Inside the Capacitor shell (Android / iOS), not a browser tab. */
export function isNativePlatform(): boolean {
    try {
        return Capacitor.isNativePlatform();
    } catch {
        return false;
    }
}

/** Safari on iOS proper (not Chrome / Firefox / Edge on iOS, which wrap
 *  WebKit but report their own tokens). */
export function isIosSafari(): boolean {
    if (typeof navigator === 'undefined') return false;
    const ua = navigator.userAgent;
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !(/CriOS|FxiOS|EdgiOS/.test(ua));
    return isIOS && /Safari/.test(ua);
}

/** `window.isSecureContext`, false when there is no window. Service workers,
 *  install prompts and the Wake Lock API all need a secure context. */
export function isSecureContext(): boolean {
    return typeof window !== 'undefined' && window.isSecureContext === true;
}
