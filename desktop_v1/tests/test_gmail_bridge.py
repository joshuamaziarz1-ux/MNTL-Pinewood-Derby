import json
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
    normalize_url,
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
            body = json.dumps(type(self).response_payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")

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


def test_bridge_request_uses_plain_json_and_never_sends_callback(monkeypatch):
    server = _run_server()
    monkeypatch.setattr(gmail_bridge, "normalize_url", lambda value: str(value))
    exact_key = "v42-key+with/special=chars=="

    try:
        payload = bridge_request(
            f"http://127.0.0.1:{server.server_port}/exec",
            exact_key,
            {},
            timeout=5,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert payload["ok"] is True
    assert _BridgeHandler.last_query["key"] == [exact_key]
    assert "callback" not in _BridgeHandler.last_query


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
    assert "callback" not in _BridgeHandler.last_query


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
    assert "plain JSON" in message
    assert "text/html" in message
    assert "PRIVATE_RACER_NAME" not in message
    assert "PRIVATE_EMAIL" not in message
