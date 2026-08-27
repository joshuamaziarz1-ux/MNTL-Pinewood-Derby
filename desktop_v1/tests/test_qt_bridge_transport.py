import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from qt_bridge import CredentiallessAppsScriptRequest, parse_apps_script_document


def test_parse_direct_jsonp_document():
    obj = {"ok": True, "registrations": [{"messageId": "m1", "name": "Racer"}]}
    raw = "__mnltBridge_123_456(" + json.dumps(obj) + ");"
    assert parse_apps_script_document(raw) == obj


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)

        # Mimic Apps Script's normal redirect hop before the final content
        # response. Preserve the original query exactly.
        if parsed.path == "/exec":
            target = "/payload"
            if parsed.query:
                target += "?" + parsed.query
            self.send_response(302)
            self.send_header("Location", target)
            self.end_headers()
            return

        query = urllib.parse.parse_qs(parsed.query)
        callback = query.get("callback", ["cb"])[0]
        key = query.get("key", [""])[0]
        payload = {
            "ok": key == "test-secret",
            "registrations": [{"messageId": "m1", "name": "Qt Test Racer"}],
        }
        body = f"{callback}({json.dumps(payload)});".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def test_qt_webengine_direct_navigation_reads_jsonp_end_to_end():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        app = QApplication.instance() or QApplication([])
        loop = QEventLoop()
        result = {"payload": None, "error": "no result"}

        req = CredentiallessAppsScriptRequest(
            f"http://127.0.0.1:{server.server_port}/exec",
            "test-secret",
            {},
            timeout_ms=10000,
        )

        def finished(payload, error):
            result["payload"] = payload
            result["error"] = error
            loop.quit()

        req.finished.connect(finished)
        QTimer.singleShot(15000, loop.quit)
        req.start()
        loop.exec()

        assert result["error"] is None
        assert result["payload"]["ok"] is True
        assert result["payload"]["registrations"][0]["name"] == "Qt Test Racer"
    finally:
        server.shutdown()
        server.server_close()
