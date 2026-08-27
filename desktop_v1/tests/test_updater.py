import hashlib
import json

import pytest

import updater


def test_fetch_manifest_validates_channel_and_hash(monkeypatch):
    payload = {
        "channel": "desktop-v1",
        "version": "Desktop v1",
        "build": "abc123",
        "min_updater": 1,
        "asset_url": "https://github.com/joshuamaziarz1-ux/MNTL-Pinewood-Derby/releases/download/desktop-v1-latest/MNLT_Derby_Manager_App.exe",
        "sha256": "a" * 64,
    }
    monkeypatch.setattr(updater, "fetch_bytes", lambda *args, **kwargs: json.dumps(payload).encode("utf-8"))
    assert updater.fetch_manifest()["build"] == "abc123"

    payload["channel"] = "wrong"
    with pytest.raises(ValueError):
        updater.fetch_manifest()


def test_sha256_matches_file(tmp_path):
    path = tmp_path / "app.exe"
    path.write_bytes(b"mnlt desktop updater test")
    assert updater.sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()
