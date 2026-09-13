# Finish Line TV — Desktop v1

Native Qt adaptation of the MNLT_Derby_FinishLine_v2 prototype. Uses the same
blue/red/gold/orange lane colors, dark background, countdown, and large winner
above the remaining finish places. Uses the current Desktop registrations,
car names, saved Photos, heat lanes, and saved results. No sample racers or
random-result controls are installed.

## Use

1. Connect the TV over HDMI and select Windows **Extend** (Windows+P).
2. In Desktop, open the Traditional or Modified race page.
3. Select the TV display in the sidebar, then **Open Finish Line TV**.
4. Select **TV Fullscreen** if desired. Escape returns the TV to a window.
5. On the race page's **Race Control** tab, choose **START TV COUNTDOWN**.
   The countdown holds each of 3, 2, 1, and GO for 1.5 seconds.
6. Enter finish order and **SAVE RESULTS** using the existing race controls.
   Both open audience displays receive those saved results. The TV holds the
   winner layout for 6.5 seconds and then follows the current heat.

**TV LINEUP / CANCEL** cancels the countdown and returns to the current heat.
Heat/division changes also cancel any old countdown. Repeated start presses
do not restart it. Saved heats cannot start another countdown.

The projector remains a separate audience window. A laptop plus one HDMI TV
can show controls on the laptop and finish-line graphics on the TV. A separate
physical projector requires another display output. The projector window can
also be opened on the laptop for inspection.

Countdown tones use Windows system audio (winsound); check the laptop's audio
output/volume at the venue. The countdown is a visual/audio cue only. It does
not release the start gate, time the race, or read Arduino sensors. Result
entry remains manual in this first integration.

Final trophy display waits for the existing on-track tie resolution. Display
code never writes race results or changes schedules. Gmail is unchanged.

## Verification

Full Desktop pytest suite plus Qt launcher smoke test: separate TV window,
countdown, cancellation, heat changes, saved-results hold, sparse lanes,
Modified runoff context, unresolved trophy ties, and read-only public payload.
Windows build and live HDMI/audio verification are also required before calling
the integration race-day proven.
