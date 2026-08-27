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

        # Exact strategy from the known-working browser v36 implementation:
        # sandboxed + credentialless iframe, then JSONP script inside it.
        inner = (
            "<!doctype html><meta charset=\"utf-8\"><script>(function(){"
            "const cb=" + json.dumps(self.callback) + ",tag=" + json.dumps(self.tag) + ";"
            "window[cb]=function(d){parent.postMessage({tag:tag,payload:d},\"*\")};"
            "const s=document.createElement(\"script\");"
            "s.src=" + json.dumps(src) + ";"
            "s.onerror=function(){parent.postMessage({tag:tag,error:\"script load failed\"},\"*\")};"
            "document.head.appendChild(s)"
            "})();<\\/script>"
        )

        html = f"""<!doctype html>
<meta charset="utf-8">
<title>MNLT Bridge</title>
<body></body>
<script>
window.__mnltResult = null;
(function(){{
  const tag={json.dumps(self.tag)};
  const frame=document.createElement('iframe');
  frame.style.display='none';
  frame.setAttribute('sandbox','allow-scripts');
  frame.setAttribute('credentialless','');
  try{{frame.credentialless=true}}catch(e){{}}
  window.addEventListener('message',function(ev){{
    if(ev.source!==frame.contentWindow||!ev.data||ev.data.tag!==tag)return;
    if(ev.data.error)window.__mnltResult={{error:String(ev.data.error)}};
    else window.__mnltResult={{payload:ev.data.payload}};
  }});
  frame.srcdoc={json.dumps(inner)};
  document.body.appendChild(frame);
}})();
</script>"""
        self.page.setHtml(html, QUrl("https://mnlt-desktop.local/"))
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
