# Codex Instructions — MNLT Derby Manager Desktop v1

## Versioning
The Windows desktop edition restarts at **v1**. Do not continue the old browser v29-v42
number sequence for desktop releases.

The proven desktop alpha is preserved by branch:
- `locked-desktop-v1-foundation`

Locked browser milestones must not be modified:
- `locked-v42-browser`
- `locked-v40-modified`
- `locked-v39-race-day`

All current desktop feature work belongs under `desktop_v1/`.

## Current priority order
1. Restore Gmail/SnapPages registration bridge.
2. Verify projector parity with the approved crowd display.
3. Verify complete Traditional and Modified race workflows.
4. Verify save/close/reopen/portable restore again.
5. **Only then** clean up layout, spacing, compacted controls, and stretched panels.

Do not redesign the UI while the functional restoration work is still underway.

## Permanent updater contract
- The user-facing permanent launcher is `MNLT_Derby_Manager.exe`.
- The actual race manager is published as `MNLT_Derby_Manager_App.exe`.
- Automatic updates use the public `desktop-v1-latest` GitHub release.
- Every update must be accompanied by `desktop-v1-manifest.json` containing build ID and SHA-256.
- The launcher must verify SHA-256 before swapping the installed app.
- If update check/download fails and a prior app exists, open the prior app.
- Updates must never overwrite, remove, migrate, or bundle the live `derby.db`, `Photos`, or `Backups`.
- Do not add Derby data or Gmail secrets to update manifests or GitHub releases.
- Changes to the updater itself require extra caution because it is intended to be installed once and reused.

## Non-negotiable race safety
1. Preserve the proven v38/v39/v40 race behavior unless a change is explicitly approved.
2. Trophy ties are settled on the track. Never use racer number, wins, random choice,
   coin flip, or hidden software logic.
3. With 4+ scored racers, no empty lanes are permitted.
4. Every scored racer gets exactly 4 races and every lane exactly once.
5. Race Control must refuse a schedule that fails verification.
6. Exhibition Modified entries never affect official standings.
7. Regular standings points and runoff state stay separate.

## Data safety
1. Data lives outside the executable.
2. Never overwrite or bundle the live `derby.db`, `Photos`, or `Backups` during updates.
3. Every Derby-state mutation is committed to SQLite immediately.
4. Portable Derby backups must retain integrity verification and pre-restore safety backup.
5. Gmail bridge credentials are local machine configuration and must not be committed to GitHub.

## Required checks before Desktop v1 is called stable
- `python -m py_compile launcher.py app.py storage.py backup.py race_engine.py migration.py gmail_bridge.py desktop_fixes.py updater.py`
- `pytest -q`
- Windows PyInstaller build completes for both updater and race manager
- update release contains app + manifest
- updater downloads a new build and verifies its SHA-256
- updater opens prior build when update check fails
- executable launches on Windows
- existing SQLite registrations survive close/reopen
- portable backup restores correctly
- Gmail bridge connects to the existing Apps Script Web App
- new signup can be reviewed and saved without duplicate registration
- Gmail draft creation is tested if server-side bridge supports `createDraft`
- projector works on second Windows display over HDMI
- projector sequence works: Results → Up Next → Now Racing
- full Traditional fake derby including trophy runoff passes
- full Modified fake derby including Exhibition and trophy runoff passes

Do not call Desktop v1 stable until these checks pass.
