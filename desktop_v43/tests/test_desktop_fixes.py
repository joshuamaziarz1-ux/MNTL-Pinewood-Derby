from desktop_fixes import unresolved_trophy_ties
from app import group_key


def _state_with_trophy_tie():
    racers = [
        {"id": 1, "name": "A", "number": 1},
        {"id": 2, "name": "B", "number": 2},
        {"id": 3, "name": "C", "number": 3},
        {"id": 4, "name": "D", "number": 4},
        {"id": 5, "name": "E", "number": 5},
    ]
    # Direct result rows are enough for standings: racers 4 and 5 tie at the
    # 4th/5th trophy cutoff after four scored races each.
    totals = {1: 4.0, 2: 8.0, 3: 10.0, 4: 12.0, 5: 12.0}
    heats = []
    for h in range(4):
        results = []
        for rid in totals:
            results.append({"racer_id": rid, "position": 1, "points": totals[rid] / 4.0})
        heats.append({"id": h + 1, "lanes": [1, 2, 3, 4], "results": results})
    return {
        "registrations": [],
        "racers": racers,
        "heats": heats,
        "current": 3,
        "tieBreaks": {},
        "runoff": None,
        "modified": {"raceRacers": [], "heats": [], "tieBreaks": {}, "runoff": None},
    }


def test_resolved_trophy_tie_does_not_reopen():
    state = _state_with_trophy_tie()
    groups = unresolved_trophy_ties(state, "Traditional")
    assert len(groups) == 1
    group = groups[0]["racers"]
    state["tieBreaks"][group_key(group)] = {"order": [4, 5], "attempts": 1}
    assert unresolved_trophy_ties(state, "Traditional") == []


def test_invalid_saved_order_still_requires_runoff():
    state = _state_with_trophy_tie()
    group = unresolved_trophy_ties(state, "Traditional")[0]["racers"]
    state["tieBreaks"][group_key(group)] = {"order": [4, 999]}
    assert len(unresolved_trophy_ties(state, "Traditional")) == 1
