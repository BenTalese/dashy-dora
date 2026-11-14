"""POST /api/desktop/quit: only the desktop app, which registers a handler, can be quit."""
import threading

import pytest
import requests

from dora_api.features.desktop import quit_desktop

BASE = "http://localhost:5170/api"


@pytest.fixture
def quit_called():
    called = threading.Event()
    quit_desktop.set_quit_handler(called.set)
    yield called
    quit_desktop._quit_handler = None


def test__server_install__quit_is_not_found(api):
    response = api.post(f"{BASE}/desktop/quit")
    assert response.status_code == 404, response.text


def test__desktop__quit_stops_the_app_and_capabilities_say_desktop(api, quit_called):
    assert requests.Session().get(f"{BASE}/auth/capabilities").json()["desktop"] is True
    response = api.post(f"{BASE}/desktop/quit")
    assert response.status_code == 204, response.text
    assert quit_called.wait(timeout=5)


def test__desktop__quit_needs_a_signed_in_user(quit_called):
    response = requests.Session().post(f"{BASE}/desktop/quit")
    assert response.status_code in (401, 403), response.text
    assert not quit_called.wait(timeout=1)
