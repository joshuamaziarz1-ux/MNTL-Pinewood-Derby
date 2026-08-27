"""Gmail / SnapPages registration bridge for MNLT Derby Manager Desktop v1.

The bridge talks to the existing Google Apps Script Web App. The URL and bridge
key are stored in a small local config file beside the desktop data, not inside
portable Derby backups.
"""

from __future__ import annotations

import copy
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
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


def normalize_url(value: str) -> str:
    value = str(value or "").strip()
    if not re.match(r"^https://script\.google\.com/macros/s/", value, re.I):
        return ""
    if not re.search(r"/exec(?:[?#]|$)", value, re.I):
        return ""
    return value.split("#", 1)[0]


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
        "ignored": list(dict.fromkeys(str(x) for x in (data.get("ignored") or [])))[-500:],
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def parse_bridge_payload(text: str, callback: str = "mnltDesktopCallback") -> dict[str, Any]:
    text = str(text or "").lstrip("\ufeff").strip()
    if not text:
        raise ValueError("The registration bridge returned an empty response.")
    if text.startswith("{") or text.startswith("["):
        data = json.loads(text)
    else:
        match = re.match(r"^[A-Za-z_$][\w$]*\s*\((.*)\)\s*;?\s*$", text, re.S)
        if not match:
            raise ValueError("The registration bridge returned an unreadable response.")
        data = json.loads(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("The registration bridge response was not an object.")
    return data


def bridge_request(url: str, key: str, params: dict[str, Any] | None = None, timeout: int = 18) -> dict[str, Any]:
    """Call the public Apps Script bridge without Google-account cookies.

    The browser build only became reliable once the request was made
    credentialless. A fresh requests.Session gives the desktop app the same
    anonymous behavior while still following Apps Script redirects.
    """
    url = normalize_url(url)
    if not url:
        raise ValueError("Apps Script Web App URL is invalid.")
    if not str(key or "").strip():
        raise ValueError("Bridge Key is required.")
    callback = "__mnltBridge_desktop"
    query: dict[str, Any] = {
        "key": str(key).strip(),
        "callback": callback,
        "_": int(time.time() * 1000),
    }
    for k, v in (params or {}).items():
        query[str(k)] = "" if v is None else str(v)

    session = requests.Session()
    session.cookies.clear()
    try:
        response = session.get(
            url,
            params=query,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 MNLT-Derby-Manager-Desktop-v1",
                "Accept": "application/json,text/javascript,text/plain,*/*",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
    except requests.RequestException as exc:
        raise ConnectionError(f"Could not reach Apps Script ({exc.__class__.__name__}).") from exc

    if response.status_code != 200:
        raise ConnectionError(f"Apps Script returned HTTP {response.status_code}.")

    body = response.text.lstrip("\ufeff").strip()
    if not body:
        raise ConnectionError("Apps Script returned an empty response.")
    if body.startswith("<!DOCTYPE html") or body.startswith("<html"):
        low = body.casefold()
        if "sign in" in low or "accounts.google" in low:
            raise ConnectionError(
                "Google returned a sign-in page. The Apps Script deployment must allow Anyone access."
            )
        raise ConnectionError("Google returned an HTML page instead of bridge data.")

    return parse_bridge_payload(body, callback)


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


def filter_new_signups(state: dict[str, Any], rows: list[dict[str, Any]], ignored: list[str]) -> list[dict[str, Any]]:
    known_ids = set(str(x) for x in ignored)
    existing_names = set()
    for reg in state.get("registrations", []):
        existing_names.add(str(reg.get("name", "")).strip().casefold())
        for field in ("sourceMessageId", "gmailMessageId"):
            if reg.get(field):
                known_ids.add(str(reg[field]))
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("messageId", "")).strip()
        name = str(row.get("name", "")).strip()
        if not mid or not name:
            continue
        if mid in known_ids:
            continue
        if name.casefold() in existing_names:
            continue
        out.append(copy.deepcopy(row))
    out.sort(key=lambda x: str(x.get("receivedAt", "")))
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
        f = title.font()
        f.setPointSize(22)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)
        layout.addWidget(QLabel("Pull new SnapPages derby signups from the existing Gmail Apps Script bridge."))

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
        self.save_btn = QPushButton("SAVE CONNECTION")
        self.save_btn.setObjectName("primary")
        self.check_btn = QPushButton("CHECK NOW")
        self.disconnect_btn = QPushButton("DISCONNECT")
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
        self.table.setHorizontalHeaderLabels(["Racer", "Contact", "Requested Entry", "Received"])
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
        return bool(normalize_url(self.url.text()) and self.key.text().strip())

    def load_connection(self) -> None:
        cfg = load_config(self.manager.store)
        self.url.setText(cfg.get("url", ""))
        self.key.setText(cfg.get("key", ""))
        self.status.setText("Ready" if self.connection_ready() else "Not set up")

    def save_connection(self) -> None:
        url = normalize_url(self.url.text())
        key = self.key.text().strip()
        if not url:
            QMessageBox.warning(self, "Gmail Bridge", "Paste the Apps Script Web App URL ending in /exec.")
            return
        if not key:
            QMessageBox.warning(self, "Gmail Bridge", "Paste the Bridge Key.")
            return
        cfg = load_config(self.manager.store)
        cfg.update({"url": url, "key": key})
        save_config(self.manager.store, cfg)
        self.url.setText(url)
        self.status.setText("Connection saved. Checking Gmail registration bridge…")
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
        url = normalize_url(self.url.text())
        key = self.key.text().strip()
        if not url or not key:
            if manual:
                QMessageBox.information(self, "Gmail Bridge", "Save the Apps Script Web App URL and Bridge Key first.")
            return
        self.status.setText("Checking for new registrations…")
        self.check_btn.setEnabled(False)
        self._future_kind = "check"
        self._future = self._executor.submit(bridge_request, url, key, {})
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
                QMessageBox.warning(self, "Gmail Draft", f"Racer was saved, but the Gmail draft could not be created.\n\n{exc}")
            return

        if kind == "check":
            if data.get("ok") is not True:
                detail = str(data.get("error") or "the bridge did not approve the request")
                self.status.setText(f"Connection problem — {detail}.")
                return
            cfg = load_config(self.manager.store)
            self.incoming = filter_new_signups(
                self.manager.state,
                data.get("registrations") if isinstance(data.get("registrations"), list) else [],
                cfg.get("ignored", []),
            )
            self.status.setText(
                f"Connected • {len(self.incoming)} new registration"
                + ("" if len(self.incoming) == 1 else "s")
                + " waiting"
            )
            self.refresh_table()
        elif kind == "draft":
            if data.get("ok") is True and data.get("draftCreated"):
                missing = data.get("missingAttachments") if isinstance(data.get("missingAttachments"), list) else []
                if missing:
                    QMessageBox.information(
                        self,
                        "Gmail Draft Created",
                        "Racer saved and Gmail confirmation draft created.\n\nOne or more rule PDF attachments need attention.",
                    )
                else:
                    QMessageBox.information(self, "Gmail Draft Created", "Racer saved and Gmail confirmation draft created.")
            else:
                QMessageBox.warning(
                    self,
                    "Gmail Draft",
                    "Racer was saved, but the Apps Script bridge did not create a draft. The bridge may still need the draft-capable server update.",
                )
            if context:
                self.mark_imported(str(context.get("messageId", "")))

    def refresh_from_state(self) -> None:
        cfg = load_config(self.manager.store)
        self.incoming = filter_new_signups(self.manager.state, self.incoming, cfg.get("ignored", []))
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
            QMessageBox.information(self, "Email Registration", "Select a registration first.")
            return
        name = str(signup.get("name", "")).strip()
        if any(str(r.get("name", "")).strip().casefold() == name.casefold() for r in self.manager.state.get("registrations", [])):
            QMessageBox.information(self, "Already Registered", f"{name} is already in Registration.")
            self.mark_imported(str(signup.get("messageId", "")))
            return

        page = self.manager.registration
        page.clear()
        page.name.setText(name)
        page.age.setValue(0)
        page.contact.setText(" | ".join(x for x in [str(signup.get("email", "")).strip(), str(signup.get("phone", "")).strip()] if x))
        page.division.setCurrentText(_division(signup.get("division") or signup.get("choice")))
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
            QMessageBox.information(self, "Email Registration", "Select a registration first.")
            return
        mid = str(signup.get("messageId", ""))
        cfg = load_config(self.manager.store)
        cfg.setdefault("ignored", []).append(mid)
        save_config(self.manager.store, cfg)
        self.incoming = [x for x in self.incoming if str(x.get("messageId", "")) != mid]
        self.refresh_table()
        self.status.setText("Registration ignored.")

    def mark_imported(self, message_id: str) -> None:
        if not message_id:
            return
        self.incoming = [x for x in self.incoming if str(x.get("messageId", "")) != str(message_id)]
        self.refresh_table()

    def create_draft_for(self, pending: dict[str, Any], saved: dict[str, Any]) -> None:
        if self._future is not None:
            QMessageBox.information(
                self,
                "Gmail Draft",
                "Racer saved. The bridge is busy right now, so create the Gmail draft after the current email check finishes.",
            )
            return
        cfg = load_config(self.manager.store)
        url = normalize_url(cfg.get("url", ""))
        key = str(cfg.get("key", "")).strip()
        if not url or not key:
            QMessageBox.information(
                self,
                "Gmail Draft",
                "Racer saved. Reconnect the Gmail registration bridge to create the confirmation draft.",
            )
            return
        params = {
            "action": "createDraft",
            "messageId": pending.get("messageId", ""),
            "division": saved.get("division") or pending.get("division") or "Traditional",
            "tradCar": saved.get("tradCar", ""),
            "modCar": saved.get("modCar", ""),
        }
        self.status.setText("Creating Gmail confirmation draft…")
        self._future_kind = "draft"
        self._draft_context = copy.deepcopy(pending)
        self._future = self._executor.submit(bridge_request, url, key, params)
        self.poll_timer.start()


def install(desktop_app) -> None:
    """Install the email-registration page and Registration review workflow."""

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
        self._bridge_draft = QCheckBox("Create Gmail confirmation draft after saving")
        self._bridge_draft.setChecked(True)
        self._bridge_draft.hide()

        form_box = next((x for x in self.findChildren(QGroupBox) if x.title() == "Add / Edit Registration"), None)
        form = form_box.layout() if form_box else None
        if form is not None:
            insert_at = max(0, form.rowCount() - 1)
            form.insertRow(insert_at, self._bridge_notice)
            form.insertRow(insert_at + 1, "", self._bridge_draft)

        self._bridge_save_button = next((x for x in self.findChildren(QPushButton) if x.text() == "SAVE RACER"), None)

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
                "REVIEW EMAIL REGISTRATION — check the fields, add the car name if available, then save."
            )
            self._bridge_notice.show()
        if hasattr(self, "_bridge_draft"):
            self._bridge_draft.show()
            self._bridge_draft.setChecked(True)
        if getattr(self, "_bridge_save_button", None):
            self._bridge_save_button.setText("SAVE RACER + CREATE EMAIL DRAFT")

    def reg_clear(self):
        base_reg_clear(self)
        clear_pending_ui(self)

    def reg_save(self):
        pending = copy.deepcopy(getattr(self, "_bridge_pending", None))
        want_draft = bool(getattr(self, "_bridge_draft", None) and self._bridge_draft.isChecked())
        before_ids = {r.get("id") for r in self.manager.state.get("registrations", [])}
        wanted_name = self.name.text().strip().casefold()
        base_reg_save(self)
        if not pending:
            return
        saved = next(
            (
                r
                for r in self.manager.state.get("registrations", [])
                if r.get("id") not in before_ids and str(r.get("name", "")).strip().casefold() == wanted_name
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
            button.clicked.connect(lambda: self.open_page(self.email_registration))
            nav.insertWidget(2, button)

    def refresh_all(self):
        base_refresh_all(self)
        if hasattr(self, "email_registration"):
            self.email_registration.refresh_from_state()

    desktop_app.MainWindow.__init__ = main_init
    desktop_app.MainWindow.refresh_all = refresh_all
