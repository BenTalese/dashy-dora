import os
import secrets
from datetime import date, datetime
from pathlib import Path

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine

from dora_api.infrastructure.configuration_manager import DoraConfig

# R-0NN — every constraint gets a deterministic, conventional name. Without
# this, SQLite + Alembic batch_alter_table can't reproduce unnamed UNIQUE /
# CHECK / FK constraints when it rebuilds a table (SQLite has no
# ALTER ... ADD/DROP CONSTRAINT), and the migration chain dies at the first
# such table. See ENGINEERING_STANDARDS.md.
NAMING_CONVENTION = {
    "ix":  "ix_%(table_name)s_%(column_0_name)s",
    "uq":  "uq_%(table_name)s_%(column_0_name)s",
    "ck":  "ck_%(table_name)s_%(constraint_name)s",
    "fk":  "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk":  "pk_%(table_name)s",
}

config_manager = DoraConfig()


class DoraJSONProvider(DefaultJSONProvider):
    """Serialise date/datetime as ISO 8601 instead of Flask's RFC-1123
    default ("Tue, 01 Sep 2026 00:00:00 GMT"). The RFC format silently broke
    every client-side string comparison against ISO dates — e.g. the route
    guard's `planned_shop_date === '2026-09-01'` never matched, so the
    "today's list" landing pick could not work (found during shopping-list
    UX v2; the Chunk-7 e2e tests always expected ISO). ISO also sorts
    correctly as a plain string, which RFC does not.

    Naive datetimes are written as UTC (with a trailing `Z`). Backstory:
    SQLite stores `DateTime(timezone=True)` columns as plain strings —
    the tzinfo is silently stripped on read despite the column flag, so
    a value written as `datetime.now(UTC)` comes back naive. Without
    explicit tagging here, `o.isoformat()` produces a timezone-less ISO
    string that the SPA's `new Date(iso)` parses as *local time*, shifting
    every relative-time display by the user's UTC offset (the
    "10 hours ago" bug for Sydney users). Tagging naive timestamps as UTC
    is correct because every datetime the API writes is created with
    `datetime.now(UTC)` — there is no naive non-UTC source in the code.
    """

    @staticmethod
    def default(o: object):
        # datetime first — it's a subclass of date.
        if isinstance(o, datetime):
            if o.tzinfo is None:
                return o.isoformat() + "Z"
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = DoraJSONProvider(app)
app.config['SQLALCHEMY_DATABASE_URI'] = config_manager.get_db_connection_string()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # True has been deprecated and does nothing

# Session / cookie config. The SECRET_KEY signs the session cookie. Set
# DORA_SECRET_KEY in the environment for prod; the dev fallback writes a
# stable random key to disk so sessions survive restarts. Never commit the
# generated file — it's already covered by the .data folder gitignore.
_SecretKeyFile = config_manager.get_data_dir() / '.secret_key'
_SecretKeyFromEnv = os.environ.get('DORA_SECRET_KEY')
if _SecretKeyFromEnv:
    app.config['SECRET_KEY'] = _SecretKeyFromEnv
else:
    if not _SecretKeyFile.exists():
        _SecretKeyFile.parent.mkdir(parents=True, exist_ok=True)
        _SecretKeyFile.touch(mode=0o600)  # owner-only before the key lands
        _SecretKeyFile.write_text(secrets.token_hex(32))
    app.config['SECRET_KEY'] = _SecretKeyFile.read_text().strip()

# Same-site=Lax keeps the session cookie on top-level navigations and same-
# origin requests. For cross-origin SPA access (dev: web 5174 → api 5170),
# the CORS layer must enable credentials, and axios must set withCredentials.
app.config['SESSION_COOKIE_NAME'] = 'dora_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Secure cookies require HTTPS. Default is fail-closed in production
# (`DORA_ENV=production` ⇒ Secure=True) so a prod deploy that forgets to
# set the env var doesn't silently ship the session cookie over plain
# HTTP. Explicit `DORA_SECURE_COOKIES=false` opts back out for internal-
# LAN / VPN / home-lab installs that deliberately serve HTTP; the
# `warn_if_insecure_cookies_in_production()` boot check surfaces the
# choice once so the operator sees it and picks intentionally.
from dora_api.infrastructure.profile import is_production
_SecureCookiesEnv = os.environ.get('DORA_SECURE_COOKIES', '').strip().lower()
if _SecureCookiesEnv in ('1', 'true', 'yes', 'on'):
    app.config['SESSION_COOKIE_SECURE'] = True
elif _SecureCookiesEnv in ('0', 'false', 'no', 'off'):
    app.config['SESSION_COOKIE_SECURE'] = False
else:
    app.config['SESSION_COOKIE_SECURE'] = is_production()

# Reverse proxy awareness (finalisation 15-R1). A self-host fronted by nginx /
# Caddy / Traefik / Cloudflare hands Flask the *proxy's* address, so the
# login rate limit (5/min per IP) throttled the whole household as one
# client and the audit log recorded the proxy IP for everyone. Opt-in by
# hop count — trusting `X-Forwarded-*` unconditionally would let any direct
# client spoof its address, which is worse than the bug. Set
# `DORA_TRUSTED_PROXY_HOPS=1` for one proxy in front of the API.
_ProxyHops = config_manager.get_trusted_proxy_hops()
if _ProxyHops > 0:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
        app.wsgi_app, x_for=_ProxyHops, x_proto=_ProxyHops, x_host=_ProxyHops, x_prefix=0,
    )

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
config_manager.get_data_dir().mkdir(parents=True, exist_ok=True)
db.init_app(app)


# SQLite does not enforce foreign-key constraints (including ON DELETE
# cascades) unless this PRAGMA is set per connection.
@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

from dora_api.persistence.table_mappings import \
    configure_mappings  # noqa: E402

configure_mappings(db)

migrate = Migrate()
migrate.init_app(app, db, str(Path(__file__).parent / 'persistence' / 'migrations'))
