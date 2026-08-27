"""Apps Script transport for MNLT Derby Manager Desktop v1.

The browser bridge was proven with Apps Script JSONP. Desktop v1 now navigates
its isolated Qt WebEngine page directly to the Apps Script URL and reads the
returned document text. That removes local-page/CORS/script-tag restrictions
entirely while still keeping the request separate from Chrome/Edge cookies.
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.parse
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings


def parse_apps_script_document(text: str) -> dict[str, Any]:
    """Parse JSON/JSONP as rendered by a direct Apps Script navigation."""
    raw = str(text or "").lstrip("\ufeff").strip()
    if not raw:
        raise ValueError("Apps Script returned an empty page.")

    # Plain JSON.
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Common JSONP wrapper.
    cleaned = re.sub(r"^\s*/\*.*?\*/\s*", "", raw, flags=re.S)
    match = re.match(
        r"^[A-Za-z_$][\w$]*\s*\((.*)\)\s*;?\s*$",
        cleaned,
        flags=re.S,
    )
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # Wrapper variants / XSSI prefixes. Decode the first JSON object found.
    start = cleaned.find("{")
    if start >= 0:
        try:
            data, _end = json.JSONDecoder().raw_decode(cleaned[start:])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    raise ValueError("Apps Script returned a page Desktop v1 could not parse.")


class CredentiallessAppsScriptRequest(QObject):
    finished = Signal(object, object)  # payload, error string/None

    def __init__(
        self,
        url: str,
        key: str,
        params: dict[str, Any] | None = None,
        parent: QObject | None = None,
        timeout_ms: int = 25000,
    ) -> None:
        super().__init__(parent)
        self.url = str(url or "")
        self.key = str(key or "")
        self.params = dict(params or {})
        self.timeout_ms = int(timeout_ms)
        self.callback = f"__mnltBridge_{int(time.time() * 1000)}_{random.randint(100000, 999999)}"
        self.page = QWebEnginePage(self)
        settings = self.page.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.page.loadFinished.connect(self._load_finished)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.done = False
        self._read_started = False
        self.request_url = ""

    def start(self) -> None:
        query = {
            "key": self.key,
            "callback": self.callback,
            "_": int(time.time() * 1000),
        }
        for k, v in self.params.items():
            query[str(k)] = "" if v is None else str(v)
        sep = "&" if "?" in self.url else "?"
        self.request_url = self.url + sep + urllib.parse.urlencode(query)

        # Important: navigate directly to Apps Script. No setHtml(), iframe,
        # cross-origin fetch, or injected remote script is involved.
        self.timer.start(self.timeout_ms)
        self.page.load(QUrl(self.request_url))

    def _load_finished(self, ok: bool) -> None:
        if self.done or self._read_started:
            return
        self._read_started = True

        # Even when Chromium reports a navigation failure, Google may still
        # have rendered an explanatory response. Read the page either way.
        QTimer.singleShot(150, self._read_document)

    def _read_document(self) -> None:
        if self.done:
            return
        script = """
(() => {
  const body = document.body;
  const root = document.documentElement;
  const text = body ? body.innerText : (root ? root.innerText : "");
  const html = root ? root.outerHTML : "";
  return {
    text: String(text || ""),
    html: String(html || ""),
    url: String(location.href || ""),
    title: String(document.title || "")
  };
})()
"""
        self.page.runJavaScript(script, self._document_result)

    def _document_result(self, value: Any) -> None:
        if self.done:
            return
        if not isinstance(value, dict):
            self._finish(None, "Qt could not read the Apps Script response page.")
            return

        text = str(value.get("text", "") or "").strip()
        html = str(value.get("html", "") or "")
        title = str(value.get("title", "") or "")
        low = (text + "\n" + html + "\n" + title).casefold()

        if "accounts.google.com" in low or ("sign in" in low and "google" in low):
            self._finish(
                None,
                "Google returned a sign-in page. The Apps Script deployment must be accessible to Anyone.",
            )
            return

        if "authorization required" in low or "access denied" in low:
            self._finish(None, "Google blocked the Apps Script web app authorization.")
            return

        # Chromium can wrap plain-text/script responses inside a PRE element;
        # innerText gives us the original JSON/JSONP in that case.
        candidate = text
        if not candidate and html:
            pre = re.search(r"<pre[^>]*>(.*?)</pre>", html, flags=re.I | re.S)
            if pre:
                candidate = re.sub(r"<[^>]+>", "", pre.group(1))

        try:
            payload = parse_apps_script_document(candidate)
        except Exception as exc:
            snippet = re.sub(r"\s+", " ", candidate)[:180]
            if snippet:
                self._finish(None, f"{exc} Response began: {snippet}")
            else:
                self._finish(None, f"{exc} Google returned no readable response text.")
            return

        self._finish(payload, None)

    def _timeout(self) -> None:
        if self.done:
            return
        # One last attempt to read whatever Chromium has before reporting a
        # timeout. This catches slow Google redirects that never fire a clean
        # loadFinished signal.
        self._read_started = True
        self._read_document()
        QTimer.singleShot(1200, self._final_timeout)

    def _final_timeout(self) -> None:
        if not self.done:
            self._finish(None, "The Apps Script bridge timed out after direct navigation.")

    def _finish(self, payload: Any, error: str | None) -> None:
        if self.done:
            return
        self.done = True
        self.timer.stop()
        try:
            self.page.loadFinished.disconnect(self._load_finished)
        except Exception:
            pass
        self.finished.emit(payload, error)
        self.page.deleteLater()
