import json
import os
import stat
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import gmail_bridge
from gmail_bridge import (
    BridgeError,
    _division,
    bridge_request,
    filter_new_signups,
    load_bridge_connection_file,
    load_config,
    normalize_url,
    save_config,
)


def test_normalize_url_removes_runtime_params_and_keeps_real_query():
    url = (
        "https://script.google.com/macros/s/DEPLOYMENT/exec"
        "?authuser=1&existing=value&key=old&callback=oldcb&_="
        "#browser-fragment"
    )
    assert normalize_url(url) == (
        "https://script.google.com/macros/s/DEPLOYMENT/exec?existing=value"
    )


def test_division_mapping_handles_snappages_labels():
    assert _division("Traditional") == "Traditional"
    assert _division("Fully Modified Race") == "Modified"
    assert _division("Both Races") == "Both"


def test_filter_new_signups_deduplicates_by_message_and_racer_name():
    state = {
        "registrations": [
            {"name": "Existing Racer", "sourceMessageId": "already-imported"},
        ]
    }
    rows = [
        {"messageId": "already-imported", "name": "Different Name"},
        {"messageId": "new-1", "name": "Existing Racer"},
        {"messageId": "ignored-1", "name": "Ignored Racer"},
        {
            "messageId": "new-2",
            "name": "New Racer",
            "receivedAt": "2026-08-27T08:00:00",
        },
    ]
    out = filter_new_signups(state, rows, ["ignored-1"])
    assert [x["messageId"] for x in out] == ["new-2"]


def test_load_bridge_connection_file_preserves_key_exactly(tmp_path):
    path = tmp_path / "MNLT_Derby_Connection.json"
    exact_key = "v42-key+with/special=chars=="
    path.write_text(
        json.dumps(
            {
                "type": "mnlt-derby-bridge",
                "version": 1,
                "url": (
                    "https://script.google.com/macros/s/TEST/exec"
                    "?authuser=1"
                ),
                "key": exact_key,
            }
        ),
        encoding="utf-8",
    )

    cfg = load_bridge_connection_file(path)
    assert cfg["url"] == "https://script.google.com/macros/s/TEST/exec"
    assert cfg["key"] == exact_key


def test_local_config_preserves_key_and_is_private(tmp_path):
    class Store:
        data_dir = tmp_path

    exact_key = "  v42-key+with/special=chars==  "
    save_config(Store(), {"url": "https://example.invalid", "key": exact_key})

    assert load_config(Store())["key"] == exact_key
    config_path = tmp_path / gmail_bridge.CONFIG_NAME
    assert config_path.is_file()

    # POSIX chmod controls group/other permission bits. Windows uses ACLs
    # instead, and Python's st_mode does not represent those ACLs.
    if os.name != "nt":
        mode = stat.S_IMODE(config_path.stat().st_mode)
        assert mode & 0o077 == 0


class _BridgeHandler(BaseHTTPRequestHandler):
    last_query = {}
    response_payload = {
        "ok": True,
        "registrations": [{"messageId": "m1", "name": "Redirect Racer"}],
    }
    html_mode = False

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)

        if parsed.path == "/exec":
            self.send_response(302)
            self.send_header("Location", "/payload?" + parsed.query)
            self.end_headers()
            return

        type(self).last_query = urllib.parse.parse_qs(
            parsed.query,
            keep_blank_values=True,
        )

        if type(self).html_mode:
            body = (
                "<html><body>PRIVATE_RACER_NAME PRIVATE_EMAIL</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            callback = type(self).last_query.get("callback", [""])[0]
            payload = json.dumps(type(self).response_payload)
            body = f"{callback}({payload});".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")

        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def _run_server():
    _BridgeHandler.last_query = {}
    _BridgeHandler.response_payload = {
        "ok": True,
        "registrations": [{"messageId": "m1", "name": "Redirect Racer"}],
    }
    _BridgeHandler.html_mode = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_bridge_request_matches_v42_jsonp_and_protects_callback(monkeypatch):
    server = _run_server()
    monkeypatch.setattr(gmail_bridge, "normalize_url", lambda value: str(value))
    exact_key = "v42-key+with/special=chars=="

    try:
        payload = bridge_request(
            f"http://127.0.0.1:{server.server_port}/exec",
            exact_key,
            {
                "key": "replacement-must-not-win",
                "callback": "jsonpMustNotBeSent",
                "_": "caller-cache-value",
            },
            timeout=5,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert payload["ok"] is True
    assert _BridgeHandler.last_query["key"] == [exact_key]
    assert _BridgeHandler.last_query["callback"] == [gmail_bridge.DESKTOP_CALLBACK]
    assert _BridgeHandler.last_query["callback"] != ["jsonpMustNotBeSent"]
    assert _BridgeHandler.last_query["_"] != ["caller-cache-value"]


def test_bridge_request_constructs_draft_action(monkeypatch):
    server = _run_server()
    monkeypatch.setattr(gmail_bridge, "normalize_url", lambda value: str(value))
    _BridgeHandler.response_payload = {"ok": True, "draftCreated": True}

    try:
        payload = bridge_request(
            f"http://127.0.0.1:{server.server_port}/exec",
            "secret",
            {
                "action": "createDraft",
                "messageId": "msg-123",
                "division": "Both",
                "tradCar": "Red Rocket",
                "modCar": "Wild Thing",
            },
            timeout=5,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert payload["draftCreated"] is True
    assert _BridgeHandler.last_query["action"] == ["createDraft"]
    assert _BridgeHandler.last_query["messageId"] == ["msg-123"]
    assert _BridgeHandler.last_query["division"] == ["Both"]
    assert _BridgeHandler.last_query["tradCar"] == ["Red Rocket"]
    assert _BridgeHandler.last_query["modCar"] == ["Wild Thing"]
    assert _BridgeHandler.last_query["callback"] == [gmail_bridge.DESKTOP_CALLBACK]


def test_bridge_error_diagnostics_do_not_echo_private_response(monkeypatch):
    server = _run_server()
    monkeypatch.setattr(gmail_bridge, "normalize_url", lambda value: str(value))
    _BridgeHandler.html_mode = True

    try:
        with pytest.raises(BridgeError) as exc:
            bridge_request(
                f"http://127.0.0.1:{server.server_port}/exec",
                "secret",
                {},
                timeout=5,
            )
    finally:
        server.shutdown()
        server.server_close()

    message = str(exc.value)
    assert "expected v42 callback response" in message
    assert "text/html" in message
    assert "PRIVATE_RACER_NAME" not in message
    assert "PRIVATE_EMAIL" not in message
