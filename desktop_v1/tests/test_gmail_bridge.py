import json

from gmail_bridge import _division, filter_new_signups, parse_bridge_payload


def test_parse_bridge_payload_accepts_json_and_jsonp():
    obj = {"ok": True, "registrations": [{"messageId": "abc", "name": "Racer"}]}
    assert parse_bridge_payload(json.dumps(obj)) == obj
    assert parse_bridge_payload("mnltDesktopCallback(" + json.dumps(obj) + ");") == obj


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
        {"messageId": "new-2", "name": "New Racer", "receivedAt": "2026-08-27T08:00:00"},
    ]
    out = filter_new_signups(state, rows, ["ignored-1"])
    assert [x["messageId"] for x in out] == ["new-2"]


def test_requests_client_is_available():
    import gmail_bridge
    assert hasattr(gmail_bridge, "requests")


def test_parse_bridge_payload_accepts_wrapper_variants():
    import json
    from gmail_bridge import parse_bridge_payload

    obj = {"ok": True, "registrations": [{"messageId": "m1", "name": "Racer"}]}
    raw = json.dumps(obj)
    assert parse_bridge_payload("/**/__mnltBridge_desktop(" + raw + ");") == obj
    assert parse_bridge_payload("__mnltBridge_desktop && __mnltBridge_desktop(" + raw + ");") == obj
    assert parse_bridge_payload(")]}'\n" + raw) == obj


def test_load_bridge_connection_file(tmp_path):
    import json
    from gmail_bridge import load_bridge_connection_file

    path = tmp_path / "MNLT_Derby_Connection.mnltbridge"
    path.write_text(json.dumps({
        "type": "mnlt-derby-bridge",
        "version": 1,
        "url": "https://script.google.com/macros/s/TEST/exec",
        "key": "secret-key"
    }), encoding="utf-8")

    cfg = load_bridge_connection_file(path)
    assert cfg["url"].endswith("/exec")
    assert cfg["key"] == "secret-key"


def test_bridge_request_matches_v42_get_through_redirect(monkeypatch):
    import json
    import threading
    import urllib.parse
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import gmail_bridge
    from gmail_bridge import bridge_request

    monkeypatch.setattr(gmail_bridge, "normalize_url", lambda value: str(value))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/exec":
                self.send_response(302)
                self.send_header("Location", "/payload?" + parsed.query)
                self.end_headers()
                return
            q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            key = q.get("key", [""])[0]
            callback = q.get("callback", ["cb"])[0]
            payload = {
                "ok": key == "v42-key+with/special=chars",
                "registrations": [{"messageId": "m1", "name": "Redirect Racer"}],
            }
            body = f"{callback}({json.dumps(payload)});".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = bridge_request(
            f"http://127.0.0.1:{server.server_port}/exec",
            "v42-key+with/special=chars",
            {},
            timeout=5,
        )
        assert payload["ok"] is True
        assert payload["registrations"][0]["name"] == "Redirect Racer"
    finally:
        server.shutdown()
        server.server_close()
