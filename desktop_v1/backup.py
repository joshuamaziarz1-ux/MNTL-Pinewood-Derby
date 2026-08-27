"""Portable backup/restore for MNLT Derby Manager v43 Desktop."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from storage import DerbyStore

BACKUP_FORMAT = "MNLT_DERBY_DESKTOP_BACKUP"
BACKUP_SCHEMA = 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def create_full_backup(store: DerbyStore, destination: Path | str | None = None) -> Path:
    """Create a portable ZIP containing a consistent DB copy, photos, and checksums."""
    destination = Path(destination) if destination else store.backups_dir / f"MNLT_Derby_Backup_{_timestamp()}.zip"
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mnlt_backup_") as td:
        stage = Path(td)
        db_copy = store.copy_database(stage / "derby.db")
        photo_stage = stage / "Photos"
        if store.photos_dir.exists():
            shutil.copytree(store.photos_dir, photo_stage, dirs_exist_ok=True)
        else:
            photo_stage.mkdir()

        files = [db_copy] + [p for p in photo_stage.rglob("*") if p.is_file()]
        checksums = {str(p.relative_to(stage)).replace("\\", "/"): _sha256(p) for p in files}
        manifest: dict[str, Any] = {
            "format": BACKUP_FORMAT,
            "schema": BACKUP_SCHEMA,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "app_version": "v43",
            "files": checksums,
        }
        manifest_path = stage / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        temp_zip = destination.with_suffix(destination.suffix + ".tmp")
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(manifest_path, "manifest.json")
            for p in files:
                zf.write(p, str(p.relative_to(stage)).replace("\\", "/"))
        os.replace(temp_zip, destination)
    return destination


def verify_backup(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix="mnlt_verify_") as td:
        stage = Path(td)
        with zipfile.ZipFile(path, "r") as zf:
            if "manifest.json" not in zf.namelist():
                raise ValueError("Backup has no manifest.")
            zf.extractall(stage)
        manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("format") != BACKUP_FORMAT:
            raise ValueError("This is not an MNLT desktop backup.")
        for rel, expected in (manifest.get("files") or {}).items():
            p = stage / rel
            if not p.is_file():
                raise ValueError(f"Backup is missing {rel}.")
            actual = _sha256(p)
            if actual.lower() != str(expected).lower():
                raise ValueError(f"Backup integrity check failed for {rel}.")
        db = stage / "derby.db"
        if not db.is_file():
            raise ValueError("Backup is missing derby.db.")
        return manifest


def restore_full_backup(store: DerbyStore, source: Path | str) -> None:
    """Verify and restore a backup. Current data is backed up first."""
    source = Path(source)
    verify_backup(source)
    create_full_backup(store, store.backups_dir / f"Before_Restore_{_timestamp()}.zip")

    with tempfile.TemporaryDirectory(prefix="mnlt_restore_") as td:
        stage = Path(td)
        with zipfile.ZipFile(source, "r") as zf:
            zf.extractall(stage)

        store.close()
        db_source = stage / "derby.db"
        db_temp = store.db_path.with_suffix(".restore.tmp")
        shutil.copy2(db_source, db_temp)
        os.replace(db_temp, store.db_path)

        restored_photos = stage / "Photos"
        photo_temp = store.data_dir / "Photos.restore.tmp"
        if photo_temp.exists():
            shutil.rmtree(photo_temp)
        photo_temp.mkdir(parents=True)
        if restored_photos.exists():
            shutil.copytree(restored_photos, photo_temp, dirs_exist_ok=True)
        old_photos = store.photos_dir
        old_backup = store.data_dir / "Photos.before-restore"
        if old_backup.exists():
            shutil.rmtree(old_backup)
        if old_photos.exists():
            os.replace(old_photos, old_backup)
        os.replace(photo_temp, old_photos)
        if old_backup.exists():
            shutil.rmtree(old_backup, ignore_errors=True)


def prune_backups(folder: Path | str, keep: int = 30) -> None:
    folder = Path(folder)
    files = sorted(folder.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[keep:]:
        try:
            p.unlink()
        except OSError:
            pass
