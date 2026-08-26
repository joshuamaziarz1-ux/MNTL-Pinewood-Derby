"""Packaged entry point for MNLT Derby Manager v43 Desktop.

Adds desktop-only migration helpers and validated race-day fixes without
changing the locked browser implementations.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

import app as desktop_app
from backup import create_full_backup
from migration import import_v42_backup
from storage import ensure_state
import desktop_fixes


desktop_fixes.install()

_original_backup_init = desktop_app.BackupPage.__init__


def _backup_init_with_migration(self, manager):
    _original_backup_init(self, manager)
    button = QPushButton("IMPORT v42 BROWSER FULL BACKUP")
    button.setMinimumHeight(46)

    def do_import():
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import v42 Browser Full Backup",
            "",
            "MNLT v42 Backup (*.json);;JSON Files (*.json)",
        )
        if not path:
            return
        if QMessageBox.question(
            self,
            "Import v42 Backup",
            "Import registrations, check-in, inspections, generated races, results, runoffs, and car photos from this v42 browser backup?\n\nThe current desktop data will remain recoverable in SQLite snapshots.",
        ) != QMessageBox.Yes:
            return
        try:
            counts = import_v42_backup(manager.store, path)
            manager.state = ensure_state(manager.store.load_state())
            create_full_backup(manager.store)
            manager.refresh_all()
            QMessageBox.information(
                self,
                "v42 Import Complete",
                "Imported successfully.\n\n"
                f"Registrations: {counts['registrations']}\n"
                f"Traditional heats: {counts['traditional_heats']}\n"
                f"Modified heats: {counts['modified_heats']}\n"
                f"Car photos: {counts['photos']}\n\n"
                "The desktop database is now independent of the browser.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "v42 Import Failed", str(exc))

    button.clicked.connect(do_import)
    layout = self.layout()
    if layout is not None:
        layout.insertWidget(3, button)


desktop_app.BackupPage.__init__ = _backup_init_with_migration


if __name__ == "__main__":
    raise SystemExit(desktop_app.main())
