"""QA2-21: the index.html Flask serves is marked same-origin.

Flask serves the SPA only when nothing sits in front of it (the desktop bundle
on a random port, a single-origin deploy). That page must call `/api` on its
own origin, not the split-port compose's `<host>:5170`, so the server marks it
and `web_app/src/services/api/backendUrl.ts` reads the mark. nginx serves the
build untouched, so the compose path never carries it.
"""
from dora_api.app import app
from dora_api.features.spa.serve_spa import SAME_ORIGIN_META, _serve_file_or_index


def _spa(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text(
        "<!doctype html><html><head><title>Dora</title></head><body></body></html>",
        encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setenv("DORA_SPA_DIR", str(tmp_path))


def test__index_and_history_routes_carry_the_same_origin_mark(tmp_path, monkeypatch):
    _spa(tmp_path, monkeypatch)
    with app.test_request_context("/"):
        for requested in (None, "index.html", "cookbook/abc"):
            response = _serve_file_or_index(requested)
            body = response.get_data(as_text=True)
            assert SAME_ORIGIN_META in body
            assert body.index(SAME_ORIGIN_META) < body.index("<title>")
            assert response.headers["Cache-Control"] == "no-cache"


def test__static_files_are_sent_untouched(tmp_path, monkeypatch):
    _spa(tmp_path, monkeypatch)
    with app.test_request_context("/app.js"):
        response = _serve_file_or_index("app.js")
        response.direct_passthrough = False
        assert SAME_ORIGIN_META not in response.get_data(as_text=True)
