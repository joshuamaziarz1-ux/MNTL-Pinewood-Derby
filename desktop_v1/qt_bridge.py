"""Apps Script transport for MNLT Derby Manager Desktop v1.

This transport uses Qt's own network stack with a fresh, cookie-free request.
It does not depend on Chrome/Edge, browser storage, CORS, injected scripts, or
Qt WebEngine rendering. Apps Script redirects are followed automatically and
the raw JSON/JSONP response body is parsed directly.
"""

from __future__ import annotations

import html
import json
import random
import re
import time
import urllib.parse
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


def parse_apps_script_document(text: str) -> dict[str, Any]:
    """Parse plain JSON, JSONP, or a small HTML wrapper containing either."""
    raw = str(text or "").lstrip("\ufeff").strip()
    if not raw:
        raise ValueError("Apps Script returned an empty response.")

    # If a server/browser wrapped text in HTML, prefer PRE/body text.
    if raw.startswith("<"):
        pre = re.search(r"<pre[^>]*>(.*?)</pre>", raw, flags=re.I | re.S)
        if pre:
            raw = html.unescape(re.sub(r"<[^>]+>", "", pre.group(1))).strip()
        else:
            body = re.search(r"<body[^>]*>(.*?)</body>", raw, flags=re.I | re.S)
            if body:
                raw = html.unescape(re.sub(r"<[^>]+>", "", body.group(1))).strip()

    # Plain JSON.
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    cleaned = re.sub(r"^\s*/\*.*?\*/\s*", "", raw, flags=re.S)

    # Standard JSONP.
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

    # Wrapper/XSSI variants. Decode the first JSON object present.
    start = cleaned.find("{")
    if start >= 0:
        try:
            data, _end = json.JSONDecoder().raw_decode(cleaned[start:])
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    raise ValueError("Apps Script returned a response format Desktop v1 did not recognize.")


class CredentiallessAppsScriptRequest(QObject):
    """One cookie-free Apps Script request using Qt Network."""

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
        self.manager = QNetworkAccessManager(self)
        self.reply: QNetworkReply | None = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
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
        request_url = self.url + sep + urllib.parse.urlencode(query)

        request = QNetworkRequest(QUrl(request_url))
        request.setRawHeader(b"User-Agent", b"Mozilla/5.0 MNLT-Derby-Manager-Desktop-v1")
        request.setRawHeader(b"Accept", b"application/json,text/javascript,text/plain,*/*")
        request.setRawHeader(b"Cache-Control", b"no-cache")
        request.setRawHeader(b"Pragma", b"no-cache")
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.NoLessSafeRedirectPolicy,
        )

        self.reply = self.manager.get(request)
        self.reply.finished.connect(self._reply_finished)
        self.timer.start(self.timeout_ms)

    def _reply_finished(self) -> None:
        if self.done or self.reply is None:
            return

        reply = self.reply
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        final_url = reply.url().toString()
        error_code = reply.error()
        raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
        reply.deleteLater()
        self.reply = None

        if error_code != QNetworkReply.NoError and not raw:
            self._finish(None, f"Network error: {reply.errorString()}")
            return

        low = raw.casefold()
        if "accounts.google.com" in low or ("sign in" in low and "google" in low):
            self._finish(
                None,
                "Google returned a sign-in page. The Apps Script deployment must be accessible to Anyone.",
            )
            return

        if status and int(status) >= 400:
            snippet = re.sub(r"\s+", " ", raw)[:180]
            self._finish(None, f"Apps Script returned HTTP {int(status)}. {snippet}".strip())
            return

        try:
            payload = parse_apps_script_document(raw)
        except Exception as exc:
            snippet = re.sub(r"\s+", " ", raw)[:220]
            where = urllib.parse.urlsplit(final_url).netloc or "Google"
            self._finish(
                None,
                f"{exc} Final host: {where}. Response began: {snippet or '[empty]'}",
            )
            return

        self._finish(payload, None)

    def _timeout(self) -> None:
        if self.done:
            return
        if self.reply is not None:
            try:
                self.reply.abort()
            except Exception:
                pass
        self._finish(None, "The Apps Script request timed out.")

    def _finish(self, payload: Any, error: str | None) -> None:
        if self.done:
            return
        self.done = True
        self.timer.stop()
        self.finished.emit(payload, error)
