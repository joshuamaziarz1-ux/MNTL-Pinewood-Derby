"""Race-day fixes layered onto the v43 desktop alpha shell.

Keep fixes isolated while the desktop port is being validated so the locked
browser implementations remain untouched.
"""

from __future__ import annotations

from typing import Any

import app


def unresolved_trophy_ties(state: dict[str, Any], division: str) -> list[dict[str, Any]]:
    """Return only trophy ties that do not already have an on-track resolution."""
    bucket = app.race_bucket(state, division)
    rows = app.standings(app.race_racers(state, division), bucket.get("heats", []))
    saved = bucket.get("tieBreaks", {}) or {}
    unresolved: list[dict[str, Any]] = []
    for group in app.trophy_tie_groups(rows):
        racers = group["racers"]
        record = saved.get(app.group_key(racers))
        if not record or not isinstance(record.get("order"), list):
            unresolved.append(group)
            continue
        required = {str(r["id"]) for r in racers}
        restored = {str(rid) for rid in record["order"]}
        if required != restored or len(record["order"]) != len(racers):
            unresolved.append(group)
    return unresolved


def install() -> None:
    """Install desktop-only fixes before the main window is created."""
    base_projector_render = app.ProjectorWindow.render

    def projector_render(self):
        division = self.override_division or self.manager.current_division
        bucket = app.race_bucket(self.manager.state, division)
        runoff = bucket.get("runoff")
        heats = runoff.get("heats", []) if runoff else bucket.get("heats", [])
        if (
            self.override_heat is None
            and heats
            and not runoff
            and all(h.get("results") for h in heats)
            and not unresolved_trophy_ties(self.manager.state, division)
        ):
            self.render_final(division)
            return
        return base_projector_render(self)

    app.ProjectorWindow.render = projector_render

    base_results_refresh = app.DivisionRacePage.refresh_results

    def refresh_results(self):
        base_results_refresh(self)
        bucket = app.race_bucket(self.manager.state, self.division)
        heats = bucket.get("heats", [])
        complete = bool(heats) and all(h.get("results") for h in heats)
        if complete and not bucket.get("runoff") and not unresolved_trophy_ties(self.manager.state, self.division):
            self.start_runoff_btn.hide()
            self.results_notice.setText("✓ TROPHY PLACES FINAL — all trophy ties have been settled on the track.")

    app.DivisionRacePage.refresh_results = refresh_results
