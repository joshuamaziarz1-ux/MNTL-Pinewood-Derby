# MNLT Derby Manager Desktop v1

This is the clean version-number restart for the Windows desktop edition.

## Proven foundation kept from the desktop alpha
- no browser dependency for race-day operation
- local SQLite database with immediate autosave
- startup and close backups
- portable full-backup ZIP files with SHA-256 integrity checks
- v42 browser-backup import
- Traditional and Modified race engines
- verified scheduling, scoring, and on-track trophy runoffs
- real car photo files stored outside the executable
- separate audience projector window for HDMI / extended desktop

## Permanent updater
The Desktop v1 user-facing icon is now a small permanent launcher named:

`MNLT_Derby_Manager.exe`

It does not contain or edit Derby race data. On launch it:
1. checks the public `desktop-v1-latest` GitHub release manifest,
2. downloads a newer `MNLT_Derby_Manager_App.exe` only when the build changes,
3. verifies the app's SHA-256 hash before replacing the installed program,
4. keeps the previous app build during the swap,
5. launches the newest verified app,
6. opens the last installed app normally when the internet is unavailable.

The downloaded app lives under the existing local data root in the `Program` subfolder.
The Derby database, Photos, and Backups remain separate and are never replaced by an app update.

After the permanent updater is installed once, normal Desktop v1 changes are published to the
stable `desktop-v1-latest` update channel by GitHub Actions. The user should not need to
manually download and replace the Derby Manager for ordinary updates.

## Desktop v1 restoration priorities
1. Gmail / SnapPages registration bridge
   - Check Now + hourly checks
   - review signup before saving
   - preserve source Gmail message ID
   - create confirmation Gmail draft when the Apps Script bridge supports it
2. Projector parity
   - Waiting
   - Now Racing
   - Heat Results
   - Up Next
   - Trophy Runoff
   - Final Results
   - Traditional + Modified
3. Full workflow shakedown and backup/restore test

## Layout rule
Do not spend time polishing spacing, widths, stretched panels, or compact controls yet.
Functional parity and reliability come first. Layout cleanup is the final phase after
Registration, Gmail bridge, Traditional, Modified, backups, and projector all work together.

The browser milestones remain locked as emergency fallbacks.
