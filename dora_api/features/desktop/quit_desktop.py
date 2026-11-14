"""POST /api/desktop/quit — stop the desktop app from inside Dora.

The desktop bundle (`desktop_app.py`) has no window: the app runs in the
background and opens in the browser. Where the desktop shows tray icons the
tray menu has Quit, but some (GNOME, for one) don't, so the app needs its
own way out. `desktop_app.py` registers the handler that stops it; a server
install never does, so there the endpoint is a 404 and the capability is off.
"""
import threading
from collections.abc import Callable

from dora_api.features.routers import DESKTOP_ROUTER
from dora_api.infrastructure.api_response import no_content, not_found_detail

_quit_handler: Callable[[], None] | None = None


def set_quit_handler(handler: Callable[[], None]) -> None:
    global _quit_handler
    _quit_handler = handler


def can_quit() -> bool:
    return _quit_handler is not None


@DESKTOP_ROUTER.route("/quit", methods=["POST"])
def quit_desktop():
    handler = _quit_handler
    if handler is None:
        return not_found_detail("Only the desktop app can be quit from here.")
    # After a beat, so this response reaches the browser before the server stops.
    threading.Timer(0.5, handler).start()
    return no_content()
