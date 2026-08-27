"""Import a v42 browser Full Derby Backup into the v43 desktop database."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

from storage import DerbyStore, ensure_state

V42_FORMAT = "MNLT_DERBY_FULL_BACKUP"


def _v42_payload(obj: dict[str, Any]) -> OrderedDict:
    return OrderedDict(
        [
            ("format", obj.get("format")),
            ("schema", obj.get("schema")),
            ("appVersion", obj.get("appVersion")),
            ("exportedAt", obj.get("exportedAt")),
            ("state", obj.get("state")),
            ("photos", obj.get("photos")),
            ("extras", obj.get("extras") or {}),
        ]
    )


def verify_v42_integrity(obj: dict[str, Any]) -> bool:
    integrity = obj.get("integrity") or {}
    expected = str(integrity.get("hash") or "").lower()
    if not expected:
        return False
    encoded = json.dumps(_v42_payload(obj), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().lower() == expected


def _decode_data_url(data: str) -> tuple[str, bytes]:
    m = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data or "", flags=re.S)
    if not m:
        raise ValueError("Invalid photo data in v42 backup.")
    mime = m.group(1) or "application/octet-stream"
    body = m.group(3)
    raw = base64.b64decode(body) if m.group(2) else body.encode("utf-8")
    return mime, raw


def _extension(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime.lower(), ".jpg")


def import_v42_backup(store: DerbyStore, path: Path | str) -> dict[str, int]:
    path = Path(path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("format") != V42_FORMAT or not isinstance(obj.get("state"), dict):
        raise ValueError("This is not a v42 Full Derby Backup.")
    if obj.get("integrity") and not verify_v42_integrity(obj):
        raise ValueError("The v42 backup failed its SHA-256 integrity check.")

    state = ensure_state(obj["state"])
    photos = obj.get("photos") or []
    written = 0
    for item in photos:
        key = str(item.get("key") or "")
        if ":" not in key or not item.get("data"):
            continue
        prefix, reg_id = key.split(":", 1)
        if prefix not in ("trad", "mod"):
            continue
        mime, raw = _decode_data_url(item["data"])
        target = store.photos_dir / f"{prefix}_{reg_id}{_extension(mime)}"
        target.write_bytes(raw)
        written += 1

    store.save_state(state, reason="import-v42-browser-backup", snapshot=True)
    return {
        "registrations": len(state.get("registrations", [])),
        "traditional_heats": len(state.get("heats", [])),
        "modified_heats": len(state.get("modified", {}).get("heats", [])),
        "photos": written,
    }
