"""Race engine for the MNLT Derby Manager desktop app.

This is a direct Python port of the verified v38/v39 race-day rules:
- exactly four scored runs per racer
- every lane exactly once
- no empty lane slots with four or more racers
- balanced/optimized opponent exposure
- low-points scoring
- no hidden trophy tiebreakers
- progressive on-track runoffs
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

TROPHY_PLACES = 4


def _offset_score(n: int, offsets: Sequence[int]) -> tuple[int, int, int]:
    counts: Counter[int] = Counter()
    for i, a in enumerate(offsets):
        for j, b in enumerate(offsets):
            if i == j:
                continue
            counts[(b - a) % n] += 1
    vals = list(counts.values())
    return max(vals), len(counts), sum(v * v for v in vals)


def _better_score(a: tuple[int, int, int], b: tuple[int, int, int] | None) -> bool:
    if b is None:
        return True
    if a[0] != b[0]:
        return a[0] < b[0]
    if a[1] != b[1]:
        return a[1] > b[1]
    return a[2] < b[2]


def choose_offsets(n: int) -> list[int] | None:
    """Return the same optimized cyclic lane offsets used by v38."""
    if n < 4:
        return None
    best = [0, 1, 2, 3]
    best_score = _offset_score(n, best)
    for a in range(1, n - 2):
        for b in range(a + 1, n - 1):
            for c in range(b + 1, n):
                cur = [0, a, b, c]
                score = _offset_score(n, cur)
                if _better_score(score, best_score):
                    best = cur
                    best_score = score
                    if score[0] == 1:
                        return best
    return best


def build_fair_schedule(ids: Iterable[Any]) -> list[dict[str, Any]]:
    """Build a verified four-lane schedule.

    For 4+ racers there are N full heats. For 2-3 racers there are four
    heats and empty lanes are mathematically unavoidable.
    """
    ids = list(ids)
    n = len(ids)
    if n < 2:
        return []

    heats: list[dict[str, Any]] = []
    if n < 4:
        for h in range(4):
            lanes: list[Any | None] = [None, None, None, None]
            for i, racer_id in enumerate(ids):
                lanes[(i + h) % 4] = racer_id
            heats.append(
                {
                    "id": h + 1,
                    "round": None,
                    "lanes": lanes,
                    "results": [],
                    "schedule_engine": "PerfectN-v43",
                }
            )
        return heats

    offsets = choose_offsets(n)
    assert offsets is not None
    for h in range(n):
        heats.append(
            {
                "id": h + 1,
                "round": None,
                "lanes": [ids[(h + o) % n] for o in offsets],
                "results": [],
                "schedule_engine": "PerfectN-v43",
                "offsets": offsets[:],
            }
        )
    return heats


@dataclass(frozen=True)
class ScheduleVerification:
    ok: bool
    errors: tuple[str, ...]
    racers: int
    heats: int
    empty_slots: int
    min_unique_opponents: int
    max_unique_opponents: int
    max_pair_repeat: int
    expected_unique_opponents: int
    expected_max_repeat: int


def verify_schedule(heats: Sequence[dict[str, Any]], ids: Iterable[Any]) -> ScheduleVerification:
    ids = list(ids)
    heats = list(heats or [])
    n = len(ids)
    errors: list[str] = []

    if n < 2:
        return ScheduleVerification(False, ("At least 2 racers are required.",), n, len(heats), 0, 0, 0, 0, 0, 0)
    if len(set(ids)) != n:
        errors.append("Duplicate racer IDs found.")

    id_set = set(ids)
    expected_heats = 4 if n < 4 else n
    expected_heat_size = min(n, 4)
    if len(heats) != expected_heats:
        errors.append(f"Expected {expected_heats} heats but found {len(heats)}.")

    races = {racer_id: 0 for racer_id in ids}
    lane_counts = {racer_id: [0, 0, 0, 0] for racer_id in ids}
    opponents: dict[Any, Counter[Any]] = {racer_id: Counter() for racer_id in ids}
    bad_heat_count = duplicate_heat_count = unknown_count = empty_slots = 0

    for heat in heats:
        lanes = list(heat.get("lanes") or [None, None, None, None])[:4]
        lanes += [None] * (4 - len(lanes))
        active = [x for x in lanes if x not in (None, "")]
        empty_slots += max(0, 4 - len(active))
        if len(active) != expected_heat_size:
            bad_heat_count += 1
        if len(set(active)) != len(active):
            duplicate_heat_count += 1
        unknown_count += sum(1 for racer_id in active if racer_id not in id_set)

        for lane, racer_id in enumerate(lanes):
            if racer_id in (None, "") or racer_id not in id_set:
                continue
            races[racer_id] += 1
            lane_counts[racer_id][lane] += 1

        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                a, b = active[i], active[j]
                if a not in id_set or b not in id_set:
                    continue
                opponents[a][b] += 1
                opponents[b][a] += 1

    if bad_heat_count:
        errors.append(f"{bad_heat_count} heat(s) have the wrong number of racers.")
    if duplicate_heat_count:
        errors.append(f"{duplicate_heat_count} heat(s) contain the same racer more than once.")
    if unknown_count:
        errors.append("Unknown racer IDs are present in the schedule.")

    bad_races = [racer_id for racer_id in ids if races[racer_id] != 4]
    if bad_races:
        errors.append(f"{len(bad_races)} racer(s) do not have exactly 4 races.")
    bad_lanes = [racer_id for racer_id in ids if any(v != 1 for v in lane_counts[racer_id])]
    if bad_lanes:
        errors.append(f"{len(bad_lanes)} racer(s) do not use every lane exactly once.")
    if n >= 4 and empty_slots:
        errors.append(f"{empty_slots} empty lane slot(s) found; none are needed with {n} racers.")

    expected_unique = min(n - 1, 12)
    expected_encounters = 4 * (min(n, 4) - 1)
    expected_max_repeat = 4 if n <= 4 else 3 if n <= 6 else 2 if n <= 12 else 1
    min_unique = 10**9
    max_unique = -1
    max_pair_repeat = 0
    pattern: tuple[int, ...] | None = None
    pattern_mismatch = bad_encounter = 0

    for racer_id in ids:
        vals = sorted(opponents[racer_id].values(), reverse=True)
        unique = len(vals)
        encounters = sum(vals)
        max_rep = vals[0] if vals else 0
        min_unique = min(min_unique, unique)
        max_unique = max(max_unique, unique)
        max_pair_repeat = max(max_pair_repeat, max_rep)
        if encounters != expected_encounters:
            bad_encounter += 1
        current_pattern = tuple(vals)
        if pattern is None:
            pattern = current_pattern
        elif current_pattern != pattern:
            pattern_mismatch += 1

    if min_unique != expected_unique or max_unique != expected_unique:
        errors.append(f"Opponent variety is not optimal. Expected {expected_unique} unique opponents per racer.")
    if max_pair_repeat > expected_max_repeat:
        errors.append(f"Some opponents repeat {max_pair_repeat} times; expected no more than {expected_max_repeat}.")
    if bad_encounter:
        errors.append(f"{bad_encounter} racer(s) have the wrong number of opponent encounters.")
    if pattern_mismatch:
        errors.append("Opponent repeat pattern is not equal for every racer.")

    if min_unique == 10**9:
        min_unique = 0
    if max_unique < 0:
        max_unique = 0

    return ScheduleVerification(
        ok=not errors,
        errors=tuple(errors),
        racers=n,
        heats=len(heats),
        empty_slots=empty_slots,
        min_unique_opponents=min_unique,
        max_unique_opponents=max_unique,
        max_pair_repeat=max_pair_repeat,
        expected_unique_opponents=expected_unique,
        expected_max_repeat=expected_max_repeat,
    )


def heat_points(position_index: int, racer_count: int) -> float:
    """Return v39/v40 low-points score for a zero-based finish position."""
    if racer_count <= 1:
        return 1.0
    if racer_count == 2:
        return (1.0, 4.0)[position_index]
    if racer_count == 3:
        return (1.0, 2.5, 4.0)[position_index]
    return float(position_index + 1)


def save_finish_order(heat: dict[str, Any], finish_order: Sequence[Any]) -> None:
    active = [x for x in heat.get("lanes", []) if x not in (None, "")]
    if len(finish_order) != len(active) or set(finish_order) != set(active):
        raise ValueError("Finish order must contain every racer in this heat exactly once.")
    heat["results"] = [
        {"racer_id": racer_id, "position": i + 1, "points": heat_points(i, len(active))}
        for i, racer_id in enumerate(finish_order)
    ]


def standings(racers: Sequence[dict[str, Any]], heats: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    table: dict[Any, dict[str, Any]] = {
        r["id"]: {
            "id": r["id"],
            "name": r.get("name", ""),
            "number": r.get("number", 0),
            "car": r.get("car", ""),
            "points": 0.0,
            "races": 0,
            "wins": 0,
        }
        for r in racers
    }
    for heat in heats:
        for result in heat.get("results") or []:
            racer_id = result.get("racer_id", result.get("racerId"))
            row = table.get(racer_id)
            if not row:
                continue
            row["points"] += float(result.get("points", 0))
            row["races"] += 1
            if int(result.get("position", 0)) == 1:
                row["wins"] += 1
    return sorted(table.values(), key=lambda x: (x["points"], x.get("number", 0)))


def trophy_tie_groups(rows: Sequence[dict[str, Any]], trophy_places: int = TROPHY_PLACES) -> list[dict[str, Any]]:
    rows = list(rows)
    groups: list[dict[str, Any]] = []
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and abs(float(rows[j]["points"]) - float(rows[i]["points"])) < 1e-9:
            j += 1
        if j - i > 1 and i < trophy_places:
            groups.append({"start": i, "end": j - 1, "racers": rows[i:j]})
        i = j
    return groups


def score_blocks(rows: Sequence[dict[str, Any]]) -> list[list[Any]]:
    """Split runoff standings into equal-score blocks for progressive reruns."""
    rows = list(rows)
    blocks: list[list[Any]] = []
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and abs(float(rows[j]["points"]) - float(rows[i]["points"])) < 1e-9:
            j += 1
        blocks.append([r["id"] for r in rows[i:j]])
        i = j
    return blocks
