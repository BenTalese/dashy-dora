"""Pins the security-relevant bits of the shipped deploy config: the compose
file must not bake in insecure cookies, and nginx's per-location add_header
blocks must not silently drop the baseline security headers."""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SECURITY_HEADERS = ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy")


def test__compose__SecureCookiesDefault__IsEmptySoProfileDecides():
    compose = (_ROOT / "compose.yml").read_text(encoding="utf-8")
    assert "- DORA_SECURE_COOKIES=${DORA_SECURE_COOKIES:-}\n" in compose


def _blocks_with_add_header(conf: str) -> list[str]:
    """Each `location ... { ... }` body (no nested braces in this file) plus
    the server-level text outside any location."""
    locations = re.findall(r"location[^{]*\{([^}]*)\}", conf)
    server_level = re.sub(r"location[^{]*\{[^}]*\}", "", conf)
    return [b for b in [server_level, *locations] if "add_header" in b]


def test__nginx__EveryAddHeaderScope__RepeatsSecurityHeaders():
    conf = (_ROOT / "nginx.conf").read_text(encoding="utf-8")
    live = "\n".join(line for line in conf.splitlines() if not line.lstrip().startswith("#"))
    blocks = _blocks_with_add_header(live)
    assert len(blocks) >= 2
    for block in blocks:
        for header in _SECURITY_HEADERS:
            assert f"add_header {header}" in block, (header, block)
