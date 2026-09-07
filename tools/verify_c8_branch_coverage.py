#!/usr/bin/env python3
"""Verify the normalized branch cover for cycle type 3^8 1^19."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path


Branch = tuple[int, int, int]

EXPECTED_BRANCHES: tuple[Branch, ...] = (
    (2, 0, 0),
    (2, 1, 0),
    (2, 0, 1),
    (3, 0, 0),
    (3, 1, 0),
    (3, 0, 1),
    (4, 0, 0),
    (4, 1, 0),
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_elementary_internal_type_counts() -> dict[str, object]:
    fixed_vertices = 19
    maximum_exceptions_per_cycle = 4

    one_triangle_upper = 7 * maximum_exceptions_per_cycle
    one_triangle_lower = 2 * (fixed_vertices - 4)
    if one_triangle_upper >= one_triangle_lower:
        raise AssertionError("one-triangle incidence contradiction failed")

    all_independent_upper = 8 * maximum_exceptions_per_cycle
    feasible_low_counts = []
    for zero_signatures in range(fixed_vertices + 1):
        for one_signatures in range(
            fixed_vertices - zero_signatures + 1
        ):
            if zero_signatures + one_signatures > 4:
                continue
            incidence_lower = (
                one_signatures
                + 2
                * (
                    fixed_vertices
                    - zero_signatures
                    - one_signatures
                )
            )
            if incidence_lower <= all_independent_upper:
                feasible_low_counts.append(
                    (zero_signatures, one_signatures)
                )
    minimum_zero_signatures = min(
        zero_signatures
        for zero_signatures, _ in feasible_low_counts
    )
    if minimum_zero_signatures < 2:
        raise AssertionError("all-independent zero-signature bound failed")
    if fixed_vertices - 2 <= 13:
        raise AssertionError("R(5,3) contradiction no longer applies")

    return {
        "excluded_triangle_cycle_counts": [0, 1, 7, 8],
        "one_triangle_incidence_upper": one_triangle_upper,
        "one_triangle_incidence_lower": one_triangle_lower,
        "all_independent_incidence_upper": all_independent_upper,
        "minimum_all_independent_zero_signatures": (
            minimum_zero_signatures
        ),
        "remaining_fixed_vertices": fixed_vertices - 2,
        "r_5_3_minus_one": 13,
        "verified": True,
    }


def exception_count(
    triangle_pattern: tuple[bool, ...],
    root_adjacency: tuple[bool, ...],
) -> int:
    return sum(
        adjacent if triangle else not adjacent
        for triangle, adjacent in zip(
            triangle_pattern,
            root_adjacency,
        )
    )


def representative_branch(
    triangle_pattern: tuple[bool, ...],
    root_adjacency: tuple[bool, ...],
) -> tuple[Branch, bool]:
    if len(triangle_pattern) != 8 or len(root_adjacency) != 8:
        raise ValueError("expected eight moved cycles")
    if exception_count(triangle_pattern, root_adjacency) > 1:
        raise ValueError("root has more than one exceptional incidence")

    triangles = sum(triangle_pattern)
    if triangles in (0, 1, 7, 8):
        raise ValueError("elementary cases are not certificate branches")
    complemented = triangles > 4

    if complemented:
        triangle_pattern = tuple(not value for value in triangle_pattern)
        root_adjacency = tuple(not value for value in root_adjacency)

    triangles = sum(triangle_pattern)
    adjacent_triangles = sum(
        triangle and adjacent
        for triangle, adjacent in zip(
            triangle_pattern,
            root_adjacency,
        )
    )
    nonadjacent_independent = sum(
        (not triangle) and (not adjacent)
        for triangle, adjacent in zip(
            triangle_pattern,
            root_adjacency,
        )
    )

    branch = (
        triangles,
        adjacent_triangles,
        nonadjacent_independent,
    )
    if branch == (4, 0, 1):
        branch = (4, 1, 0)
        complemented = not complemented
    if branch not in EXPECTED_BRANCHES:
        raise AssertionError(f"unexpected normalized branch: {branch}")
    return branch, complemented


def verify() -> dict[str, object]:
    rows = []
    branch_counts: Counter[Branch] = Counter()
    selected_configurations = 0
    elementary_configurations = 0
    elementary_audit = verify_elementary_internal_type_counts()

    for triangle_pattern in itertools.product((False, True), repeat=8):
        triangles = sum(triangle_pattern)
        if triangles in (0, 1, 7, 8):
            elementary_configurations += 9
            continue
        for root_adjacency in itertools.product((False, True), repeat=8):
            exceptions = exception_count(
                triangle_pattern,
                root_adjacency,
            )
            if exceptions > 1:
                continue

            branch, complemented = representative_branch(
                triangle_pattern,
                root_adjacency,
            )
            branch_counts[branch] += 1
            selected_configurations += 1
            rows.append(
                {
                    "triangle_pattern": "".join(
                        "T" if value else "I"
                        for value in triangle_pattern
                    ),
                    "root_adjacency": "".join(
                        "1" if value else "0"
                        for value in root_adjacency
                    ),
                    "exceptions": exceptions,
                    "complemented": complemented,
                    "representative_branch": list(branch),
                }
            )

    observed = tuple(sorted(branch_counts))
    if observed != tuple(sorted(EXPECTED_BRANCHES)):
        raise AssertionError(
            f"branch mismatch: observed={observed}, "
            f"expected={EXPECTED_BRANCHES}"
        )

    exception_incidence_upper = 8 * 4
    fixed_vertices = 19
    guaranteed_root_exception_upper = (
        exception_incidence_upper // fixed_vertices
    )
    if guaranteed_root_exception_upper != 1:
        raise AssertionError("pigeonhole root bound changed")

    total_configurations = (
        selected_configurations + elementary_configurations
    )
    if total_configurations != 256 * 9:
        raise AssertionError("low-exception configuration count changed")

    arithmetic_coverage_complete = (
        elementary_audit["verified"]
        and total_configurations == 256 * 9
    )
    return {
        "cycle_type": "3^8 1^19",
        "verifier_sha256": file_sha256(Path(__file__)),
        "audit_scope": (
            "Arithmetic enumeration of the normalized root branches, "
            "conditional on the documented graph-theoretic lemmas."
        ),
        "graph_theoretic_assumptions": [
            "The internal-type counts 0, 1, 7, and 8 are excluded.",
            "Complementation reduces the remaining counts to 2, 3, and 4.",
            "Every moved cycle has at most four fixed-vertex exceptions.",
        ],
        "elementary_audit": elementary_audit,
        "certificate_internal_type_counts": [2, 3, 4, 5, 6],
        "exception_incidence_upper": exception_incidence_upper,
        "fixed_vertices": fixed_vertices,
        "guaranteed_root_exception_upper": (
            guaranteed_root_exception_upper
        ),
        "low_exception_configurations_total": total_configurations,
        "elementary_configurations": elementary_configurations,
        "certificate_configurations": selected_configurations,
        "solved_branches": [list(branch) for branch in EXPECTED_BRANCHES],
        "branch_counts": {
            "-".join(map(str, branch)): branch_counts[branch]
            for branch in EXPECTED_BRANCHES
        },
        "arithmetic_coverage_complete": arithmetic_coverage_complete,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = verify()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open(
            "w",
            encoding="ascii",
            newline="\n",
        ) as handle:
            handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
