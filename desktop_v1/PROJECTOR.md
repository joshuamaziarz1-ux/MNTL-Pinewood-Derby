# Desktop v1 Projector Contract

The projector is a crowd scoreboard, not a second operator screen.

## Required screens
- **Waiting:** MNLT Pinewood Derby, division, Race Starting Soon.
- **Now Racing:** Lane 1-4, large car photo, car name largest, racer name, heat number.
- **Heat Results:** the same four racers with clear 1st-4th finish positions.
- **Up Next:** next heat after results.
- **Trophy Runoff:** same clean race layout with an obvious TROPHY RUNOFF label.
- **Final Results:** only trophy places 1st-4th, car photo, car name, racer.
- **Modified Exhibition:** must be clearly marked Exhibition / Not Scored when used.

## Automatic crowd sequence
Saved heat:
1. Heat Results
2. about 6.5 seconds
3. Up Next
4. about 5 seconds
5. return to Now Racing

Duplicate save/update signals must never cause the sequence to skip.

## Do show
- division
- heat / runoff context
- lane
- car photo
- car name
- racer name
- finishing place when relevant

## Do not show
- racer number
- registration/contact information
- weight or inspection details
- schedule-engine details
- opponent history
- operator controls
- random stats or clutter

## Visual direction
Simple, clean, organized, high contrast, readable from across the room.
Dark background, white type, restrained gold accent, large photography, generous spacing.

## Race-day display
The projector must be a separate Windows window that can be dragged to a TV/projector
using Windows Extend mode over HDMI. The operator keeps Race Control on the laptop.

Layout polish is postponed until all functional projector states are verified.
