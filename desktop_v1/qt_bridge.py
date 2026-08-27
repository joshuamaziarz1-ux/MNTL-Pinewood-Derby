"""Embedded credentialless Apps Script runner for Desktop v1.

This intentionally mirrors the browser v36 bridge that was proven to work with
the user's multi-Google-account setup. It uses Qt WebEngine embedded inside the
desktop app, not Chrome/Edge and not browser storage.
"""

from __future__ import annotations

import json
import random
import time
import urllib.parse
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage


class CredentiallessAppsScriptRequest(QObject):
    finished = Signal(object, object)  # payload, error string/None

    def __init__(
        self,
        url: str,
        key: str,
        params: dict[str, Any] | None = None,
        parent: QObject | None = None,
        timeout_ms: int = 19000,
    ) -> None:
        super().__init__(parent)
        self.url = str(url or "")
        self.key = str(key or "")
        self.params = dict(params or {})
        self.timeout_ms = int(timeout_ms)
        self.callback = f"__mnltBridge_{int(time.time() * 1000)}_{random.randint(100000, 999999)}"
        self.tag = "mnltDesktop_" + self.callback
        self.page = QWebEnginePage(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.poll = QTimer(self)
        self.poll.setInterval(120)
        self.poll.timeout.connect(self._poll)
        self.done = False

    def start(self) -> None:
        query = {
            "key": self.key,
            "callback": self.callback,
            "_": int(time.time() * 1000),
        }
        for k, v in self.params.items():
            query[str(k)] = "" if v is None else str(v)
        sep = "&" if "?" in self.url else "?"
        src = self.url + sep + urllib.parse.urlencode(query)

        # Qt WebEngine uses its own fresh cookie jar/profile, separate from the
        # user's Chrome/Google sessions. That means we do not need the browser
        # v36 credentialless iframe trick here. Execute the JSONP endpoint
        # directly as a <script> so Apps Script can call the callback exactly
        # as it does in a normal browser, with no CORS or Python parsing layer.
        html = f"""<!doctype html>
<meta charset="utf-8">
<title>MNLT Bridge</title>
<body></body>
<script>
window.__mnltResult = null;
(function(){{
  const cb={json.dumps(self.callback)};
  window[cb]=function(data){{
    window.__mnltResult={{payload:data}};
  }};
  const s=document.createElement('script');
  s.src={json.dumps(src)};
  s.async=true;
  s.onerror=function(){{
    window.__mnltResult={{error:'Apps Script JSONP script failed to load'}};
  }};
  document.head.appendChild(s);
}})();
</script>"""
        self.page.setHtml(html, QUrl("about:blank"))
        self.timer.start(self.timeout_ms)
        self.poll.start()

    def _poll(self) -> None:
        if self.done:
            return
        self.page.runJavaScript("window.__mnltResult", self._js_result)

    def _js_result(self, value: Any) -> None:
        if self.done or not value:
            return
        if isinstance(value, dict) and value.get("error"):
            self._finish(None, str(value.get("error")))
            return
        if isinstance(value, dict) and "payload" in value:
            payload = value.get("payload")
            if isinstance(payload, dict):
                self._finish(payload, None)
            else:
                self._finish(None, "The Apps Script bridge returned a non-object payload.")

    def _timeout(self) -> None:
        self._finish(None, "The Apps Script bridge timed out.")

    def _finish(self, payload: Any, error: str | None) -> None:
        if self.done:
            return
        self.done = True
        self.timer.stop()
        self.poll.stop()
        self.finished.emit(payload, error)
        self.page.deleteLater()
