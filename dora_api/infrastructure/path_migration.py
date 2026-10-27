"""D2 — one-time migration of legacy on-disk locations into the
config-driven layout.

Runs on dora_api startup. Each migration is idempotent: if the
destination already has the file it stays put and the source is left
alone (operators may have intentionally repopulated it). Source files
move (not copy) so duplicates don't leak.

What it covers:
  - Legacy `./data/dora.data.db` when the user sets
    `DORA_DB_URL=sqlite:///<elsewhere>` or `DORA_DATA_DIR` to a
    different location — files migrate once. Only called when the
    resolved DB URL is SQLite; Postgres has nothing to relocate.
  - Legacy `./data/uploads/*` → `<DATA_DIR>/uploads/*`.
"""
import logging
import shutil
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def migrate_legacy_db(target_db: Path) -> bool:
    """Move a `./data/dora.data.db` from the working dir into the new
    target location when the operator has pointed `DORA_DB_URL` (a
    SQLite URL) or `DORA_DATA_DIR` elsewhere. Returns True if a move
    happened."""
    legacy = Path.cwd() / "data" / "dora.data.db"
    if not legacy.is_file():
        return False
    if legacy.resolve() == target_db.resolve():
        return False  # No-op: legacy location IS the target.
    if target_db.exists():
        # Target already populated — operator made a deliberate choice;
        # leave the legacy file in place for them to clean up manually
        # rather than risk overwriting newer data.
        _LOGGER.warning(
            "Legacy DB %s exists but target %s is already populated. "
            "Skipping migration; remove the legacy file manually if intended.",
            legacy, target_db,
        )
        return False
    target_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target_db))
    _LOGGER.info("Migrated legacy DB %s → %s", legacy, target_db)
    return True


def migrate_legacy_appsettings(target_path: Path) -> bool:
    """D3: appsettings.json used to live at `./config/dapi.appsettings.json`
    (CWD-relative). It now lives under `<DATA_DIR>/config/`. Move it
    once on first boot so dev installs that customised the legacy
    file don't silently lose their tweaks."""
    legacy = Path.cwd() / "config" / "dapi.appsettings.json"
    if not legacy.is_file():
        return False
    if legacy.resolve() == target_path.resolve():
        return False
    if target_path.exists():
        _LOGGER.warning(
            "Legacy appsettings %s exists but target %s is already populated. "
            "Leaving legacy in place.", legacy, target_path,
        )
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target_path))
    _LOGGER.info("Migrated legacy appsettings %s → %s", legacy, target_path)
    return True


def migrate_legacy_uploads(uploads_dir: Path) -> int:
    """Move `./data/uploads/*` into the new uploads dir if the legacy
    path differs from the resolved one. Returns count of files moved."""
    legacy = Path.cwd() / "data" / "uploads"
    if not legacy.is_dir():
        return 0
    if legacy.resolve() == uploads_dir.resolve():
        return 0

    moved = 0
    uploads_dir.mkdir(parents=True, exist_ok=True)
    for src in legacy.iterdir():
        if not src.is_file():
            continue
        target = uploads_dir / src.name
        if target.exists():
            continue
        shutil.move(str(src), str(target))
        moved += 1

    if moved:
        _LOGGER.info(
            "Migrated %d staged upload(s) from %s → %s", moved, legacy, uploads_dir,
        )
    try:
        legacy.rmdir()
    except OSError:
        pass
    return moved
