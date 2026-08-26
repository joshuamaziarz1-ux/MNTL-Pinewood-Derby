import json
from pathlib import Path

from backup import create_full_backup, verify_backup
from storage import DerbyStore, fresh_state


def test_sqlite_round_trip_and_snapshot(tmp_path: Path):
    store = DerbyStore(tmp_path / "data")
    state = fresh_state()
    state["registrations"].append({"id": 1, "name": "Test Racer", "division": "Traditional"})
    store.save_state(state, reason="test-save")
    loaded = store.load_state()
    assert loaded["registrations"][0]["name"] == "Test Racer"
    snaps = store.list_snapshots()
    assert snaps
    store.close()


def test_photo_is_real_file_and_portable_backup_verifies(tmp_path: Path):
    store = DerbyStore(tmp_path / "data")
    source = tmp_path / "car.jpg"
    source.write_bytes(b"fake-jpeg-test-data")
    saved = store.save_photo(123, "Traditional", source)
    assert saved.is_file()
    assert store.find_photo(123, "Traditional") == saved

    backup = create_full_backup(store, tmp_path / "derby.zip")
    manifest = verify_backup(backup)
    assert manifest["format"] == "MNLT_DERBY_DESKTOP_BACKUP"
    assert "derby.db" in manifest["files"]
    assert any(name.startswith("Photos/") for name in manifest["files"])
    store.close()


def test_database_copy_is_consistent(tmp_path: Path):
    store = DerbyStore(tmp_path / "data")
    state = fresh_state()
    for i in range(25):
        state["registrations"].append({"id": i, "name": f"Racer {i}", "division": "Traditional"})
    store.save_state(state, reason="bulk")
    copy_path = store.copy_database(tmp_path / "copy.db")
    assert copy_path.is_file()
    store.close()

    copied = DerbyStore(tmp_path / "copy_data")
    copied.close()
