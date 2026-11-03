"""FU-640 / 19-D4: a refused write leaves a WARNING line naming the route,
the status and the reason the user was shown; reads and successes don't."""
import logging

import requests

BASE = "http://localhost:5170/api"
_LOGGER_NAME = "dora_api.infrastructure.middleware"


def _warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records
            if r.name == _LOGGER_NAME and r.levelno == logging.WARNING]


def test__rejected_write__logs_route_status_and_reason(api, caplog):
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resp = requests.post(f"{BASE}/client-logs", json={"level": "loud", "message": "x"})
    assert resp.status_code == 400, resp.text
    lines = _warnings(caplog)
    assert any(line.startswith("POST /api/client-logs -> 400") and "level" in line for line in lines), lines


def test__rejected_read__is_not_logged(api, caplog):
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resp = requests.get(f"{BASE}/stock-items/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404, resp.text
    assert not _warnings(caplog)
