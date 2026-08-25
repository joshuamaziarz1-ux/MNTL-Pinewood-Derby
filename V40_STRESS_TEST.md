# MNLT Derby Manager v40 — Modified Division Stress Test

Tested August 25, 2026.

## v40 Modified race rules

- Modified entries are classified at inspection as Official Modified Race, Exhibition Only, or Not Cleared to Run.
- Any car allowed to run must pass the core safety checks: track safe, no flame/burning/track-damaging effect, and all parts/weights/batteries secure.
- Official Modified racers must also pass the head-to-head compatibility checks: fits/clears one lane, does not interfere with adjacent lanes, approved starting method, and clears the finish area/timer.
- Exhibition cars may run safely by themselves but receive no points and never affect Official Modified standings.
- The Official Modified race uses the verified v38/v39 4-lane schedule engine.
- Every Official racer receives exactly 4 scored races and uses Lane 1, Lane 2, Lane 3, and Lane 4 exactly once.
- With 4 or more Official racers, every heat is full. There are no empty lanes, including the first heat.
- With only 2 or 3 Official racers, empty lanes are mathematically unavoidable and are not scored as wins or byes.
- Race Control locks if schedule verification fails or if the Official racer list changes after the schedule is generated.
- Trophy ties affecting places 1 through 4 are settled by verified on-track runoff sets.
- Runoffs progressively resolve the field: racers separated by points keep their order and only racers still tied race again.
- No race number, wins count, random choice, or hidden software tiebreaker settles a trophy tie.

## Important state-isolation test/fix

During v40 development, the original manager's `S.modified.racers` array was identified as a registration mirror that can contain every Modified registration, including Exhibition entries. Using it directly as the Official race roster could cause later registration edits to pollute a generated Official race.

That design was rejected before release. Final v40 uses a separate `S.modified.raceRacers` snapshot for the Official Modified race. Exhibition and registration records remain outside the scored race roster.

## Automated tests completed

### Schedule structure

- 49,500 shuffled schedule tests across field sizes 2 through 100 (500 registration orders for every field size).
- 100,000 additional shuffled schedule tests with a 5-racer Modified field, matching the current Modified signup count visible during development.
- Every tested racer received exactly 4 races and every lane exactly once.
- Every tested field with 4 or more racers had 0 empty lane slots, including the opening heat.

Result: all 149,500 schedule tests passed.

### Classification / no-show / Exhibition filtering

- 100,000 randomized 11-registration states were tested with combinations of checked in / not checked in, safety pass / fail, Official / Exhibition / blocked / unclassified.
- Only checked-in, safety-cleared, Official-classified racers were admitted to the scored schedule.
- Exhibition entries never entered Official standings.

Result: all 100,000 classification/filter tests passed.

### Full race scoring

- 100,000 complete randomized Official Modified races across field sizes 2 through 100.
- 100,000 additional complete randomized races with a 5-racer Modified field.
- All racers received exactly 4 scored results and standings completed without race-count failures.

Result: all 200,000 full-race simulations passed.

### Progressive trophy runoffs

- 200,000 randomized progressive runoff resolutions with starting tie groups of 2 through 20 racers.
- Every runoff used the same verified 4-race/every-lane-once scheduling rules.
- Every original tied racer appeared exactly once in the final resolved order.
- Only still-tied score blocks advanced to another runoff set.

Result: all 200,000 runoff simulations passed.

### Corrupted schedule rejection

- 396 explicit corrupted schedules were tested across field sizes 2 through 100.
- Corruptions included duplicate racer in a heat, missing racer/empty slot, unknown racer ID, and missing heat.

Result: all 396 corrupt schedules were rejected by the verification rules.

## Total

649,896 automated Modified schedule, classification, complete-race, runoff, and corruption scenarios/checks were completed on the v40 design.

No failure was found in the final tested race logic.

## Version

Modified candidate: `v40.html`

v39 remains frozen as the locked Traditional race-day stable version on branch `locked-v39-race-day`. v40 does not modify the saved v39 race-day build.
