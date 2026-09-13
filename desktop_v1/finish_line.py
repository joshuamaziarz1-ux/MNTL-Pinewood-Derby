"""Read-only finish-line presentation, driven by Desktop race state.

Native Qt adaptation of MNLT_Derby_FinishLine_v2: lane colors, big countdown,
winner above three places. No sample data, random results, or race mutations.
"""
from __future__ import annotations

import copy
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

import app
from desktop_fixes import unresolved_trophy_ties

COLORS = ['#1487ff', '#ff2c35', '#ffc400', '#ff7a00']
COUNTDOWN_MS = 1500


def heat_payload(manager, division, heat, total, runoff=None):
    """Public display fields only; read current names/photos, preserve lane IDs."""
    racers = {str(r['id']): r for r in app.race_racers(manager.state, division)}
    regs = {str(r['id']): r for r in manager.state.get('registrations', [])}
    places = {str(r.get('racer_id', r.get('racerId'))): r.get('position')
              for r in heat.get('results', [])}
    entries = []
    for lane, rid in enumerate(heat.get('lanes', []), 1):
        if rid is None or rid == '':
            continue
        racer = racers.get(str(rid), {})
        reg = regs.get(str(racer.get('registrationId')), {})
        photo = manager.store.find_photo(racer.get('registrationId'), division)
        entries.append({'lane': lane, 'id': str(rid),
                        'name': reg.get('name', racer.get('name', '')),
                        'car': reg.get('tradCar' if division == 'Traditional' else 'modCar', racer.get('car', '')) or 'Unnamed Car',
                        'photo': str(photo) if photo else '', 'place': places.get(str(rid))})
    return {'division': division, 'heat': heat.get('id', 1), 'total': total,
            'runoff': runoff.get('attempt', 1) if runoff else None, 'entries': entries}


def current_payload(manager, division):
    bucket = app.race_bucket(manager.state, division)
    ro = bucket.get('runoff')
    heats = ro.get('heats', []) if ro else bucket.get('heats', [])
    if not heats:
        return {'division': division, 'heat': None, 'entries': [], 'mode': 'ready'}
    index = max(0, min(int(ro.get('current', 0) if ro else bucket.get('current', 0)), len(heats)-1))
    payload = heat_payload(manager, division, heats[index], len(heats), ro)
    payload['mode'] = 'results' if heats[index].get('results') else 'lineup'
    if ro and ro.get('completed'):
        payload['mode'] = 'tie'
    elif not ro and all(h.get('results') for h in heats):
        if unresolved_trophy_ties(manager.state, division):
            payload['mode'] = 'tie'
        else:
            payload['mode'] = 'final'
            rows = app.final_standings(copy.deepcopy(manager.state), division)[:4]
            fake = {'lanes': [r['id'] for r in rows], 'results': [
                {'racer_id': r['id'], 'position': i+1} for i, r in enumerate(rows)]}
            payload['entries'] = heat_payload(manager, division, fake, len(heats))['entries']
            for entry in payload['entries']:
                entry['lane'] = None  # final standings have no lane assignment
    return payload


class Photo(QLabel):
    def __init__(self, path):
        super().__init__()
        self.pix = QPixmap(path) if path else QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(50, 50)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setStyleSheet('background:#080d13;color:#9aa5b1;border:0;')
        self.update_photo()

    def update_photo(self):
        if self.pix.isNull():
            self.setText('CAR PHOTO')
        else:
            self.setPixmap(self.pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_photo()


class FinishLineWindow(QMainWindow):
    def __init__(self, manager):
        super().__init__(manager, Qt.Window)
        self.manager = manager
        self.setWindowTitle('MNLT Derby • Finish Line TV')
        self.resize(1280, 720)
        self.payload = {'division': 'Traditional', 'entries': [], 'heat': None}
        self.mode = 'ready'
        self.count = 3
        self.sound = True
        self.audio = ThreadPoolExecutor(max_workers=1, thread_name_prefix='finish-audio')
        self.count_timer = QTimer(self)
        self.count_timer.timeout.connect(self.tick)
        self.result_timer = QTimer(self)
        self.result_timer.setSingleShot(True)
        self.result_timer.timeout.connect(self.return_live)
        self.live_key = None
        self.setStyleSheet('QWidget{background:#05070a;color:#f7f8fa;} QLabel{border:0;}')
        self.draw()

    def label(self, text, size, color='#f7f8fa'):
        w = QLabel(str(text))
        w.setTextFormat(Qt.PlainText)
        w.setAlignment(Qt.AlignCenter)
        w.setWordWrap(True)
        w.setFont(QFont('Arial', size, QFont.Bold))
        w.setStyleSheet('color:'+color+';background:transparent;border:0;')
        return w

    def card(self, entry, winner=False, results=False):
        lane = entry.get('lane')
        color = '#ffc400' if winner else COLORS[(lane or 1)-1]
        card = QFrame()
        card.setMinimumSize(0, 0)
        card.setStyleSheet('QFrame{background:#0b1016;border:2px solid '+color+';}')
        layout = QHBoxLayout(card) if winner else QVBoxLayout(card)
        top = app.ordinal(entry['place']).upper() if results and entry.get('place') else 'LANE '+str(lane)
        layout.addWidget(self.label(top, 64 if winner else 23, color))
        layout.addWidget(Photo(entry['photo']), 2 if winner else 1)
        info = QVBoxLayout()
        info.addWidget(self.label(entry['car'], 28 if winner else 20, color))
        info.addWidget(self.label(entry['name'], 20 if winner else 15))
        if results and lane:
            info.addWidget(self.label('LANE '+str(lane), 13, '#9aa5b1'))
        layout.addLayout(info, 1 if winner else 0)
        return card

    def draw(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        header = QHBoxLayout()
        header.addWidget(self.label('MNLT DERBY', 21, '#ffc400'))
        title = 'FINAL RESULTS' if self.mode == 'final' else ('HEAT '+str(self.payload.get('heat')) if self.payload.get('heat') else 'TRACK READY')
        header.addWidget(self.label(title, 25), 1)
        division = self.payload['division'].upper()
        if self.payload.get('runoff'):
            division += ' • RUNOFF '+str(self.payload['runoff'])
        header.addWidget(self.label(division, 16))
        layout.addLayout(header)
        entries = self.payload['entries']
        if self.mode in ('results', 'final') and entries:
            ordered = sorted(entries, key=lambda e: e.get('place') or 99)
            layout.addWidget(self.card(ordered[0], True, True), 3)
            row = QHBoxLayout()
            for entry in ordered[1:]:
                row.addWidget(self.card(entry, results=True), 1)
            layout.addLayout(row, 2)
        elif self.mode == 'countdown':
            layout.addWidget(self.label(str(self.count) if self.count else 'GO!', 160, '#ffc400' if self.count else '#39e75f'), 1)
            row = QHBoxLayout()
            for entry in entries:
                row.addWidget(self.label('LANE '+str(entry['lane'])+'\n'+entry['car'], 18, COLORS[entry['lane']-1]), 1)
            layout.addLayout(row)
        elif self.mode == 'lineup' and entries:
            layout.addWidget(self.label('RACERS READY', 26))
            row = QHBoxLayout()
            for entry in entries:
                row.addWidget(self.card(entry), 1)
            layout.addLayout(row, 1)
        else:
            title, subtitle = {
                'racing': ('RACING…', 'Good luck racers!'),
                'tie': ('TROPHY RUNOFF', 'Trophy places will be settled on the track'),
            }.get(self.mode, ('TRACK READY', 'Waiting for the next heat'))
            layout.addStretch()
            layout.addWidget(self.label(title, 64, '#ffc400'))
            layout.addWidget(self.label(subtitle, 24))
            layout.addStretch()
        layout.addWidget(self.label('MNLT PINEWOOD DERBY', 12, '#9aa5b1'))
        previous = self.takeCentralWidget()
        self.setCentralWidget(root)
        if previous:
            previous.deleteLater()

    def stop_timers(self):
        self.count_timer.stop()
        self.result_timer.stop()

    def sync(self, force=False):
        payload = current_payload(self.manager, self.manager.current_division)
        key = json.dumps(payload, sort_keys=True)
        if force or key != self.live_key:
            self.stop_timers()
            self.live_key = key
            self.payload = payload
            self.mode = payload['mode']
            self.draw()

    def cue(self, hz, ms):
        if self.sound and sys.platform == 'win32':
            def play():
                try:
                    import winsound
                    winsound.Beep(hz, ms)
                except RuntimeError:
                    pass  # audio-device failure must not interrupt the race
            self.audio.submit(play)

    def start_countdown(self):
        if self.count_timer.isActive():
            return
        self.sync(force=True)
        if self.mode != 'lineup' or not self.payload['entries']:
            return
        page = self.manager.modified if self.manager.current_division == 'Modified' else self.manager.traditional
        heats, _ = page._control_heats()
        ro = page._runoff()
        racers = page._runoff_racers(ro) if ro else app.race_racers(self.manager.state, page.division)
        if not app.verify_schedule(heats, [r['id'] for r in racers]).ok:
            QMessageBox.warning(self.manager, 'Finish Line', 'Race Control must have a verified schedule before starting.')
            return
        self.mode = 'countdown'
        self.count = 3
        self.draw()
        self.cue(520, 130)
        self.count_timer.start(COUNTDOWN_MS)

    def tick(self):
        if self.count:
            self.count -= 1
            self.draw()
            self.cue(520 if self.count else 880, 130 if self.count else 320)
        else:
            self.count_timer.stop()
            self.mode = 'racing'
            self.draw()

    def saved(self, division, heat, total, runoff):
        self.stop_timers()
        self.live_key = json.dumps(current_payload(self.manager, self.manager.current_division), sort_keys=True)
        self.payload = heat_payload(self.manager, division, copy.deepcopy(heat), total, runoff)
        self.mode = 'results'
        self.draw()
        self.result_timer.start(6500)

    def return_live(self):
        self.sync(force=True)

    def closeEvent(self, event):
        self.stop_timers()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.showNormal()
        elif event.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        else:
            super().keyPressEvent(event)


def install(desktop_app):
    if getattr(desktop_app, '_finish_line_installed', False):
        return
    desktop_app._finish_line_installed = True
    base_init = desktop_app.MainWindow.__init__
    base_refresh = desktop_app.MainWindow.refresh_projector
    base_saved = desktop_app.MainWindow.project_saved_heat
    base_open = desktop_app.MainWindow.open_page
    base_close = desktop_app.MainWindow.closeEvent

    def get_window(manager):
        if manager.finish_line is None:
            manager.finish_line = FinishLineWindow(manager)
        return manager.finish_line

    def open_tv(manager, fullscreen=False):
        window = get_window(manager)
        window.sync()
        window.show()
        selected = manager.finish_screen.currentData()
        screens = manager.screen().virtualSiblings()
        if isinstance(selected, int) and selected < len(screens):
            target = screens[selected]
            window.windowHandle().setScreen(target)
            window.move(target.geometry().topLeft())
        if fullscreen:
            window.showFullScreen()
        window.raise_()

    def init(manager):
        base_init(manager)
        manager.finish_line = None
        nav = manager.centralWidget().layout().itemAt(1).layout().itemAt(0).layout()
        manager.finish_screen = QComboBox()
        screens = manager.screen().virtualSiblings()
        for i, screen in enumerate(screens):
            manager.finish_screen.addItem(f'TV: Display {i+1} ({screen.name()})', i)
        manager.finish_screen.setCurrentIndex(1 if len(screens)>1 else 0)
        nav.insertWidget(max(0, nav.count()-1), manager.finish_screen)
        button = QPushButton('Open Finish Line TV')
        button.clicked.connect(lambda: open_tv(manager))
        nav.insertWidget(max(0, nav.count()-1), button)
        full = QPushButton('TV Fullscreen')
        full.clicked.connect(lambda: open_tv(manager, True))
        nav.insertWidget(max(0, nav.count()-1), full)
        for page in (manager.traditional, manager.modified):
            controls = QHBoxLayout()
            start = QPushButton('START TV COUNTDOWN')
            cancel = QPushButton('TV LINEUP / CANCEL')
            sound = QCheckBox('Countdown sound')
            sound.setChecked(True)
            def countdown(p=page, s=sound):
                manager.current_division = p.division
                open_tv(manager)
                manager.finish_line.sound = s.isChecked()
                manager.finish_line.start_countdown()
            start.clicked.connect(lambda checked=False, fn=countdown: fn())
            cancel.clicked.connect(lambda checked=False: get_window(manager).sync(force=True))
            controls.addWidget(start)
            controls.addWidget(cancel)
            controls.addWidget(sound)
            page.control_tab.layout().addLayout(controls)

    def refresh(manager):
        base_refresh(manager)
        if getattr(manager, 'finish_line', None):
            manager.finish_line.sync()

    def saved(manager, division, heat, next_heat, total, runoff):
        base_saved(manager, division, heat, next_heat, total, runoff)
        if getattr(manager, 'finish_line', None):
            manager.finish_line.saved(division, heat, total, runoff)

    def open_page(manager, page):
        if page in (manager.traditional, manager.modified):
            manager.current_division = page.division
        base_open(manager, page)
        manager.refresh_projector()

    def close(manager, event):
        if getattr(manager, 'finish_line', None):
            manager.finish_line.close()
            manager.finish_line.audio.shutdown(wait=False, cancel_futures=True)
        base_close(manager, event)

    desktop_app.MainWindow.__init__ = init
    desktop_app.MainWindow.refresh_projector = refresh
    desktop_app.MainWindow.project_saved_heat = saved
    desktop_app.MainWindow.open_page = open_page
    desktop_app.MainWindow.closeEvent = close
