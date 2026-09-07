#!/usr/bin/env python3
"""Check the arithmetic coverage of the small-support automorphism proof."""

from __future__ import annotations

import itertools
import json


ORDER = 43
MIN_DEGREE = 18
MAX_DEGREE = 24
R35_MINUS_ONE = 13


def equality_boundary_is_impossible(cycles: int) -> bool:
    """Check the complete-crossing versus empty-crossing boundary argument."""
    for statuses in itertools.product((0, 1), repeat=cycles):
        consistent = True
        for left in range(cycles):
            for right in range(left + 1, cycles):
                left_requires_complete = bool(statuses[left])
                right_requires_complete = bool(statuses[right])
                if left_requires_complete != right_requires_complete:
                    consistent = False
                    break
            if not consistent:
                break

        if not consistent:
            continue
        if all(statuses) or not any(statuses):
            # Complete or empty crossings combine with the same internal
            # status to make all moved vertices a clique or independent set.
            continue
        return False
    return True


def exclude_order_two(cycles: int) -> bool:
    fixed = ORDER - 2 * cycles
    edge_pair_max_degree = 1 + 2 * (cycles - 1) + R35_MINUS_ONE
    nonedge_pair_min_degree = fixed - R35_MINUS_ONE

    if cycles <= 2:
        return (
            edge_pair_max_degree < MIN_DEGREE
            and nonedge_pair_min_degree > MAX_DEGREE
        )

    if cycles == 3:
        edge_forces_complete_crossing = edge_pair_max_degree == MIN_DEGREE
        nonedge_forces_empty_crossing = nonedge_pair_min_degree == MAX_DEGREE
        mixed_status_impossible = (
            edge_forces_complete_crossing and nonedge_forces_empty_crossing
        )
        return mixed_status_impossible and equality_boundary_is_impossible(cycles)

    return False


def exclude_order_three(cycles: int) -> bool:
    fixed = ORDER - 3 * cycles
    triangle_cycle_max_degree = 2 + 3 * (cycles - 1) + 4
    independent_cycle_min_degree = fixed - 4
    if cycles <= 4:
        return (
            triangle_cycle_max_degree < MIN_DEGREE
            and independent_cycle_min_degree > MAX_DEGREE
        )
    if cycles == 5:
        triangle_forces_complete_crossing = (
            triangle_cycle_max_degree == MIN_DEGREE
        )
        independent_forces_empty_crossing = (
            independent_cycle_min_degree == MAX_DEGREE
        )
        mixed_status_impossible = (
            triangle_forces_complete_crossing
            and independent_forces_empty_crossing
        )
        return mixed_status_impossible and equality_boundary_is_impossible(cycles)
    return False


def exclude_prime_at_least_five(prime: int, cycles: int) -> bool:
    fixed = ORDER - prime * cycles
    return prime >= 5 and fixed > 2 * R35_MINUS_ONE


def main() -> None:
    excluded: list[dict[str, int]] = []

    for cycles in range(1, 4):
        if exclude_order_two(cycles):
            excluded.append({"prime": 2, "cycles": cycles})

    for cycles in range(1, 6):
        if exclude_order_three(cycles):
            excluded.append({"prime": 3, "cycles": cycles})

    for prime in (5, 7, 11, 13):
        for cycles in range(1, ORDER // prime + 1):
            if exclude_prime_at_least_five(prime, cycles):
                excluded.append({"prime": prime, "cycles": cycles})

    expected = {
        (2, 1),
        (2, 2),
        (2, 3),
        (3, 1),
        (3, 2),
        (3, 3),
        (3, 4),
        (3, 5),
        (5, 1),
        (5, 2),
        (5, 3),
        (7, 1),
        (7, 2),
        (11, 1),
        (13, 1),
    }
    actual = {(item["prime"], item["cycles"]) for item in excluded}
    if actual != expected:
        raise AssertionError(
            f"coverage mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )

    print(
        json.dumps(
            {
                "order": ORDER,
                "degree_interval": [MIN_DEGREE, MAX_DEGREE],
                "r_3_5_minus_one": R35_MINUS_ONE,
                "excluded_cycle_types": excluded,
                "excluded_count": len(excluded),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
