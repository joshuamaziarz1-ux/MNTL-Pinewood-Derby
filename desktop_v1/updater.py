"""Permanent bootstrap/updater for MNLT Derby Manager Desktop.

This executable is intentionally separate from the race manager app. It never
opens, edits, migrates, or deletes derby.db, Photos, or Backups.

On every launch it checks the public Desktop v1 release manifest. If a newer
verified app build exists, it downloads it to the Program folder, verifies its
SHA-256 hash, atomically swaps the program file, then launches the manager.
If the internet is unavailable, the last installed app opens normally.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MANIFEST_URL = (
    "https://github.com/joshuamaziarz1-ux/MNTL-Pinewood-Derby/"
    "releases/download/desktop-v1-latest/desktop-v1-manifest.json"
)
EXPECTED_CHANNEL = "desktop-v1"
APP_FILENAME = "MNLT_Derby_Manager_App.exe"
UPDATER_VERSION = 1


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "MNLT Derby Manager"
    return Path.home() / "AppData" / "Local" / "MNLT Derby Manager"


def program_dir() -> Path:
    path = data_dir() / "Program"
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_path() -> Path:
    return program_dir() / APP_FILENAME


def version_path() -> Path:
    return program_dir() / "installed_build.json"


def log_path() -> Path:
    return program_dir() / "updater.log"


def log(message: str) -> None:
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def message(title: str, text: str, icon: int = 0x40) -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(None, text, title, icon)
            return
        except Exception:
            pass


def fetch_bytes(url: str, timeout: int = 20) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("_mnlt", str(int(time.time() * 1000))))
    uncached = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )
    request = urllib.request.Request(
        uncached,
        headers={
            "User-Agent": "MNLT-Derby-Manager-Updater/1",
            "Accept": "application/json,application/octet-stream,*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_manifest() -> dict[str, Any]:
    raw = fetch_bytes(MANIFEST_URL, timeout=15)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Update manifest was not an object.")
    if data.get("channel") != EXPECTED_CHANNEL:
        raise ValueError("Update manifest channel did not match Desktop v1.")
    if int(data.get("min_updater", 1)) > UPDATER_VERSION:
        raise RuntimeError("This updater is too old for the newest Desktop v1 build.")
    asset_url = str(data.get("asset_url", ""))
    if not asset_url.startswith(
        "https://github.com/joshuamaziarz1-ux/MNTL-Pinewood-Derby/releases/download/"
    ):
        raise ValueError("Update manifest contained an unexpected download location.")
    digest = str(data.get("sha256", "")).lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("Update manifest SHA-256 value was invalid.")
    if not str(data.get("build", "")).strip():
        raise ValueError("Update manifest had no build identifier.")
    return data


def load_installed() -> dict[str, Any]:
    try:
        data = json.loads(version_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_installed(manifest: dict[str, Any]) -> None:
    payload = {
        "channel": EXPECTED_CHANNEL,
        "version": manifest.get("version", "Desktop v1"),
        "build": manifest.get("build", ""),
        "sha256": manifest.get("sha256", ""),
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updater": UPDATER_VERSION,
    }
    temp = version_path().with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp, version_path())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def install_build(manifest: dict[str, Any]) -> None:
    target = app_path()
    incoming = target.with_suffix(".download")
    previous = target.with_suffix(".previous.exe")
    try:
        raw = fetch_bytes(str(manifest["asset_url"]), timeout=120)
        incoming.write_bytes(raw)
        actual = sha256(incoming)
        expected = str(manifest["sha256"]).lower()
        if actual != expected:
            raise ValueError("Downloaded program failed its SHA-256 integrity check.")

        if previous.exists():
            previous.unlink()
        if target.exists():
            os.replace(target, previous)
        try:
            os.replace(incoming, target)
        except Exception:
            if previous.exists() and not target.exists():
                os.replace(previous, target)
            raise
        save_installed(manifest)
        log(f"Installed build {manifest.get('build')}.")
    finally:
        try:
            if incoming.exists():
                incoming.unlink()
        except Exception:
            pass


def launch_app() -> int:
    target = app_path()
    if not target.is_file():
        return 2
    subprocess.Popen([str(target)], cwd=str(program_dir()))
    return 0


def main() -> int:
    program_dir()
    installed = load_installed()
    manifest: dict[str, Any] | None = None
    update_error: Exception | None = None

    try:
        manifest = fetch_manifest()
    except Exception as exc:
        update_error = exc
        log(f"Update check failed: {exc}")

    needs_install = not app_path().is_file()
    if manifest is not None:
        needs_install = needs_install or str(installed.get("build", "")) != str(manifest.get("build", ""))

    if manifest is not None and needs_install:
        if app_path().is_file():
            message(
                "MNLT Derby Manager Update",
                "A newer Derby Manager build is ready.\n\n"
                "Click OK and wait while it updates. The Derby Manager will open automatically.",
            )
        else:
            message(
                "MNLT Derby Manager Setup",
                "Desktop v1 will install its race manager program now.\n\n"
                "Click OK and wait. Your Derby database and backups are stored separately and will not be changed.",
            )
        try:
            install_build(manifest)
        except Exception as exc:
            update_error = exc
            log(f"Update install failed: {exc}")

    if app_path().is_file():
        if update_error is not None:
            log("Opening previously installed app after update failure.")
        return launch_app()

    detail = str(update_error) if update_error else "No Desktop v1 build could be downloaded."
    message(
        "MNLT Derby Manager",
        "The Derby Manager could not be installed.\n\n"
        f"{detail}\n\n"
        "Check the internet connection and try again.",
        0x10,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
