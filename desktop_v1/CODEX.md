# Codex Instructions — MNLT Derby Manager v43 Desktop

## Non-negotiable safety rules

1. Do not modify the locked browser milestones in place:
   - v42 browser backup branch: `locked-v42-browser`
   - v40 Modified milestone: `locked-v40-modified`
   - v39 Traditional milestone: `locked-v39-race-day`
2. Desktop work belongs under `desktop_v43/` unless a build workflow needs updating.
3. Preserve the proven race behavior from v38/v39/v40 exactly unless a new change is explicitly approved.
4. Never use racer number, wins, random choice, or hidden software logic to settle a trophy tie. Trophy ties are settled on the track.
5. With 4+ racers, no empty lanes are permitted in the scored race.
6. Every scored racer gets exactly 4 races and each lane exactly once.
7. Race Control must refuse an invalid schedule.
8. Data must live outside the executable. Never bundle or overwrite `derby.db`, `Photos`, or `Backups` during software updates.
9. Every data mutation must be committed to SQLite immediately.
10. Do not remove backup verification or automatic pre-restore backup behavior.

## Required checks before calling a desktop build stable

- `python -m py_compile app.py storage.py backup.py race_engine.py migration.py`
- `pytest -q`
- Windows PyInstaller build completes
- executable launches on Windows
- close/reopen resumes state
- full portable backup restores onto a clean second data directory
- v42 browser backup migration restores registrations and photos
- projector works on a second Windows display over HDMI
- full Traditional fake derby including trophy runoff passes
- full Modified fake derby including Exhibition and trophy runoff passes

Do not describe v43 as race-day stable until all of the above have passed.
