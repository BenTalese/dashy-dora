"""Which `X-Forwarded-*` hops the API trusts.

The container's own nginx proxies `/api/` to the API over loopback, so every
request the SPA makes arrives from 127.0.0.1 with the browser's address
appended to `X-Forwarded-For`. That hop is always one more than the operator's
`DORA_TRUSTED_PROXY_HOPS`; a request from anywhere else (port 5170 published
directly, a desktop bundle on another interface) gets exactly the configured
count. Only processes on the same host can connect over loopback, so trusting
one extra `X-Forwarded-For` entry from them gives a remote client nothing to
forge. nginx passes `X-Forwarded-Proto` and `X-Forwarded-Host` through
unchanged, so those keep the configured count either way.
"""
from werkzeug.middleware.proxy_fix import ProxyFix

_LOOPBACK = frozenset({"127.0.0.1", "::1"})


class TrustedProxyHops:
    def __init__(self, app, hops: int):
        self._direct = ProxyFix(app, x_for=hops, x_proto=hops, x_host=hops) if hops else app
        self._via_loopback = ProxyFix(app, x_for=hops + 1, x_proto=hops, x_host=hops)

    def __call__(self, environ, start_response):
        if environ.get("REMOTE_ADDR") in _LOOPBACK:
            return self._via_loopback(environ, start_response)
        return self._direct(environ, start_response)
