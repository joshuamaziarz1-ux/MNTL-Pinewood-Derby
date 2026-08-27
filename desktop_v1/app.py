"""MNLT Derby Manager Desktop v1.

Pure Python/PySide6 desktop shell. No browser, GitHub Pages, or network is
required for race-day operation.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backup import create_full_backup, restore_full_backup, verify_backup
from race_engine import build_fair_schedule, heat_points, score_blocks, standings, trophy_tie_groups, verify_schedule
from storage import DerbyStore, ensure_state

APP_VERSION = "Desktop v1"

TRAD_ITEMS = [
    "Length 7.0 in maximum",
    "Overall width 2 3/4 in maximum",
    "Underbody clearance at least 3/8 in",
    "Clears finish-line / timer",
    "Main body pine only",
    "Official BSA Grand Prix wheels",
    "Official BSA Grand Prix axles",
    "Wheel modifications polishing / smoothing only",
    "Axle modifications deburring / polishing only",
    "All 4 wheels touch",
    "No bearings, washers, bushings, or springs",
    "Dry lubricant only",
    "Weights securely attached",
    "Gravity powered only",
    "Safe for the track",
]
MOD_SAFETY = [
    "Will not damage the track",
    "No burning, flame, or track-damaging effect",
    "Parts, weights, batteries, and attachments are secure",
]
MOD_COMPAT = [
    "Fits and clears one lane safely",
    "Will not interfere with cars in adjacent lanes",
    "Works safely with the starting gate / approved start method",
    "Clears the finish area / timer safely",
]


def ordinal(n: int) -> str:
    if n == 1:
        return "1st"
    if n == 2:
        return "2nd"
    if n == 3:
        return "3rd"
    return f"{n}th"


def group_key(rows: list[dict[str, Any]]) -> str:
    ids = ",".join(sorted(str(r["id"]) for r in rows))
    points = f"{float(rows[0]['points']):.6f}" if rows else "0"
    return f"{ids}@{points}"


def division_match(reg: dict[str, Any], division: str) -> bool:
    if reg.get("status") == "Withdrawn":
        return False
    entry = reg.get("division", "Traditional")
    return entry == "Both" or entry == division


def race_bucket(state: dict[str, Any], division: str) -> dict[str, Any]:
    if division == "Traditional":
        return state
    return state["modified"]


def race_racers(state: dict[str, Any], division: str) -> list[dict[str, Any]]:
    return state["racers"] if division == "Traditional" else state["modified"]["raceRacers"]


def final_standings(state: dict[str, Any], division: str) -> list[dict[str, Any]]:
    bucket = race_bucket(state, division)
    rows = standings(race_racers(state, division), bucket.get("heats", []))
    tie_breaks = bucket.setdefault("tieBreaks", {})
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and abs(rows[j]["points"] - rows[i]["points"]) < 1e-9:
            j += 1
        if j - i > 1:
            group = rows[i:j]
            saved = tie_breaks.get(group_key(group))
            if saved and isinstance(saved.get("order"), list):
                order = {str(rid): pos for pos, rid in enumerate(saved["order"])}
                if set(order) == {str(r["id"]) for r in group}:
                    rows[i:j] = sorted(group, key=lambda r: order[str(r["id"])])
        i = j
    return rows


class ProjectorWindow(QMainWindow):
    def __init__(self, manager: "MainWindow") -> None:
        super().__init__()
        self.manager = manager
        self.setWindowTitle("MNLT Pinewood Derby - Audience Display")
        self.resize(1500, 900)
        self.mode = "normal"
        self.override_division: str | None = None
        self.override_heat: dict[str, Any] | None = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._after_results)
        self.root = QWidget()
        self.root.setObjectName("projectorRoot")
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.setCentralWidget(self.root)
        self.setStyleSheet(
            "#projectorRoot{background:#07111d;color:white;}"
            "QLabel{color:white;}"
            ".card{background:#101d2d;border:2px solid #29415c;border-radius:16px;}"
        )
        self.render()

    def _clear(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _label(self, text: str, size: int, bold: bool = False, color: str = "white", align=Qt.AlignCenter) -> QLabel:
        label = QLabel(text)
        label.setAlignment(align)
        label.setStyleSheet(f"color:{color};")
        font = QFont("Arial", size)
        font.setBold(bold)
        label.setFont(font)
        return label

    def render_waiting(self, division: str) -> None:
        self._clear()
        self.layout.addStretch()
        self.layout.addWidget(self._label("MNLT PINEWOOD DERBY", 24, True, "#d8a63d"))
        self.layout.addWidget(self._label(f"{division.upper()} DIVISION", 54, True))
        self.layout.addWidget(self._label("Race Starting Soon", 30, True, "#d9e0e7"))
        self.layout.addWidget(self._label("Watch this screen for your car name and lane", 20, False, "#9eb0c2"))
        self.layout.addStretch()

    def _photo(self, registration_id: Any, division: str, car_name: str) -> QLabel:
        box = QLabel(car_name)
        box.setAlignment(Qt.AlignCenter)
        box.setMinimumHeight(260)
        box.setStyleSheet("background:#0b1522;color:#71879c;font-size:24px;font-weight:800;")
        photo = self.manager.store.find_photo(registration_id, division)
        if photo:
            pix = QPixmap(str(photo))
            if not pix.isNull():
                box.setText("")
                box.setPixmap(pix.scaled(700, 460, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        return box

    def _card(self, division: str, racer: dict[str, Any], lane: int, place: int | None = None) -> QFrame:
        state = self.manager.state
        reg = next((r for r in state["registrations"] if r.get("id") == racer.get("registrationId")), None)
        car = (reg.get("tradCar") if division == "Traditional" else reg.get("modCar")) if reg else racer.get("car", "")
        car = car or "Unnamed Car"
        card = QFrame()
        card.setStyleSheet("QFrame{background:#101d2d;border:2px solid #29415c;border-radius:16px;}")
        lay = QVBoxLayout(card)
        top = QHBoxLayout()
        lane_label = self._label(f"LANE {lane}", 22, True, "#111820")
        lane_label.setStyleSheet("background:#d8a63d;color:#111820;padding:8px;border-radius:8px;")
        top.addWidget(lane_label)
        top.addStretch()
        if place:
            place_label = self._label(ordinal(place).upper(), 24, True, "#111820")
            place_label.setStyleSheet("background:white;color:#111820;padding:8px;border-radius:8px;")
            top.addWidget(place_label)
        lay.addLayout(top)
        lay.addWidget(self._photo(racer.get("registrationId"), division, car), 1)
        lay.addWidget(self._label(car, 27, True, "#f2ca69", Qt.AlignLeft))
        lay.addWidget(self._label(racer.get("name", ""), 18, True, "white", Qt.AlignLeft))
        return card

    def render_heat(self, division: str, heat: dict[str, Any], total: int, mode: str, runoff: dict[str, Any] | None = None) -> None:
        self._clear()
        eyebrow = f"{division.upper()} DIVISION"
        if runoff:
            eyebrow += "  •  TROPHY RUNOFF"
        headline = "NOW RACING" if mode == "race" else "HEAT RESULTS" if mode == "results" else "UP NEXT"
        self.layout.addWidget(self._label(eyebrow, 17, True, "#9eb0c2"))
        self.layout.addWidget(self._label(headline, 42, True))
        sub = f"HEAT {heat.get('id', 1)} OF {total}"
        if runoff:
            sub = f"RUNOFF SET {runoff.get('attempt', 1)}  •  {sub}"
        self.layout.addWidget(self._label(sub, 20, True, "#f2ca69"))
        grid = QGridLayout()
        grid.setSpacing(16)
        bucket = race_bucket(self.manager.state, division)
        racers = race_racers(self.manager.state, division)
        result_map = {str(x.get("racer_id", x.get("racerId"))): int(x.get("position", 0)) for x in heat.get("results", [])}
        entries = []
        for lane, rid in enumerate(heat.get("lanes", []), start=1):
            if rid in (None, ""):
                continue
            racer = next((r for r in racers if str(r["id"]) == str(rid)), None)
            if racer:
                entries.append((lane, racer, result_map.get(str(rid))))
        if mode == "results":
            entries.sort(key=lambda x: x[2] or 99)
        for i, (lane, racer, place) in enumerate(entries):
            grid.addWidget(self._card(division, racer, lane, place if mode == "results" else None), 0, i)
        self.layout.addLayout(grid, 1)

    def render_final(self, division: str) -> None:
        self._clear()
        self.layout.addWidget(self._label(f"{division.upper()} DIVISION", 18, True, "#9eb0c2"))
        self.layout.addWidget(self._label("FINAL RESULTS", 44, True))
        rows = final_standings(self.manager.state, division)[:4]
        grid = QGridLayout()
        for i, row in enumerate(rows):
            racer = next(r for r in race_racers(self.manager.state, division) if r["id"] == row["id"])
            card = self._card(division, racer, i + 1, i + 1)
            grid.addWidget(card, 0, i)
        self.layout.addLayout(grid, 1)

    def render(self) -> None:
        division = self.override_division or self.manager.current_division
        bucket = race_bucket(self.manager.state, division)
        runoff = bucket.get("runoff")
        heats = runoff.get("heats", []) if runoff else bucket.get("heats", [])
        current = int(runoff.get("current", 0) if runoff else bucket.get("current", 0))
        if self.override_heat is not None:
            self.render_heat(division, self.override_heat, len(heats), self.mode, runoff)
            return
        if not heats:
            self.render_waiting(division)
            return
        current = max(0, min(current, len(heats) - 1))
        heat = heats[current]
        mode = "results" if heat.get("results") else "race"
        if all(h.get("results") for h in heats) and not runoff and not trophy_tie_groups(standings(race_racers(self.manager.state, division), heats)):
            self.render_final(division)
        else:
            self.render_heat(division, heat, len(heats), mode, runoff)

    def show_saved_heat_sequence(self, division: str, saved_heat: dict[str, Any], next_heat: dict[str, Any] | None, total: int, runoff: dict[str, Any] | None) -> None:
        self.timer.stop()
        self.override_division = division
        self.override_heat = copy.deepcopy(saved_heat)
        self.mode = "results"
        self.render_heat(division, self.override_heat, total, "results", runoff)
        self._next_preview = copy.deepcopy(next_heat) if next_heat else None
        self._next_total = total
        self._next_runoff = copy.deepcopy(runoff) if runoff else None
        self.timer.start(6500)

    def _after_results(self) -> None:
        if self._next_preview:
            self.override_heat = self._next_preview
            self.mode = "upnext"
            self.render_heat(self.override_division or self.manager.current_division, self.override_heat, self._next_total, "upnext", self._next_runoff)
            QTimer.singleShot(5000, self._return_live)
        else:
            self._return_live()

    def _return_live(self) -> None:
        self.override_heat = None
        self.override_division = None
        self.mode = "normal"
        self.render()


class RegistrationPage(QWidget):
    changed = Signal()

    def __init__(self, manager: "MainWindow") -> None:
        super().__init__()
        self.manager = manager
        self.edit_id: Any = None
        layout = QHBoxLayout(self)
        form_box = QGroupBox("Add / Edit Registration")
        form = QFormLayout(form_box)
        self.name = QLineEdit()
        self.age = QSpinBox(); self.age.setRange(0, 120)
        self.contact = QLineEdit()
        self.division = QComboBox(); self.division.addItems(["Traditional", "Modified", "Both"])
        self.trad_car = QLineEdit(); self.mod_car = QLineEdit()
        self.status = QComboBox(); self.status.addItems(["Registered", "Confirmed", "Withdrawn"])
        self.rules = QCheckBox("Rules sent")
        self.notes = QTextEdit(); self.notes.setMaximumHeight(90)
        for label, widget in [("Racer Name", self.name), ("Age", self.age), ("Email / Phone", self.contact), ("Race Entry", self.division), ("Traditional Car Name", self.trad_car), ("Modified Car Name", self.mod_car), ("Status", self.status), ("Notes", self.notes)]:
            form.addRow(label, widget)
        form.addRow("", self.rules)
        buttons = QHBoxLayout()
        save = QPushButton("SAVE RACER"); save.setObjectName("primary"); save.clicked.connect(self.save)
        clear = QPushButton("CLEAR"); clear.clicked.connect(self.clear)
        delete = QPushButton("DELETE"); delete.clicked.connect(self.delete)
        buttons.addWidget(save); buttons.addWidget(clear); buttons.addWidget(delete)
        form.addRow(buttons)
        layout.addWidget(form_box, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Registrations"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Racer", "Entry", "Traditional Car", "Modified Car", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(self.load_selected)
        right.addWidget(self.table, 1)
        layout.addLayout(right, 2)
        self.refresh()

    def _next_number(self, field: str) -> int:
        vals = [int(r.get(field, 0) or 0) for r in self.manager.state["registrations"]]
        return max(vals or [0]) + 1

    def save(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Racer Name", "Enter the racer's name first.")
            return
        regs = self.manager.state["registrations"]
        if self.edit_id is None:
            now = int(time.time() * 1000)
            reg = {
                "id": now,
                "name": self.name.text().strip(),
                "age": self.age.value(),
                "contact": self.contact.text().strip(),
                "division": self.division.currentText(),
                "tradCar": self.trad_car.text().strip(),
                "modCar": self.mod_car.text().strip(),
                "status": self.status.currentText(),
                "rulesSent": self.rules.isChecked(),
                "notes": self.notes.toPlainText().strip(),
                "tradCheckIn": "waiting",
                "modCheckIn": "waiting",
                "tradNo": self._next_number("tradNo"),
                "modNo": self._next_number("modNo"),
            }
            regs.append(reg)
        else:
            reg = next(r for r in regs if r["id"] == self.edit_id)
            reg.update({"name": self.name.text().strip(), "age": self.age.value(), "contact": self.contact.text().strip(), "division": self.division.currentText(), "tradCar": self.trad_car.text().strip(), "modCar": self.mod_car.text().strip(), "status": self.status.currentText(), "rulesSent": self.rules.isChecked(), "notes": self.notes.toPlainText().strip()})
        self.manager.save("registration")
        self.clear(); self.refresh(); self.changed.emit()

    def clear(self) -> None:
        self.edit_id = None
        self.name.clear(); self.age.setValue(0); self.contact.clear(); self.division.setCurrentIndex(0)
        self.trad_car.clear(); self.mod_car.clear(); self.status.setCurrentIndex(0); self.rules.setChecked(False); self.notes.clear()

    def delete(self) -> None:
        if self.edit_id is None:
            return
        answer = QMessageBox.question(self, "Delete Racer", "Delete this registration?")
        if answer != QMessageBox.Yes:
            return
        self.manager.state["registrations"] = [r for r in self.manager.state["registrations"] if r["id"] != self.edit_id]
        self.manager.save("delete-registration")
        self.clear(); self.refresh(); self.changed.emit()

    def load_selected(self, row: int, _col: int) -> None:
        rid = self.table.item(row, 0).data(Qt.UserRole)
        reg = next((r for r in self.manager.state["registrations"] if r["id"] == rid), None)
        if not reg:
            return
        self.edit_id = rid
        self.name.setText(reg.get("name", "")); self.age.setValue(int(reg.get("age", 0) or 0)); self.contact.setText(reg.get("contact", ""))
        self.division.setCurrentText(reg.get("division", "Traditional")); self.trad_car.setText(reg.get("tradCar", "")); self.mod_car.setText(reg.get("modCar", ""))
        self.status.setCurrentText(reg.get("status", "Registered")); self.rules.setChecked(bool(reg.get("rulesSent"))); self.notes.setPlainText(reg.get("notes", ""))

    def refresh(self) -> None:
        regs = sorted(self.manager.state["registrations"], key=lambda r: r.get("name", ""))
        self.table.setRowCount(len(regs))
        for row, reg in enumerate(regs):
            vals = [reg.get("name", ""), reg.get("division", ""), reg.get("tradCar", ""), reg.get("modCar", ""), reg.get("status", "")]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if col == 0:
                    item.setData(Qt.UserRole, reg["id"])
                self.table.setItem(row, col, item)


class DivisionRacePage(QWidget):
    def __init__(self, manager: "MainWindow", division: str) -> None:
        super().__init__()
        self.manager = manager
        self.division = division
        self.finish_order: list[Any] = []
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self); layout.addWidget(self.tabs)
        self.checkin_tab = QWidget(); self.inspection_tab = QWidget(); self.generate_tab = QWidget(); self.control_tab = QWidget(); self.results_tab = QWidget()
        self.tabs.addTab(self.checkin_tab, "Check-In")
        self.tabs.addTab(self.inspection_tab, "Inspection & Photo")
        self.tabs.addTab(self.generate_tab, "Generate Race")
        self.tabs.addTab(self.control_tab, "Race Control")
        self.tabs.addTab(self.results_tab, "Results")
        self._build_checkin(); self._build_inspection(); self._build_generate(); self._build_control(); self._build_results()
        self.tabs.currentChanged.connect(lambda _i: self.refresh())

    def regs(self) -> list[dict[str, Any]]:
        return [r for r in self.manager.state["registrations"] if division_match(r, self.division)]

    def check_field(self) -> str:
        return "tradCheckIn" if self.division == "Traditional" else "modCheckIn"

    def inspect_field(self) -> str:
        return "tradInspection" if self.division == "Traditional" else "modInspection"

    def _build_checkin(self) -> None:
        lay = QVBoxLayout(self.checkin_tab)
        self.check_table = QTableWidget(0, 4); self.check_table.setHorizontalHeaderLabels(["Racer", "Car", "Status", "Action"]); self.check_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.check_table)

    def _build_inspection(self) -> None:
        lay = QVBoxLayout(self.inspection_tab)
        top = QHBoxLayout(); top.addWidget(QLabel("Racer")); self.inspect_select = QComboBox(); self.inspect_select.currentIndexChanged.connect(self.load_inspection); top.addWidget(self.inspect_select, 1); lay.addLayout(top)
        self.weight = QLineEdit(); self.weight.setPlaceholderText("0.00 oz")
        self.weight_row = QFrame(); wf = QHBoxLayout(self.weight_row); wf.addWidget(QLabel("Weight (oz)")); wf.addWidget(self.weight)
        lay.addWidget(self.weight_row)
        self.checks_box = QGroupBox("Inspection"); self.checks_layout = QVBoxLayout(self.checks_box); lay.addWidget(self.checks_box)
        self.class_box = QFrame(); cf = QHBoxLayout(self.class_box); cf.addWidget(QLabel("Modified Run Classification")); self.race_class = QComboBox(); self.race_class.addItems(["Official Modified Race", "Exhibition Only"]); cf.addWidget(self.race_class); lay.addWidget(self.class_box)
        buttons = QHBoxLayout(); photo = QPushButton("CHOOSE CAR PHOTO"); photo.clicked.connect(self.choose_photo); save = QPushButton("SAVE INSPECTION"); save.setObjectName("primary"); save.clicked.connect(self.save_inspection); buttons.addWidget(photo); buttons.addWidget(save); lay.addLayout(buttons)
        self.photo_status = QLabel(""); lay.addWidget(self.photo_status); lay.addStretch()
        self.inspect_checks: list[QCheckBox] = []

    def _build_generate(self) -> None:
        lay = QVBoxLayout(self.generate_tab)
        self.gen_status = QLabel(); self.gen_status.setWordWrap(True); lay.addWidget(self.gen_status)
        self.generate_btn = QPushButton("GENERATE VERIFIED RACE"); self.generate_btn.setObjectName("primary"); self.generate_btn.clicked.connect(self.generate_race); lay.addWidget(self.generate_btn)
        self.schedule = QTableWidget(0, 5); self.schedule.setHorizontalHeaderLabels(["Heat", "Lane 1", "Lane 2", "Lane 3", "Lane 4"]); self.schedule.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); lay.addWidget(self.schedule, 1)

    def _build_control(self) -> None:
        lay = QVBoxLayout(self.control_tab)
        self.heat_title = QLabel(); self.heat_title.setAlignment(Qt.AlignCenter); f=QFont(); f.setPointSize(24); f.setBold(True); self.heat_title.setFont(f); lay.addWidget(self.heat_title)
        self.control_notice = QLabel(); self.control_notice.setAlignment(Qt.AlignCenter); self.control_notice.setWordWrap(True); lay.addWidget(self.control_notice)
        self.lane_buttons = QVBoxLayout(); lay.addLayout(self.lane_buttons)
        self.finish_label = QLabel("Finish Order: —"); self.finish_label.setWordWrap(True); lay.addWidget(self.finish_label)
        actions = QHBoxLayout(); undo=QPushButton("Undo Pick"); undo.clicked.connect(self.undo_pick); self.save_result_btn=QPushButton("SAVE RESULTS"); self.save_result_btn.setObjectName("primary"); self.save_result_btn.clicked.connect(self.save_results); prev=QPushButton("← Previous"); prev.clicked.connect(lambda:self.move_heat(-1)); nxt=QPushButton("Next →"); nxt.clicked.connect(lambda:self.move_heat(1)); projector=QPushButton("PROJECTOR"); projector.clicked.connect(self.manager.show_projector); self.continue_runoff_btn=QPushButton("START NEXT RUNOFF SET"); self.continue_runoff_btn.clicked.connect(self.continue_runoff)
        for b in (undo,self.save_result_btn,prev,nxt,projector,self.continue_runoff_btn): actions.addWidget(b)
        lay.addLayout(actions); lay.addStretch()

    def _build_results(self) -> None:
        lay=QVBoxLayout(self.results_tab)
        self.results_notice=QLabel(); self.results_notice.setWordWrap(True); lay.addWidget(self.results_notice)
        self.start_runoff_btn=QPushButton("START TROPHY RUNOFF"); self.start_runoff_btn.setObjectName("primary"); self.start_runoff_btn.clicked.connect(self.start_runoff); lay.addWidget(self.start_runoff_btn)
        self.results_table=QTableWidget(0,5); self.results_table.setHorizontalHeaderLabels(["Place","Racer","Points","Races","Wins"]); self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); lay.addWidget(self.results_table,1)

    def refresh(self) -> None:
        self.refresh_checkin(); self.refresh_inspection(); self.refresh_generate(); self.refresh_control(); self.refresh_results()

    def refresh_checkin(self) -> None:
        regs=self.regs(); self.check_table.setRowCount(len(regs)); field=self.check_field()
        for row,reg in enumerate(regs):
            car=reg.get("tradCar","") if self.division=="Traditional" else reg.get("modCar","")
            status=reg.get(field,"waiting")
            for col,val in enumerate([reg.get("name",""),car,"CHECKED IN" if status=="checked" else "NO SHOW" if status=="noshow" else "WAITING"]): self.check_table.setItem(row,col,QTableWidgetItem(str(val)))
            b=QPushButton("MARK WAITING" if status=="checked" else "CHECK IN"); b.clicked.connect(lambda _=False,rid=reg["id"]:self.toggle_checkin(rid)); self.check_table.setCellWidget(row,3,b)

    def toggle_checkin(self,rid:Any)->None:
        reg=next(r for r in self.manager.state["registrations"] if r["id"]==rid); field=self.check_field(); reg[field]="waiting" if reg.get(field)=="checked" else "checked"; self.clear_race(); self.manager.save(f"{self.division}-checkin"); self.refresh()

    def _selected_reg(self)->dict[str,Any]|None:
        rid=self.inspect_select.currentData(); return next((r for r in self.manager.state["registrations"] if r.get("id")==rid),None)

    def refresh_inspection(self)->None:
        current=self.inspect_select.currentData(); self.inspect_select.blockSignals(True); self.inspect_select.clear(); self.inspect_select.addItem("Select racer…",None)
        for reg in self.regs():
            if reg.get(self.check_field())=="checked": self.inspect_select.addItem(reg.get("name",""),reg["id"])
        idx=self.inspect_select.findData(current); self.inspect_select.setCurrentIndex(idx if idx>=0 else 0); self.inspect_select.blockSignals(False); self.load_inspection()

    def load_inspection(self)->None:
        while self.checks_layout.count():
            item=self.checks_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.inspect_checks=[]; reg=self._selected_reg(); self.weight_row.setVisible(self.division=="Traditional"); self.class_box.setVisible(self.division=="Modified")
        if not reg: self.photo_status.setText(""); return
        data=reg.get(self.inspect_field(),{}) or {}; passed=set(data.get("passed",[])); labels=TRAD_ITEMS if self.division=="Traditional" else MOD_SAFETY+MOD_COMPAT
        for label in labels:
            cb=QCheckBox(label); cb.setChecked(label in passed); self.inspect_checks.append(cb); self.checks_layout.addWidget(cb)
        if self.division=="Traditional": self.weight.setText(str(data.get("weight", "")))
        else: self.race_class.setCurrentIndex(1 if data.get("raceClass")=="exhibition" else 0)
        photo=self.manager.store.find_photo(reg["id"],self.division); self.photo_status.setText(f"Photo saved: {photo.name}" if photo else "No car photo saved yet.")

    def choose_photo(self)->None:
        reg=self._selected_reg()
        if not reg: return
        path,_=QFileDialog.getOpenFileName(self,"Choose Car Photo","","Images (*.jpg *.jpeg *.png *.webp)")
        if not path:return
        saved=self.manager.store.save_photo(reg["id"],self.division,path); self.photo_status.setText(f"Photo saved: {saved.name}"); self.manager.save(f"{self.division}-photo",snapshot=False)

    def save_inspection(self)->None:
        reg=self._selected_reg()
        if not reg:return
        labels=TRAD_ITEMS if self.division=="Traditional" else MOD_SAFETY+MOD_COMPAT; passed=[label for label,cb in zip(labels,self.inspect_checks) if cb.isChecked()]
        if self.division=="Traditional":
            try: weight=float(self.weight.text())
            except ValueError: weight=0
            approved=len(passed)==len(labels) and 0<weight<=5.0
            reg[self.inspect_field()]={"passed":passed,"weight":weight,"approved":approved,"savedAt":time.time()}
            msg="Traditional inspection PASSED." if approved else "Inspection saved, but this car is not yet approved."
        else:
            safe=all(x in passed for x in MOD_SAFETY); compat=all(x in passed for x in MOD_COMPAT); requested="exhibition" if self.race_class.currentIndex()==1 else "official"; approved=safe and (requested=="exhibition" or compat); race_class=requested if approved else "blocked"
            reg[self.inspect_field()]={"passed":passed,"approved":approved,"raceClass":race_class,"savedAt":time.time()}
            msg="Modified car approved for Official Race." if race_class=="official" else "Modified car approved for Exhibition Only." if race_class=="exhibition" else "Modified car is NOT cleared to run."
        self.clear_race(); self.manager.save(f"{self.division}-inspection"); QMessageBox.information(self,"Inspection",msg); self.refresh()

    def eligible_regs(self)->list[dict[str,Any]]:
        out=[]
        for reg in self.regs():
            if reg.get(self.check_field())!="checked":continue
            ins=reg.get(self.inspect_field(),{}) or {}
            if not ins.get("approved"):continue
            if self.division=="Modified" and ins.get("raceClass")!="official":continue
            out.append(reg)
        return out

    def clear_race(self)->None:
        bucket=race_bucket(self.manager.state,self.division); bucket["heats"]=[]; bucket["current"]=0; bucket["tieBreaks"]={}; bucket["runoff"]=None
        if self.division=="Traditional": self.manager.state["racers"]=[]
        else: bucket["raceRacers"]=[]

    def _make_racers(self,regs:list[dict[str,Any]])->list[dict[str,Any]]:
        out=[]; idfield="tradRacerId" if self.division=="Traditional" else "modRacerId"; nofield="tradNo" if self.division=="Traditional" else "modNo"; carfield="tradCar" if self.division=="Traditional" else "modCar"
        for i,reg in enumerate(regs,1):
            if not reg.get(idfield):reg[idfield]=int(time.time()*1000000)+i
            out.append({"id":reg[idfield],"registrationId":reg["id"],"name":reg.get("name",""),"car":reg.get(carfield,""),"division":self.division,"number":int(reg.get(nofield,i) or i)})
        return out

    def generate_race(self)->None:
        regs=self.eligible_regs()
        if len(regs)<2: QMessageBox.warning(self,"Generate Race","At least 2 checked-in, inspected, eligible racers are required.");return
        bucket=race_bucket(self.manager.state,self.division); racers=self._make_racers(regs); heats=build_fair_schedule([r["id"] for r in racers]); check=verify_schedule(heats,[r["id"] for r in racers])
        if not check.ok: QMessageBox.critical(self,"Schedule Verification","Race schedule failed verification:\n"+"\n".join(check.errors));return
        if self.division=="Traditional":self.manager.state["racers"]=racers
        else:bucket["raceRacers"]=racers
        bucket["heats"]=heats;bucket["current"]=0;bucket["tieBreaks"]={};bucket["runoff"]=None;self.manager.state["raceType"]=self.division;self.manager.save(f"{self.division}-generate-race");self.refresh()

    def refresh_generate(self)->None:
        bucket=race_bucket(self.manager.state,self.division); racers=race_racers(self.manager.state,self.division); heats=bucket.get("heats",[]); eligible=self.eligible_regs(); self.generate_btn.setText("REGENERATE VERIFIED RACE" if heats else "GENERATE VERIFIED RACE")
        if heats:
            check=verify_schedule(heats,[r["id"] for r in racers]); self.gen_status.setText(("✓ RACE SCHEDULE VERIFIED\n" if check.ok else "RACE SCHEDULE FAILED\n")+f"{len(racers)} racers • {len(heats)} heats • {check.empty_slots} empty lane slots • every racer uses every lane once"+("\n"+"\n".join(check.errors) if check.errors else ""))
        else:self.gen_status.setText(f"{len(eligible)} racer(s) currently eligible for the Official {self.division} race.")
        self.schedule.setRowCount(len(heats))
        names={r["id"]:r["name"] for r in racers}
        for row,h in enumerate(heats):
            vals=[f"{h['id']} of {len(heats)}"]+[names.get(x,"—") if x else "—" for x in h.get("lanes",[])]
            for col,val in enumerate(vals):self.schedule.setItem(row,col,QTableWidgetItem(str(val)))

    def _runoff(self)->dict[str,Any]|None:return race_bucket(self.manager.state,self.division).get("runoff")
    def _control_heats(self)->tuple[list[dict[str,Any]],int]:
        bucket=race_bucket(self.manager.state,self.division); ro=bucket.get("runoff")
        return (ro.get("heats",[]),int(ro.get("current",0))) if ro else (bucket.get("heats",[]),int(bucket.get("current",0)))

    def refresh_control(self)->None:
        while self.lane_buttons.count():
            item=self.lane_buttons.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.continue_runoff_btn.hide(); heats,current=self._control_heats(); bucket=race_bucket(self.manager.state,self.division); ro=bucket.get("runoff")
        if ro and ro.get("completed"):
            self.heat_title.setText("TROPHY RUNOFF - TIE REMAINS"); self.control_notice.setText("Racers already separated keep their order. Only the racers still tied race again."); self.save_result_btn.setEnabled(False); self.continue_runoff_btn.show(); return
        if not heats:self.heat_title.setText("Generate the race first");self.control_notice.setText("");self.save_result_btn.setEnabled(False);return
        ids=[r["id"] for r in (self._runoff_racers(ro) if ro else race_racers(self.manager.state,self.division))]; check=verify_schedule(heats,ids)
        if not check.ok:self.heat_title.setText("RACE CONTROL LOCKED");self.control_notice.setText("Schedule failed verification:\n"+"\n".join(check.errors));self.save_result_btn.setEnabled(False);return
        current=max(0,min(current,len(heats)-1)); h=heats[current]; if_saved=bool(h.get("results")); self.heat_title.setText(("TROPHY RUNOFF • " if ro else "")+f"Heat {h['id']} of {len(heats)}"); self.control_notice.setText("✓ VERIFIED RACE SCHEDULE")
        active=[]; racers=self._runoff_racers(ro) if ro else race_racers(self.manager.state,self.division)
        if if_saved:self.finish_order=[x.get("racer_id",x.get("racerId")) for x in sorted(h.get("results",[]),key=lambda x:x.get("position",99))]
        else:self.finish_order=[rid for rid in self.finish_order if rid in h.get("lanes",[])]
        for lane,rid in enumerate(h.get("lanes",[]),1):
            if not rid:continue
            racer=next((r for r in racers if r["id"]==rid),None); active.append(rid); b=QPushButton(f"Lane {lane} — {racer.get('car') or racer.get('name') if racer else rid}   ({racer.get('name','') if racer else ''})"); b.setMinimumHeight(54); b.setEnabled(not if_saved); b.clicked.connect(lambda _=False,x=rid:self.pick_finish(x)); self.lane_buttons.addWidget(b)
        names={r["id"]:(r.get("car") or r.get("name")) for r in racers}; self.finish_label.setText("Finish Order: "+("  →  ".join(f"{ordinal(i+1)} {names.get(rid,rid)}" for i,rid in enumerate(self.finish_order)) if self.finish_order else "—")); self.save_result_btn.setEnabled(not if_saved and len(self.finish_order)==len(active))

    def _runoff_racers(self,ro:dict[str,Any]|None)->list[dict[str,Any]]:
        if not ro:return[]
        ids=set(ro.get("currentIds",[]));return[r for r in race_racers(self.manager.state,self.division) if r["id"] in ids]

    def pick_finish(self,rid:Any)->None:
        if rid in self.finish_order:self.finish_order.remove(rid)
        else:self.finish_order.append(rid)
        self.refresh_control()
    def undo_pick(self)->None:
        if self.finish_order:self.finish_order.pop();self.refresh_control()
    def move_heat(self,delta:int)->None:
        bucket=race_bucket(self.manager.state,self.division);ro=bucket.get("runoff");heats,current=self._control_heats();new=max(0,min(current+delta,len(heats)-1)) if heats else 0
        if ro:ro["current"]=new
        else:bucket["current"]=new
        self.finish_order=[];self.manager.save(f"{self.division}-move-heat",snapshot=False);self.refresh_control();self.manager.refresh_projector()

    def save_results(self)->None:
        bucket=race_bucket(self.manager.state,self.division);ro=bucket.get("runoff");heats,current=self._control_heats();h=heats[current];active=[x for x in h.get("lanes",[]) if x]
        if len(self.finish_order)!=len(active) or set(self.finish_order)!=set(active):return
        h["results"]=[{"racer_id":rid,"position":i+1,"points":heat_points(i,len(active))} for i,rid in enumerate(self.finish_order)]
        saved_heat=copy.deepcopy(h); next_heat=None
        if current<len(heats)-1:
            if ro:ro["current"]=current+1
            else:bucket["current"]=current+1
            next_heat=heats[current+1]
        if ro and all(x.get("results") for x in heats):self._finish_runoff(ro)
        self.finish_order=[];self.manager.save(f"{self.division}-heat-results");self.refresh();self.manager.project_saved_heat(self.division,saved_heat,next_heat,len(heats),ro)

    def _finish_runoff(self,ro:dict[str,Any])->None:
        racers=self._runoff_racers(ro);rows=standings(racers,ro.get("heats",[]));replacement=score_blocks(rows);idx=int(ro.get("blockIndex",0));blocks=ro.get("blocks",[]);blocks[idx:idx+1]=replacement;ro["blocks"]=blocks;next_idx=next((i for i,b in enumerate(blocks) if len(b)>1),-1)
        if next_idx>=0:ro["completed"]=True;ro["nextBlockIndex"]=next_idx;return
        bucket=race_bucket(self.manager.state,self.division);bucket.setdefault("tieBreaks",{})[ro["key"]]={"order":[x for block in blocks for x in block],"attempts":ro.get("attempt",1),"resolvedAt":time.time()};bucket["runoff"]=None

    def continue_runoff(self)->None:
        bucket=race_bucket(self.manager.state,self.division);ro=bucket.get("runoff")
        if not ro or not ro.get("completed"):return
        idx=int(ro.get("nextBlockIndex",-1));ids=list(ro.get("blocks",[])[idx]);heats=build_fair_schedule(ids);check=verify_schedule(heats,ids)
        if not check.ok:QMessageBox.critical(self,"Runoff","New runoff schedule failed verification.");return
        ro.update({"blockIndex":idx,"currentIds":ids,"attempt":int(ro.get("attempt",1))+1,"current":0,"heats":heats,"completed":False,"nextBlockIndex":None});self.manager.save(f"{self.division}-continue-runoff");self.refresh_control();self.manager.refresh_projector()

    def refresh_results(self)->None:
        bucket=race_bucket(self.manager.state,self.division);heats=bucket.get("heats",[]);rows=final_standings(self.manager.state,self.division) if heats else[];complete=bool(heats) and all(h.get("results") for h in heats);raw=standings(race_racers(self.manager.state,self.division),heats) if heats else[];pending=trophy_tie_groups(raw)[0] if complete and trophy_tie_groups(raw) else None
        self.start_runoff_btn.setVisible(bool(pending and not bucket.get("runoff")))
        if not heats:self.results_notice.setText("No race has been generated yet.")
        elif not complete:self.results_notice.setText(f"PROVISIONAL RESULTS — {sum(1 for h in heats if h.get('results'))} of {len(heats)} heats saved.")
        elif bucket.get("runoff"):self.results_notice.setText("TROPHY RUNOFF IN PROGRESS — trophy places are not final yet.")
        elif pending:self.results_notice.setText(f"TROPHY TIE — runoff required for {ordinal(pending['start']+1)} through {ordinal(pending['end']+1)} place. No hidden tiebreaker will be used.")
        else:self.results_notice.setText("✓ TROPHY PLACES FINAL")
        self.results_table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for c,val in enumerate([i+1,r["name"],f"{r['points']:.2f}",r["races"],r["wins"]]):self.results_table.setItem(i,c,QTableWidgetItem(str(val)))

    def start_runoff(self)->None:
        bucket=race_bucket(self.manager.state,self.division);raw=standings(race_racers(self.manager.state,self.division),bucket.get("heats",[]));groups=trophy_tie_groups(raw)
        if not groups:return
        g=groups[0];ids=[r["id"] for r in g["racers"]];heats=build_fair_schedule(ids);check=verify_schedule(heats,ids)
        if not check.ok:QMessageBox.critical(self,"Runoff","Runoff schedule failed verification.");return
        bucket["runoff"]={"active":True,"key":group_key(g["racers"]),"rootIds":ids[:],"blocks":[ids[:]],"blockIndex":0,"currentIds":ids[:],"placeStart":g["start"]+1,"placeEnd":g["end"]+1,"attempt":1,"current":0,"heats":heats,"completed":False};self.tabs.setCurrentWidget(self.control_tab);self.manager.save(f"{self.division}-start-runoff");self.refresh();self.manager.refresh_projector()


class BackupPage(QWidget):
    def __init__(self, manager:"MainWindow")->None:
        super().__init__();self.manager=manager;lay=QVBoxLayout(self);title=QLabel("Backup & Recovery");f=QFont();f.setPointSize(22);f.setBold(True);title.setFont(f);lay.addWidget(title)
        self.status=QLabel();self.status.setWordWrap(True);lay.addWidget(self.status)
        save=QPushButton("CREATE FULL PORTABLE BACKUP");save.setObjectName("primary");save.clicked.connect(self.create);restore=QPushButton("RESTORE FULL BACKUP");restore.clicked.connect(self.restore);folder=QPushButton("SHOW DATA LOCATION");folder.clicked.connect(self.show_location);lay.addWidget(save);lay.addWidget(restore);lay.addWidget(folder);self.location=QLabel();self.location.setTextInteractionFlags(Qt.TextSelectableByMouse);lay.addWidget(self.location);lay.addStretch();self.refresh()
    def refresh(self)->None:self.status.setText("Every change is written to SQLite immediately. Backups contain derby.db plus all car photo files and SHA-256 integrity checks.");self.location.setText(f"Data: {self.manager.store.data_dir}\nDatabase: {self.manager.store.db_path}\nPhotos: {self.manager.store.photos_dir}\nBackups: {self.manager.store.backups_dir}")
    def create(self)->None:
        path,_=QFileDialog.getSaveFileName(self,"Save Full Derby Backup",str(self.manager.store.backups_dir/"MNLT_Derby_Backup.zip"),"ZIP Backup (*.zip)")
        if not path:return
        try:p=create_full_backup(self.manager.store,path);self.status.setText(f"✓ Backup created and checksummed:\n{p}")
        except Exception as e:QMessageBox.critical(self,"Backup Failed",str(e))
    def restore(self)->None:
        path,_=QFileDialog.getOpenFileName(self,"Restore Full Derby Backup",str(self.manager.store.backups_dir),"ZIP Backup (*.zip)")
        if not path:return
        try:verify_backup(path)
        except Exception as e:QMessageBox.critical(self,"Invalid Backup",str(e));return
        if QMessageBox.question(self,"Restore Backup","Integrity verified. Restore this backup? The current derby will be backed up first.")!=QMessageBox.Yes:return
        try:restore_full_backup(self.manager.store,path);QMessageBox.information(self,"Restored","Backup restored. The app will now close. Reopen MNLT Derby Manager to continue.");QApplication.quit()
        except Exception as e:QMessageBox.critical(self,"Restore Failed",str(e))
    def show_location(self)->None:
        QMessageBox.information(self,"Data Location",str(self.manager.store.data_dir))


class MainWindow(QMainWindow):
    def __init__(self)->None:
        super().__init__();self.setWindowTitle(f"MNLT Derby Manager • {APP_VERSION}");self.resize(1400,900);self.store=DerbyStore();self.state=ensure_state(self.store.load_state());self.current_division="Traditional";self.projector:ProjectorWindow|None=None
        root=QWidget();outer=QVBoxLayout(root);header=QHBoxLayout();brand=QLabel("MNLT DERBY MANAGER");f=QFont();f.setPointSize(20);f.setBold(True);brand.setFont(f);header.addWidget(brand);header.addStretch();self.save_label=QLabel("SQLite autosave ready");header.addWidget(self.save_label);outer.addLayout(header)
        body=QHBoxLayout();nav=QVBoxLayout();self.stack=QStackedWidget();body.addLayout(nav,0);body.addWidget(self.stack,1);outer.addLayout(body,1);self.setCentralWidget(root)
        self.registration=RegistrationPage(self);self.traditional=DivisionRacePage(self,"Traditional");self.modified=DivisionRacePage(self,"Modified");self.backup=BackupPage(self)
        self.home=self._home_page();self.stack.addWidget(self.home);self.stack.addWidget(self.registration);self.stack.addWidget(self.traditional);self.stack.addWidget(self.modified);self.stack.addWidget(self.backup)
        for text,page in [("Home",self.home),("Registration",self.registration),("Traditional Race",self.traditional),("Modified Race",self.modified),("Backup & Recovery",self.backup)]:
            b=QPushButton(text);b.setMinimumHeight(48);b.clicked.connect(lambda _=False,p=page:self.open_page(p));nav.addWidget(b)
        projector=QPushButton("Open Projector");projector.setMinimumHeight(48);projector.clicked.connect(self.show_projector);nav.addWidget(projector);nav.addStretch();self.setStyleSheet(self._style());self.registration.changed.connect(self.refresh_all);QTimer.singleShot(1000,self._startup_backup)
    def _style(self)->str:return """QMainWindow,QWidget{background:#0b1522;color:#f4f7fb;font-family:Arial;}QGroupBox{border:1px solid #30465f;border-radius:10px;margin-top:10px;padding:12px;font-weight:bold;}QLineEdit,QComboBox,QSpinBox,QTextEdit,QTableWidget{background:#0e1c2c;border:1px solid #41566e;border-radius:6px;padding:6px;color:white;}QHeaderView::section{background:#13243a;color:#9dafc1;padding:7px;border:0;}QPushButton{background:#2a405a;color:white;border:0;border-radius:8px;padding:10px;font-weight:bold;}QPushButton:hover{background:#385472;}QPushButton#primary{background:#d8a63d;color:#111820;}QTabBar::tab{background:#13243a;color:#c7d3df;padding:11px 16px;}QTabBar::tab:selected{background:#d8a63d;color:#111820;font-weight:bold;}"""
    def _home_page(self)->QWidget:
        w=QWidget();lay=QVBoxLayout(w);lay.addStretch();title=QLabel("MNLT Pinewood Derby");f=QFont();f.setPointSize(34);f.setBold(True);title.setFont(f);title.setAlignment(Qt.AlignCenter);lay.addWidget(title);sub=QLabel("Desktop Race Manager • No browser required");sub.setAlignment(Qt.AlignCenter);lay.addWidget(sub);lay.addStretch();return w
    def open_page(self,page:QWidget)->None:self.stack.setCurrentWidget(page);self.refresh_all()
    def save(self,reason:str,snapshot:bool=True)->None:
        self.store.save_state(self.state,reason=reason,snapshot=snapshot);self.state=ensure_state(self.store.load_state());self.save_label.setText("✓ Saved to SQLite");QTimer.singleShot(1800,lambda:self.save_label.setText("SQLite autosave ready"));self.refresh_projector()
    def refresh_all(self)->None:
        self.registration.refresh();self.traditional.refresh();self.modified.refresh();self.backup.refresh()
    def show_projector(self)->None:
        if self.stack.currentWidget() is self.modified:self.current_division="Modified"
        elif self.stack.currentWidget() is self.traditional:self.current_division="Traditional"
        self.state["raceType"]=self.current_division;self.save("projector-open",snapshot=False)
        if not self.projector:self.projector=ProjectorWindow(self)
        self.projector.render();self.projector.show();self.projector.raise_();self.projector.activateWindow()
    def refresh_projector(self)->None:
        if self.projector and self.projector.isVisible():self.projector.render()
    def project_saved_heat(self,division:str,saved_heat:dict[str,Any],next_heat:dict[str,Any]|None,total:int,runoff:dict[str,Any]|None)->None:
        if self.projector and self.projector.isVisible():self.projector.show_saved_heat_sequence(division,saved_heat,next_heat,total,runoff)
    def _startup_backup(self)->None:
        try:create_full_backup(self.store);from backup import prune_backups;prune_backups(self.store.backups_dir,30);self.save_label.setText("✓ Autosave + startup backup ready")
        except Exception:self.save_label.setText("SQLite autosave ready • make a portable backup soon")
    def closeEvent(self,event)->None:
        try:self.store.save_state(self.state,reason="application-close",snapshot=True);create_full_backup(self.store);self.store.close()
        except Exception:pass
        event.accept()


def main()->int:
    app=QApplication(sys.argv);app.setApplicationName("MNLT Derby Manager");window=MainWindow();window.show();return app.exec()

if __name__=="__main__":raise SystemExit(main())
