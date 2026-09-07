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
    if cycles == 7:
        return bool(order_three_seven_cycle_audit()["excluded"])
    return False


def order_three_seven_cycle_audit() -> dict[str, object]:
    """Audit the counting contradiction for cycle type 3^7 1^22."""
    cycles = 7
    fixed = ORDER - 3 * cycles
    maximum_fixed_nonneighbors = 4
    minimum_fixed_neighbors = fixed - maximum_fixed_nonneighbors
    minimum_independent_pair_weight = 1
    minimum_intercycle_weight = (
        (cycles - 1) * minimum_independent_pair_weight
    )
    maximum_intercycle_weight = MAX_DEGREE - minimum_fixed_neighbors

    mixed_cases = []
    for triangle_cycles in range(1, cycles):
        independent_cycles = cycles - triangle_cycles
        triangle_degree_sum_lower = 12 * triangle_cycles
        triangle_degree_sum_upper = (
            4 * (triangle_cycles * (triangle_cycles - 1) // 2)
            + independent_cycles * triangle_cycles
        )
        mixed_cases.append(
            {
                "triangle_cycles": triangle_cycles,
                "independent_cycles": independent_cycles,
                "triangle_degree_sum_lower": triangle_degree_sum_lower,
                "triangle_degree_sum_upper": triangle_degree_sum_upper,
                "excluded": (
                    triangle_degree_sum_upper < triangle_degree_sum_lower
                ),
            }
        )

    # Equality of the lower and upper intercycle bounds forces every pair
    # weight to be one. The same degree bound then forces 18 fixed neighbors.
    pair_weights_forced_one = (
        minimum_intercycle_weight == maximum_intercycle_weight
    )
    intercycle_weight = minimum_intercycle_weight
    maximum_fixed_neighbors = MAX_DEGREE - intercycle_weight
    fixed_neighbors_forced = (
        minimum_fixed_neighbors == maximum_fixed_neighbors
    )
    fixed_neighbors = minimum_fixed_neighbors
    fixed_nonneighbors_per_cycle = fixed - fixed_neighbors
    total_fixed_cycle_nonneighbor_incidences = (
        cycles * fixed_nonneighbors_per_cycle
    )

    # Adjacent fixed vertices have at most 13 common neighbors. If their
    # missed-cycle signatures have union size u, then 3(7-u) <= 13.
    maximum_fully_common_cycles = R35_MINUS_ONE // 3
    minimum_signature_union_for_fixed_edge = (
        cycles - maximum_fully_common_cycles
    )

    # Fixed vertices missing at most one cycle form an independent set, so
    # there are at most four. Every other fixed vertex misses at least two.
    maximum_low_signature_vertices = 4
    minimum_incidence_total = (
        2 * (fixed - maximum_low_signature_vertices)
    )

    excluded = (
        all(case["excluded"] for case in mixed_cases)
        and pair_weights_forced_one
        and fixed_neighbors_forced
        and intercycle_weight == 6
        and fixed_neighbors == 18
        and fixed_nonneighbors_per_cycle == 4
        and minimum_signature_union_for_fixed_edge == 3
        and total_fixed_cycle_nonneighbor_incidences
        < minimum_incidence_total
    )

    return {
        "cycles": cycles,
        "fixed_vertices": fixed,
        "mixed_cases": mixed_cases,
        "independent_normal_form": {
            "minimum_fixed_neighbors_per_cycle": minimum_fixed_neighbors,
            "minimum_intercycle_weight_per_pair": (
                minimum_independent_pair_weight
            ),
            "minimum_intercycle_weight_per_cycle": (
                minimum_intercycle_weight
            ),
            "maximum_intercycle_weight_per_cycle": (
                maximum_intercycle_weight
            ),
            "pair_weights_forced_one": pair_weights_forced_one,
            "intercycle_weight_per_pair": 1,
            "intercycle_weight_per_cycle": intercycle_weight,
            "maximum_fixed_neighbors_per_cycle": maximum_fixed_neighbors,
            "fixed_neighbors_forced": fixed_neighbors_forced,
            "fixed_neighbors_per_cycle": fixed_neighbors,
            "fixed_nonneighbors_per_cycle": fixed_nonneighbors_per_cycle,
        },
        "fixed_signature_counting": {
            "total_nonneighbor_incidences": (
                total_fixed_cycle_nonneighbor_incidences
            ),
            "minimum_signature_union_for_fixed_edge": (
                minimum_signature_union_for_fixed_edge
            ),
            "maximum_vertices_missing_at_most_one_cycle": (
                maximum_low_signature_vertices
            ),
            "minimum_nonneighbor_incidences": minimum_incidence_total,
        },
        "excluded": excluded,
    }


def exclude_prime_at_least_five(prime: int, cycles: int) -> bool:
    fixed = ORDER - prime * cycles
    return prime >= 5 and fixed > 2 * R35_MINUS_ONE


def main() -> None:
    excluded: list[dict[str, int]] = []

    for cycles in range(1, 4):
        if exclude_order_two(cycles):
            excluded.append({"prime": 2, "cycles": cycles})

    for cycles in range(1, 8):
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
        (3, 7),
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
                "order_three_seven_cycle_audit": (
                    order_three_seven_cycle_audit()
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
