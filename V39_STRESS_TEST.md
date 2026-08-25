# MNLT Derby Manager v39 — Race-Day Stress Test

Tested August 25, 2026.

## Final race rules enforced by v39

- Traditional racers receive exactly 4 scored races.
- Every racer uses Lane 1, Lane 2, Lane 3, and Lane 4 exactly once.
- With 4 or more racers, every heat uses all 4 lanes. There are no empty lanes, including the opening heat.
- With only 2 or 3 racers, empty lanes are unavoidable and are not treated as wins or scored as byes.
- The schedule verifier checks heat count, racer count, duplicate racers in a heat, unknown racers, races per racer, lane usage, empty lanes, opponent variety, opponent repeat balance, and total opponent encounters.
- Race Control locks if the generated schedule fails verification.
- Trophy ties affecting places 1 through 4 require a track runoff.
- No race number, number of wins, random choice, or hidden software tiebreaker settles a trophy tie.
- A runoff gives each tied racer 4 actual runs and each lane once.
- If a runoff partially breaks a tie, racers already separated keep their order and only racers still tied race another verified runoff set.

## Automated stress tests completed

### Main schedule structure

- 99 canonical field sizes tested: 2 through 100 racers.
- 19,800 shuffled schedule tests: 200 different registration orders for every field size from 2 through 100.
- 97 explicit no-empty-lane tests: every field size from 4 through 100, checking every heat and the first heat specifically.
- Current registered Traditional field tested directly: 10 Traditional racers.
- 10,000 additional shuffled schedules using the current registered Traditional field.

Result: all schedule verification tests passed.

Current 10-racer field result:
- 10 heats
- 4 racers in every heat
- 0 empty lanes
- every racer runs 4 times
- every racer uses every lane once
- every racer meets all 9 other racers
- no opponent is faced more than twice

### Full race simulations

- 19,800 complete randomized races across field sizes 2 through 100.
- 10,000 complete randomized races using the current registered Traditional field.

Result: all racers received exactly 4 scored results, all standings calculations completed, and no race-count failures occurred.

### Trophy-tie detection

- Explicit tests included a tie for 4th/5th, a tie outside the trophy cutoff, and a tie spanning multiple trophy places.
- 500,000 randomized standings/tie-pattern tests checked that every tie intersecting places 1 through 4 is caught and ties entirely below 4th are not incorrectly forced into a trophy runoff.

Result: 500,003 tie-detection cases passed.

### Runoff system

The first v39 runoff design repeated the entire tied group until every racer had a unique runoff score. Stress testing showed that a large tie group could require too many repeat sets. That design was rejected before release.

The final v39 design progressively resolves the field: after each runoff set, racers separated by points keep that order and only racers still tied race again.

Final runoff stress tests:
- 100,000 randomized progressive runoff resolutions with starting tie groups of 2 through 20 racers.
- 100,000 two-racer runoff series.
- 100,000 three-racer runoff series.
- 100,000 four-racer runoff series.
- 50,000 five-racer runoff series.
- 50,000 ten-racer runoff series.

Result: all 500,000 runoff scenarios resolved correctly without a hidden tiebreaker.

Observed runoff behavior in the stress tests:
- 2-racer ties averaged 1.601 runoff sets.
- 3-racer ties averaged 1.503 runoff sets.
- 4-racer ties averaged 1.900 runoff sets.
- 5-racer ties averaged 2.331 runoff sets.
- 10-racer artificial all-tie groups averaged 5.232 progressive runoff sets.

The large artificial tie tests are intentionally much harsher than a normal Pinewood Derby trophy tie.

## Total

More than 1,059,800 automated schedule, race, tie-detection, and runoff test scenarios/checks were completed on the final v39 race logic.

No failure was found in the final tested logic.

## Version

Race-day candidate: `v39.html`

v37 remains preserved as the earlier locked application version. v38 remains the intermediate verified schedule-engine test version. v39 adds the final progressive trophy-runoff system.