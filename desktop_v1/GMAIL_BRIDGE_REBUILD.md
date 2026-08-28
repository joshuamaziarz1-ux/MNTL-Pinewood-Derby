# Desktop v1 Gmail Bridge — Clean Rebuild Specification

## Decision

Do not patch the existing Desktop v1 Gmail bridge further. Rebuild it cleanly from scratch.

The browser v42 implementation is the behavioral source of truth and is currently known-good against the live Apps Script deployment.

Reference browser files:
- `v31-email-bridge.js`
- `v36-credentialless.js`
- `v37-review-draft.js`

## What to replace

Under `desktop_v1/`, inspect and remove the accumulated experimental Gmail bridge transports and dead code paths.

In particular, either delete or fully replace:
- `desktop_v1/gmail_bridge.py`
- `desktop_v1/qt_bridge.py`
- obsolete tests tied to failed transport experiments

Keep the stable integration points:
- Registration page
- SQLite Derby state
- local config storage
- automatic updater
- race engine
- projector
- backup/recovery

Do not modify locked browser/race snapshots.

## Architecture rule

Use ONE transport implementation only.

Do not keep a fallback stack of:
- requests
- urllib
- Qt WebEngine
- Qt Network
- iframe
- multiple parser variants

Choose the one transport that most faithfully reproduces the working v42 request and remove the others.

## Functional requirements

The rebuilt Desktop v1 Email Registration feature must:

1. Load the Apps Script Web App URL and Bridge Key from local Desktop config / imported v42 connection file.
2. Preserve the Bridge Key exactly.
3. Normalize only browser-only account-routing state that should not be sent by Desktop.
4. Match v42 request semantics to the Apps Script `/exec` endpoint.
5. Parse the actual Apps Script response format used by the deployed bridge.
6. Support manual **CHECK NOW**.
7. Check automatically about once per hour while Desktop v1 is open.
8. Show a clear Connected / error status.
9. List new SnapPages registrations waiting for review.
10. Let the operator review a signup before saving.
11. Prefill Registration fields.
12. Prevent duplicate imports using Gmail message ID and racer name.
13. Preserve source Gmail message ID.
14. Create a Gmail confirmation draft after saving if the deployed Apps Script supports `createDraft`.
15. Never expose the Bridge Key or private registration data in logs.

## Safe diagnostics

Future failures must be diagnosable without exposing secrets.

Safe to log/display:
- normalized URL host/path
- names of query parameters, not values
- Bridge Key length only
- HTTP status
- content type
- response byte length
- response classification: JSON / JSONP / HTML / empty
- callback/wrapper classification

Never log/display:
- Bridge Key contents
- emails
- phone numbers
- racer names
- registration payload contents

## Tests required

Automated tests must cover:
- v42 connection-file import
- exact key preservation
- URL normalization
- query encoding exactly once
- redirect behavior
- JSONP callback handling
- the exact response wrapper supported by the reference bridge
- duplicate filtering
- manual CHECK NOW state transitions
- draft-request construction
- all existing race/persistence/backup tests

Run:
- Python byte-compile checks
- full pytest suite
- Windows PyInstaller build
- existing Desktop v1 GitHub Actions workflow

## Acceptance criteria

Mocked tests alone are not enough.

Do not call this feature fixed until the user performs the live test and confirms:
- browser v42 remains **Connected**
- Desktop v1 says **Connected**
- Desktop v1 CHECK NOW returns the same waiting-registration state as v42
- no Gmail setting changes are required
- no manual secret copy/paste is needed after connection import
- review/save works
- duplicate prevention works
- Gmail draft creation works if the deployed Apps Script supports it
- updater publishes the rebuilt Desktop v1 app successfully

If live testing is not possible inside Codex because the Bridge Key is intentionally unavailable, finish the implementation/build and explicitly say **LIVE USER TEST REQUIRED** rather than claiming success.

## Safety / locked versions

Do not modify:
- `locked-v39-race-day`
- `locked-v40-modified`
- `locked-v42-browser`
- `locked-desktop-v1-foundation`

All rebuild work stays under `desktop_v1/`.

Never modify or delete live:
- `derby.db`
- `Photos`
- `Backups`

## Priority

Reliability first. Layout cleanup comes later.
