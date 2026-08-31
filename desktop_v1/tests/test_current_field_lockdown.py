import random

from race_engine import build_fair_schedule, save_finish_order, standings, verify_schedule

TRADITIONAL_COUNT = 10
MODIFIED_COUNT = 5


def _field(count, start):
    ids = list(range(start, start + count))
    racers = [{"id": rid, "name": f"Race Day Racer {rid}", "number": i + 1} for i, rid in enumerate(ids)]
    return ids, racers


def test_current_2026_field_schedules_are_race_day_valid():
    for count, start in ((TRADITIONAL_COUNT, 1000), (MODIFIED_COUNT, 2000)):
        ids, _ = _field(count, start)
        heats = build_fair_schedule(ids)
        check = verify_schedule(heats, ids)
        assert check.ok, check.errors
        assert len(heats) == count
        assert check.empty_slots == 0
        assert all(len([r for r in h["lanes"] if r is not None]) == 4 for h in heats)


def test_current_2026_field_every_racer_runs_four_times_and_each_lane_once():
    for count, start in ((TRADITIONAL_COUNT, 1000), (MODIFIED_COUNT, 2000)):
        ids, _ = _field(count, start)
        heats = build_fair_schedule(ids)
        appearances = {rid: 0 for rid in ids}
        lane_counts = {rid: [0, 0, 0, 0] for rid in ids}
        for heat in heats:
            for lane, rid in enumerate(heat["lanes"]):
                appearances[rid] += 1
                lane_counts[rid][lane] += 1
        assert set(appearances.values()) == {4}
        assert all(counts == [1, 1, 1, 1] for counts in lane_counts.values())


def test_current_2026_fields_survive_2000_complete_random_races():
    rng = random.Random(20260914)
    for count, start in ((TRADITIONAL_COUNT, 1000), (MODIFIED_COUNT, 2000)):
        ids, racers = _field(count, start)
        for _ in range(1000):
            heats = build_fair_schedule(ids)
            for heat in heats:
                order = list(heat["lanes"])
                rng.shuffle(order)
                save_finish_order(heat, order)
            rows = standings(racers, heats)
            assert len(rows) == count
            assert all(r["races"] == 4 for r in rows)
            assert all(4.0 <= r["points"] <= 16.0 for r in rows)
            assert rows == sorted(rows, key=lambda r: (r["points"], r["number"]))


def test_bad_finish_entry_cannot_corrupt_current_field():
    ids, _ = _field(TRADITIONAL_COUNT, 1000)
    heat = build_fair_schedule(ids)[0]
    good = list(heat["lanes"])
    bad = good[:-1] + [good[0]]
    try:
        save_finish_order(heat, bad)
        raised = False
    except ValueError:
        raised = True
    assert raised
    assert heat["results"] == []
