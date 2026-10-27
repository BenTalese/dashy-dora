"""A dict key for an id read back from raw SQL, whatever shape the driver
returns: a `UUID`, SQLite's 16 raw bytes, or a string."""
from uuid import UUID


def uuid_key(value) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return str(UUID(bytes=value))
    return str(value)


def uuid_bind(value, dialect_name: str) -> bytes | str:
    """A UUID in the bind form a raw `text()` statement needs: the 16 bytes for
    SQLite's BINARY(16) columns, the canonical string for Postgres' native
    `uuid` (which rejects a bytea bind: `operator does not exist: uuid = bytea`)."""
    as_uuid = UUID(uuid_key(value))
    return as_uuid.bytes if dialect_name == "sqlite" else str(as_uuid)
