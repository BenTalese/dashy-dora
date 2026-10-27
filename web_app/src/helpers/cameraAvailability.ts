// What to tell the user about the camera on this device. One authority, so the
// scan overlay and the admin scanning toggle say the same thing (R-003).
//
// Browsers normally only expose `navigator.mediaDevices` on a secure origin
// (HTTPS or localhost), so a self-hosted Dora on `http://192.168.x.x` usually
// can't open the camera. "Usually" is the point: some browsers and setups allow
// it anyway (owner, 2026-09-27: it worked for him over http). So Dora never
// blocks on the origin. It warns, tries, and only explains the http cause once
// an attempt has actually failed.
//
// The native app is unaffected: Capacitor serves the SPA from
// `https://localhost`, which is a secure origin.

import { isNativePlatform } from 'src/helpers/platform';

export type CameraUnavailable = {
    kind: 'insecure-context' | 'unsupported';
    message: string;
};

const INSECURE_WARNING =
    'This page is on plain http, so your browser may not allow the camera.';

const INSECURE_MESSAGE =
    'Your browser won\'t allow the camera over plain http. Use the Android app '
    + 'or serve Dora over HTTPS, or type the barcode below.';

const UNSUPPORTED_MESSAGE =
    'This browser doesn\'t support the camera. Type the barcode below.';

function onInsecureOrigin(): boolean {
    return !window.isSecureContext && !isNativePlatform();
}

/** A heads-up to show before trying, or null when there's nothing to say. */
export function insecureContextWarning(): string | null {
    return onInsecureOrigin() ? INSECURE_WARNING : null;
}

/** After a failed start: whether the browser simply has no camera API here,
 *  and why. Null means the API exists and the failure was something else
 *  (permission, no device), which the caller reports itself. */
export function explainCameraFailure(): CameraUnavailable | null {
    if (navigator.mediaDevices?.getUserMedia !== undefined) return null;
    return onInsecureOrigin()
        ? { kind: 'insecure-context', message: INSECURE_MESSAGE }
        : { kind: 'unsupported', message: UNSUPPORTED_MESSAGE };
}
