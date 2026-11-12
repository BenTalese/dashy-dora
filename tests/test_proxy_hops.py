"""The container's nginx hop (loopback) is trusted on top of DORA_TRUSTED_PROXY_HOPS."""
from werkzeug.test import Client
from werkzeug.wrappers import Request, Response

from dora_api.infrastructure.proxy_hops import TrustedProxyHops


def _client(hops: int) -> Client:
    def app(environ, start_response):
        request = Request(environ)
        return Response(f"{request.remote_addr}|{request.scheme}")(environ, start_response)
    return Client(TrustedProxyHops(app, hops))


def _get(client: Client, remote: str, **headers: str) -> str:
    return client.get("/", environ_base={"REMOTE_ADDR": remote}, headers=headers).get_data(as_text=True)


def test__via_container_nginx_the_browser_address_is_used():
    assert _get(_client(0), "127.0.0.1", **{"X-Forwarded-For": "192.168.1.20"}) == "192.168.1.20|http"


def test__a_forged_entry_before_nginx_is_ignored():
    assert _get(_client(0), "127.0.0.1", **{"X-Forwarded-For": "6.6.6.6, 192.168.1.20"}) == "192.168.1.20|http"


def test__a_direct_client_cannot_forge_its_address_with_no_proxy_configured():
    assert _get(_client(0), "203.0.113.9", **{"X-Forwarded-For": "6.6.6.6"}) == "203.0.113.9|http"


def test__behind_one_outer_proxy_the_client_and_scheme_come_through_nginx():
    result = _get(
        _client(1), "127.0.0.1",
        **{"X-Forwarded-For": "198.51.100.7, 172.18.0.1", "X-Forwarded-Proto": "https"},
    )
    assert result == "198.51.100.7|https"


def test__behind_one_outer_proxy_a_direct_request_trusts_one_hop():
    assert _get(_client(1), "172.18.0.1", **{"X-Forwarded-For": "198.51.100.7"}) == "198.51.100.7|http"
