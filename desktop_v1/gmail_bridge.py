"""Clean Gmail / SnapPages registration bridge for MNLT Derby Manager Desktop v1.

Desktop v1 intentionally uses one transport only:
    requests GET -> Apps Script /exec -> plain JSON

The working browser v42 uses JSONP because browsers need a script callback. Desktop
Python does not. The Apps Script bridge already returns plain JSON whenever the
callback query parameter is omitted, so Desktop v1 avoids JSONP completely.

Bridge credentials are stored locally beside the Desktop data and are never written
into Derby portable backups or GitHub.
"""

from __future__ import annotations

import copy
import json
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

CONFIG_NAME = "bridge_config.json"
CHECK_INTERVAL_MS = 60 * 60 * 1000
BRIDGE_TIMEOUT_SECONDS = 25
RUNTIME_QUERY_NAMES = {
    "authuser",
    "key",
    "callback",
    "_",
    "action",
    "messageid",
    "division",
    "tradcar",
    "modcar",
}


class BridgeError(RuntimeError):
    """Safe bridge failure message. Never includes credentials or registration data."""


def normalize_url(value: str) -> str:
    """Return a clean Apps Script /exec endpoint.

    v42 removes Google's browser-only authuser routing before using the bridge.
    Desktop also removes stale runtime bridge parameters so key/callback/action
    values cannot be duplicated or encoded twice.
    """

    value = str(value or "").strip()
    if not re.match(r"^https://script\.google\.com/macros/s/", value, re.I):
        return ""

    parts = urllib.parse.urlsplit(value)
    if not re.search(r"/exec$", parts.path, re.I):
        return ""

    query = []
    for name, item in urllib.parse.parse_qsl(parts.query, keep_blank_values=True):
        if name.casefold() in RUNTIME_QUERY_NAMES:
            continue
        query.append((name, item))

    return urllib.parse.urlunsplit(
        (
            "https",
            parts.netloc,
            parts.path,
            urllib.parse.urlencode(query, doseq=True),
            "",
        )
    )


def _config_path(store) -> Path:
    return Path(store.data_dir) / CONFIG_NAME


def load_config(store) -> dict[str, Any]:
    path = _config_path(store)
    if not path.is_file():
        return {"url": "", "key": "", "ignored": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"url": "", "key": "", "ignored": []}

    return {
        "url": str(data.get("url", "")),
        "key": str(data.get("key", "")),
        "ignored": [str(x) for x in (data.get("ignored") or [])][-500:],
    }


def save_config(store, data: dict[str, Any]) -> None:
    path = _config_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "url": str(data.get("url", "")),
        "key": str(data.get("key", "")),
        "ignored": list(
            dict.fromkeys(str(x) for x in (data.get("ignored") or []))
        )[-500:],
    }

    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def load_bridge_connection_file(path: str | Path) -> dict[str, str]:
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict) or data.get("type") != "mnlt-derby-bridge":
        raise ValueError("That is not an MNLT Derby connection file.")

    url = normalize_url(str(data.get("url", "")))
    key = str(data.get("key", ""))

    if not url:
        raise ValueError(
            "The connection file does not contain a valid Apps Script Web App URL."
        )
    if not key:
        raise ValueError("The connection file does not contain a Bridge Key.")

    return {"url": url, "key": key}


def _response_classification(response: requests.Response) -> str:
    body = response.text or ""
    stripped = body.lstrip()
    content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip()

    if not stripped:
        kind = "empty"
    elif stripped.startswith("{") or stripped.startswith("["):
        kind = "json"
    elif stripped.startswith("<"):
        kind = "html"
    elif re.match(r"^[A-Za-z_$][\w$\.]*\s*\(", stripped):
        kind = "jsonp"
    else:
        kind = "text"

    return (
        f"HTTP {response.status_code} • "
        f"{content_type or 'unknown content type'} • "
        f"{len(response.content)} bytes • {kind}"
    )


def bridge_request(
    url: str,
    key: str,
    params: dict[str, Any] | None = None,
    timeout: int = BRIDGE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Call Apps Script and return its plain JSON payload.

    Desktop intentionally does NOT send callback. The Apps Script doGet() in
    MNLT_Registration_Bridge.gs returns application/json when callback is absent.
    """

    clean_url = normalize_url(url)
    if not clean_url:
        raise BridgeError("Apps Script Web App URL is invalid.")

    key = str(key if key is not None else "")
    if key == "":
        raise BridgeError("Bridge Key is required.")

    query: dict[str, str] = {
        "key": key,
        "_": str(int(time.time() * 1000)),
    }
    for name, value in (params or {}).items():
        query[str(name)] = "" if value is None else str(value)

    session = requests.Session()
    session.cookies.clear()

    try:
        response = session.get(
            clean_url,
            params=query,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "MNLT-Derby-Manager-Desktop-v1",
                "Accept": "application/json,text/plain;q=0.9,*/*;q=0.5",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
    except requests.RequestException as exc:
        raise BridgeError(
            f"Could not reach Apps Script ({exc.__class__.__name__})."
        ) from exc

    diagnostic = _response_classification(response)
    body = response.text or ""
    low = body.casefold()

    if "accounts.google.com" in low or ("sign in" in low and "google" in low):
        raise BridgeError(
            "Google returned a sign-in page. "
            f"{diagnostic}. The Web App deployment must allow Anyone access."
        )

    if response.status_code != 200:
        raise BridgeError(f"Apps Script request failed. {diagnostic}.")

    try:
        data = response.json()
    except ValueError as exc:
        raise BridgeError(
            "Apps Script did not return plain JSON. "
            f"{diagnostic}. Desktop v1 uses the JSON endpoint only."
        ) from exc

    if not isinstance(data, dict):
        raise BridgeError(f"Apps Script returned an invalid JSON payload. {diagnostic}.")

    return data


def _division(value: str) -> str:
    value = str(value or "").strip()
    if value in {"Traditional", "Modified", "Both"}:
        return value

    low = value.casefold()
    if "both" in low:
        return "Both"
    if "modified" in low:
        return "Modified"
    return "Traditional"


def filter_new_signups(
    state: dict[str, Any],
    rows: list[dict[str, Any]],
    ignored: list[str],
) -> list[dict[str, Any]]:
    known_ids = {str(x) for x in ignored}
    existing_names: set[str] = set()

    for reg in state.get("registrations", []):
        existing_names.add(str(reg.get("name", "")).strip().casefold())
        for field in ("sourceMessageId", "gmailMessageId"):
            if reg.get(field):
                known_ids.add(str(reg[field]))

    out: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue

        message_id = str(row.get("messageId", "")).strip()
        name = str(row.get("name", "")).strip()

        if not message_id or not name:
            continue
        if message_id in known_ids:
            continue
        if name.casefold() in existing_names:
            continue

        out.append(copy.deepcopy(row))

    out.sort(key=lambda item: str(item.get("receivedAt", "")))
    return out


class EmailRegistrationPage(QWidget):
    def __init__(self, manager) -> None:
        super().__init__()
        self.manager = manager
        self.incoming: list[dict[str, Any]] = []
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mnlt-mail")
        self._future = None
        self._future_kind = ""
        self._draft_context = None

        layout = QVBoxLayout(self)

        title = QLabel("Email Registration")
        font = title.font()
        font.setPointSize(22)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        layout.addWidget(
            QLabel("Pull new SnapPages derby signups from the Gmail Apps Script bridge.")
        )

        setup = QGroupBox("Gmail Registration Bridge")
        setup_layout = QVBoxLayout(setup)

        self.url = QLineEdit()
        self.url.setPlaceholderText("https://script.google.com/macros/s/.../exec")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("Bridge Key")

        setup_layout.addWidget(QLabel("Apps Script Web App URL"))
        setup_layout.addWidget(self.url)
        setup_layout.addWidget(QLabel("Bridge Key"))
        setup_layout.addWidget(self.key)

        buttons = QHBoxLayout()
        self.import_btn = QPushButton("IMPORT V42 CONNECTION FILE")
        self.save_btn = QPushButton("SAVE CONNECTION")
        self.save_btn.setObjectName("primary")
        self.check_btn = QPushButton("CHECK NOW")
        self.disconnect_btn = QPushButton("DISCONNECT")

        buttons.addWidget(self.import_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.check_btn)
        buttons.addWidget(self.disconnect_btn)
        buttons.addStretch()

        setup_layout.addLayout(buttons)

        self.status = QLabel("Not set up")
        self.status.setWordWrap(True)
        setup_layout.addWidget(self.status)
        layout.addWidget(setup)

        list_box = QGroupBox("New Registrations Waiting")
        list_layout = QVBoxLayout(list_box)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Racer", "Contact", "Requested Entry", "Received"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        list_layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.review_btn = QPushButton("REVIEW SELECTED")
        self.review_btn.setObjectName("primary")
        self.ignore_btn = QPushButton("IGNORE SELECTED")
        actions.addWidget(self.review_btn)
        actions.addWidget(self.ignore_btn)
        actions.addStretch()
        list_layout.addLayout(actions)

        layout.addWidget(list_box, 1)

        self.import_btn.clicked.connect(self.import_connection_file)
        self.save_btn.clicked.connect(self.save_connection)
        self.check_btn.clicked.connect(lambda: self.check_now(True))
        self.disconnect_btn.clicked.connect(self.disconnect)
        self.review_btn.clicked.connect(self.review_selected)
        self.ignore_btn.clicked.connect(self.ignore_selected)
        self.table.cellDoubleClicked.connect(lambda *_: self.review_selected())

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(100)
        self.poll_timer.timeout.connect(self._poll_future)

        self.auto_timer = QTimer(self)
        self.auto_timer.setInterval(CHECK_INTERVAL_MS)
        self.auto_timer.timeout.connect(lambda: self.check_now(False))

        self.load_connection()
        if self.connection_ready():
            self.auto_timer.start()
            QTimer.singleShot(1200, lambda: self.check_now(False))

    def connection_ready(self) -> bool:
        return bool(normalize_url(self.url.text()) and self.key.text() != "")

    def load_connection(self) -> None:
        cfg = load_config(self.manager.store)
        self.url.setText(cfg.get("url", ""))
        self.key.setText(cfg.get("key", ""))
        self.status.setText("Ready" if self.connection_ready() else "Not set up")

    def import_connection_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import v42 Gmail Connection",
            "",
            "MNLT Derby Connection (*.mnltbridge *.json);;JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return

        try:
            imported = load_bridge_connection_file(path)
        except Exception as exc:
            QMessageBox.warning(self, "Gmail Bridge", str(exc))
            return

        cfg = load_config(self.manager.store)
        cfg.update(imported)
        save_config(self.manager.store, cfg)

        self.url.setText(imported["url"])
        self.key.setText(imported["key"])
        self.status.setText("v42 connection imported. Checking…")
        self.auto_timer.start()
        self.check_now(True)

    def save_connection(self) -> None:
        url = normalize_url(self.url.text())
        key = self.key.text()

        if not url:
            QMessageBox.warning(
                self,
                "Gmail Bridge",
                "Paste the Apps Script Web App URL ending in /exec.",
            )
            return
        if key == "":
            QMessageBox.warning(self, "Gmail Bridge", "Paste the Bridge Key.")
            return

        cfg = load_config(self.manager.store)
        cfg.update({"url": url, "key": key})
        save_config(self.manager.store, cfg)

        self.url.setText(url)
        self.status.setText("Connection saved. Checking…")
        self.auto_timer.start()
        self.check_now(True)

    def disconnect(self) -> None:
        cfg = load_config(self.manager.store)
        cfg["url"] = ""
        cfg["key"] = ""
        save_config(self.manager.store, cfg)

        self.url.clear()
        self.key.clear()
        self.incoming = []
        self.refresh_table()
        self.auto_timer.stop()
        self.status.setText("Disconnected")

    def check_now(self, manual: bool = True) -> None:
        if self._future is not None:
            return

        cfg = load_config(self.manager.store)
        url = normalize_url(cfg.get("url", "") or self.url.text())
        key = str(cfg.get("key", "") or self.key.text())

        if not url or key == "":
            if manual:
                QMessageBox.information(
                    self,
                    "Gmail Bridge",
                    "Save or import the Apps Script connection first.",
                )
            return

        self.status.setText("Checking for new registrations…")
        self.check_btn.setEnabled(False)
        self._start_request("check", {}, None)

    def _start_request(
        self,
        kind: str,
        params: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> None:
        if self._future is not None:
            return

        cfg = load_config(self.manager.store)
        url = normalize_url(cfg.get("url", "") or self.url.text())
        key = str(cfg.get("key", "") or self.key.text())

        if not url or key == "":
            self.check_btn.setEnabled(True)
            self.status.setText("Not set up")
            return

        self._future_kind = kind
        self._draft_context = copy.deepcopy(context) if context else None
        self._future = self._executor.submit(bridge_request, url, key, params)
        self.poll_timer.start()

    def _poll_future(self) -> None:
        if self._future is None or not self._future.done():
            return

        future = self._future
        kind = self._future_kind
        context = self._draft_context

        self._future = None
        self._future_kind = ""
        self._draft_context = None
        self.poll_timer.stop()
        self.check_btn.setEnabled(True)

        try:
            data = future.result()
        except Exception as exc:
            if kind == "check":
                self.status.setText(f"Connection problem — {exc}")
            else:
                QMessageBox.warning(
                    self,
                    "Gmail Draft",
                    "Racer was saved, but the Gmail draft could not be created.\n\n"
                    + str(exc),
                )
            return

        if kind == "check":
            self._finish_check(data)
        elif kind == "draft":
            self._finish_draft(data, context)

    def _finish_check(self, data: dict[str, Any]) -> None:
        if data.get("ok") is not True:
            detail = str(data.get("error") or "the bridge did not approve the request")
            self.status.setText(f"Connection problem — {detail}.")
            return

        cfg = load_config(self.manager.store)
        rows = data.get("registrations")
        self.incoming = filter_new_signups(
            self.manager.state,
            rows if isinstance(rows, list) else [],
            cfg.get("ignored", []),
        )
        self.status.setText(
            f"Connected • {len(self.incoming)} new registration"
            + ("" if len(self.incoming) == 1 else "s")
            + " waiting"
        )
        self.refresh_table()

    def _finish_draft(
        self,
        data: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> None:
        if data.get("ok") is True and data.get("draftCreated") is True:
            missing = (
                data.get("missingAttachments")
                if isinstance(data.get("missingAttachments"), list)
                else []
            )
            if missing:
                QMessageBox.information(
                    self,
                    "Gmail Draft Created",
                    "Racer saved and Gmail confirmation draft created.\n\n"
                    "One or more rule PDF attachments need attention.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Gmail Draft Created",
                    "Racer saved and Gmail confirmation draft created.",
                )
        elif data.get("ok") is True:
            QMessageBox.information(
                self,
                "Gmail Draft",
                "Racer saved. The connected Apps Script bridge does not have "
                "Gmail draft creation enabled yet.",
            )
        else:
            detail = str(data.get("error") or "the bridge did not create the draft")
            QMessageBox.warning(
                self,
                "Gmail Draft",
                f"Racer was saved, but the Gmail draft could not be created.\n\n{detail}",
            )

        if context:
            self.mark_imported(str(context.get("messageId", "")))

    def refresh_from_state(self) -> None:
        cfg = load_config(self.manager.store)
        self.incoming = filter_new_signups(
            self.manager.state,
            self.incoming,
            cfg.get("ignored", []),
        )
        self.refresh_table()

    def refresh_table(self) -> None:
        self.table.setRowCount(len(self.incoming))

        for row_index, row in enumerate(self.incoming):
            contact = str(row.get("email") or row.get("phone") or "")
            values = [
                str(row.get("name", "")),
                contact,
                str(row.get("choice") or row.get("division") or ""),
                str(row.get("receivedAt", "")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, row_index)
                self.table.setItem(row_index, col, item)

    def _selected_signup(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.incoming):
            return None
        return self.incoming[row]

    def review_selected(self) -> None:
        signup = self._selected_signup()
        if not signup:
            QMessageBox.information(
                self, "Email Registration", "Select a registration first."
            )
            return

        name = str(signup.get("name", "")).strip()
        if any(
            str(reg.get("name", "")).strip().casefold() == name.casefold()
            for reg in self.manager.state.get("registrations", [])
        ):
            QMessageBox.information(
                self,
                "Already Registered",
                f"{name} is already in Registration.",
            )
            self.mark_imported(str(signup.get("messageId", "")))
            return

        page = self.manager.registration
        page.clear()
        page.name.setText(name)
        page.age.setValue(0)
        page.contact.setText(
            " | ".join(
                item
                for item in [
                    str(signup.get("email", "")).strip(),
                    str(signup.get("phone", "")).strip(),
                ]
                if item
            )
        )
        page.division.setCurrentText(
            _division(signup.get("division") or signup.get("choice"))
        )
        page.trad_car.clear()
        page.mod_car.clear()
        page.status.setCurrentText("Registered")
        page.rules.setChecked(False)
        page.notes.setPlainText("Imported from SnapPages registration email")

        if hasattr(page, "set_bridge_pending"):
            page.set_bridge_pending(copy.deepcopy(signup))

        self.manager.open_page(page)

    def ignore_selected(self) -> None:
        signup = self._selected_signup()
        if not signup:
            QMessageBox.information(
                self, "Email Registration", "Select a registration first."
            )
            return

        message_id = str(signup.get("messageId", ""))
        cfg = load_config(self.manager.store)
        cfg.setdefault("ignored", []).append(message_id)
        save_config(self.manager.store, cfg)

        self.incoming = [
            item
            for item in self.incoming
            if str(item.get("messageId", "")) != message_id
        ]
        self.refresh_table()
        self.status.setText("Registration ignored.")

    def mark_imported(self, message_id: str) -> None:
        if not message_id:
            return

        self.incoming = [
            item
            for item in self.incoming
            if str(item.get("messageId", "")) != str(message_id)
        ]
        self.refresh_table()

    def create_draft_for(
        self,
        pending: dict[str, Any],
        saved: dict[str, Any],
    ) -> None:
        if self._future is not None:
            QMessageBox.information(
                self,
                "Gmail Draft",
                "Racer saved. The bridge is busy right now, so create the Gmail "
                "draft after the current check finishes.",
            )
            return

        params = {
            "action": "createDraft",
            "messageId": pending.get("messageId", ""),
            "division": saved.get("division")
            or pending.get("division")
            or "Traditional",
            "tradCar": saved.get("tradCar", ""),
            "modCar": saved.get("modCar", ""),
        }

        self.status.setText("Creating Gmail confirmation draft…")
        self._start_request("draft", params, pending)


def install(desktop_app) -> None:
    """Install Email Registration and its Registration review integration."""

    if getattr(desktop_app, "_gmail_bridge_v1_installed", False):
        return
    desktop_app._gmail_bridge_v1_installed = True

    base_reg_init = desktop_app.RegistrationPage.__init__
    base_reg_clear = desktop_app.RegistrationPage.clear
    base_reg_save = desktop_app.RegistrationPage.save

    def reg_init(self, manager):
        base_reg_init(self, manager)

        self._bridge_pending = None
        self._bridge_notice = QLabel("")
        self._bridge_notice.setWordWrap(True)
        self._bridge_notice.setStyleSheet("color:#f2ca69;font-weight:bold;")
        self._bridge_notice.hide()

        self._bridge_draft = QCheckBox(
            "Create Gmail confirmation draft after saving"
        )
        self._bridge_draft.setChecked(True)
        self._bridge_draft.hide()

        form_box = next(
            (
                widget
                for widget in self.findChildren(QGroupBox)
                if widget.title() == "Add / Edit Registration"
            ),
            None,
        )
        form = form_box.layout() if form_box else None
        if form is not None:
            insert_at = max(0, form.rowCount() - 1)
            form.insertRow(insert_at, self._bridge_notice)
            form.insertRow(insert_at + 1, "", self._bridge_draft)

        self._bridge_save_button = next(
            (
                widget
                for widget in self.findChildren(QPushButton)
                if widget.text() == "SAVE RACER"
            ),
            None,
        )

    def clear_pending_ui(self):
        self._bridge_pending = None

        if hasattr(self, "_bridge_notice"):
            self._bridge_notice.clear()
            self._bridge_notice.hide()

        if hasattr(self, "_bridge_draft"):
            self._bridge_draft.hide()
            self._bridge_draft.setChecked(True)

        if getattr(self, "_bridge_save_button", None):
            self._bridge_save_button.setText("SAVE RACER")

    def set_bridge_pending(self, signup: dict[str, Any]) -> None:
        self._bridge_pending = copy.deepcopy(signup)

        if hasattr(self, "_bridge_notice"):
            self._bridge_notice.setText(
                "REVIEW EMAIL REGISTRATION — check the fields, add the car name "
                "if available, then save."
            )
            self._bridge_notice.show()

        if hasattr(self, "_bridge_draft"):
            self._bridge_draft.show()
            self._bridge_draft.setChecked(True)

        if getattr(self, "_bridge_save_button", None):
            self._bridge_save_button.setText(
                "SAVE RACER + CREATE EMAIL DRAFT"
            )

    def reg_clear(self):
        base_reg_clear(self)
        clear_pending_ui(self)

    def reg_save(self):
        pending = copy.deepcopy(getattr(self, "_bridge_pending", None))
        want_draft = bool(
            getattr(self, "_bridge_draft", None)
            and self._bridge_draft.isChecked()
        )

        before_ids = {
            reg.get("id") for reg in self.manager.state.get("registrations", [])
        }
        wanted_name = self.name.text().strip().casefold()

        base_reg_save(self)

        if not pending:
            return

        saved = next(
            (
                reg
                for reg in self.manager.state.get("registrations", [])
                if reg.get("id") not in before_ids
                and str(reg.get("name", "")).strip().casefold() == wanted_name
            ),
            None,
        )
        if not saved:
            return

        saved["sourceMessageId"] = str(pending.get("messageId", ""))
        saved["email"] = str(pending.get("email", "")).strip()
        saved["phone"] = str(pending.get("phone", "")).strip()

        if not saved.get("notes"):
            saved["notes"] = "Imported from SnapPages registration email"

        self.manager.save("email-registration-import")

        email_page = getattr(self.manager, "email_registration", None)
        if email_page:
            email_page.mark_imported(str(pending.get("messageId", "")))
            if want_draft:
                email_page.create_draft_for(pending, saved)

    desktop_app.RegistrationPage.__init__ = reg_init
    desktop_app.RegistrationPage.clear = reg_clear
    desktop_app.RegistrationPage.save = reg_save
    desktop_app.RegistrationPage.set_bridge_pending = set_bridge_pending

    base_main_init = desktop_app.MainWindow.__init__
    base_refresh_all = desktop_app.MainWindow.refresh_all

    def main_init(self):
        base_main_init(self)

        self.email_registration = EmailRegistrationPage(self)
        self.stack.insertWidget(2, self.email_registration)

        outer = self.centralWidget().layout()
        body = outer.itemAt(1).layout() if outer and outer.count() > 1 else None
        nav = body.itemAt(0).layout() if body and body.count() else None

        if nav is not None:
            button = QPushButton("Email Registration")
            button.setMinimumHeight(48)
            button.clicked.connect(
                lambda: self.open_page(self.email_registration)
            )
            nav.insertWidget(2, button)

    def refresh_all(self):
        base_refresh_all(self)
        if hasattr(self, "email_registration"):
            self.email_registration.refresh_from_state()

    desktop_app.MainWindow.__init__ = main_init
    desktop_app.MainWindow.refresh_all = refresh_all
