import random

from race_engine import build_fair_schedule, heat_points, save_finish_order, standings, trophy_tie_groups, verify_schedule


def test_every_field_size_2_to_100_is_verified():
    for n in range(2, 101):
        ids = list(range(1, n + 1))
        heats = build_fair_schedule(ids)
        result = verify_schedule(heats, ids)
        assert result.ok, (n, result.errors)
        assert result.heats == (4 if n < 4 else n)
        if n >= 4:
            assert result.empty_slots == 0


def test_9900_shuffled_schedules():
    rng = random.Random(20260826)
    for n in range(2, 101):
        ids = list(range(1, n + 1))
        for _ in range(100):
            rng.shuffle(ids)
            heats = build_fair_schedule(ids)
            result = verify_schedule(heats, ids)
            assert result.ok, (n, ids, result.errors)


def test_current_known_field_sizes_are_full_lane():
    for n in (5, 10):
        ids = list(range(1000, 1000 + n))
        result = verify_schedule(build_fair_schedule(ids), ids)
        assert result.ok
        assert result.empty_slots == 0


def test_random_complete_races_have_four_scores_per_racer():
    rng = random.Random(430043)
    for n in range(2, 101):
        ids = list(range(1, n + 1))
        racers = [{"id": i, "name": f"Racer {i}", "number": i} for i in ids]
        for _ in range(20):
            heats = build_fair_schedule(ids)
            for heat in heats:
                active = [x for x in heat["lanes"] if x is not None]
                rng.shuffle(active)
                save_finish_order(heat, active)
            rows = standings(racers, heats)
            assert len(rows) == n
            assert all(r["races"] == 4 for r in rows)
            assert all(4.0 <= r["points"] <= 16.0 for r in rows)


def test_trophy_tie_detection_includes_fourth_fifth_cutoff():
    rows = [
        {"id": 1, "points": 4.0},
        {"id": 2, "points": 5.0},
        {"id": 3, "points": 6.0},
        {"id": 4, "points": 7.0},
        {"id": 5, "points": 7.0},
        {"id": 6, "points": 8.0},
    ]
    groups = trophy_tie_groups(rows)
    assert len(groups) == 1
    assert groups[0]["start"] == 3
    assert groups[0]["end"] == 4


def test_tie_below_trophy_cutoff_does_not_force_runoff():
    rows = [
        {"id": 1, "points": 4.0},
        {"id": 2, "points": 5.0},
        {"id": 3, "points": 6.0},
        {"id": 4, "points": 7.0},
        {"id": 5, "points": 8.0},
        {"id": 6, "points": 9.0},
        {"id": 7, "points": 9.0},
    ]
    assert trophy_tie_groups(rows) == []


def test_corruption_is_rejected():
    for n in range(4, 101):
        ids = list(range(1, n + 1))
        heats = build_fair_schedule(ids)

        duplicate = [dict(h, lanes=list(h["lanes"])) for h in heats]
        duplicate[0]["lanes"][1] = duplicate[0]["lanes"][0]
        assert not verify_schedule(duplicate, ids).ok

        empty = [dict(h, lanes=list(h["lanes"])) for h in heats]
        empty[0]["lanes"][0] = None
        assert not verify_schedule(empty, ids).ok

        unknown = [dict(h, lanes=list(h["lanes"])) for h in heats]
        unknown[0]["lanes"][0] = 9999999
        assert not verify_schedule(unknown, ids).ok


def test_low_point_scoring_matches_browser_rules():
    assert [heat_points(i, 4) for i in range(4)] == [1.0, 2.0, 3.0, 4.0]
    assert [heat_points(i, 3) for i in range(3)] == [1.0, 2.5, 4.0]
    assert [heat_points(i, 2) for i in range(2)] == [1.0, 4.0]
