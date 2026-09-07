#!/usr/bin/env python3
"""Independently rebuild and compare the four strengthened t4 CNFs."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from verify_c8_formula_semantics import (
    CYCLES,
    ORDER,
    PRIME,
    ReferenceFormula,
    branch_units,
    build_degree_template,
    build_edge_orbits,
    build_ramsey_signatures,
    build_triangle_body,
    compare_cnf,
    cycle_fixed_literals,
    expected_cnf_lines,
    file_sha256,
    require_inside_repository,
)
from verify_c8_t4_reduction import EXPECTED_MATRICES


SplitBranch = tuple[int, str]
EXPECTED_SPLIT_BRANCHES: tuple[SplitBranch, ...] = (
    (0, "two-c4"),
    (0, "c8"),
    (1, "two-c4"),
    (1, "c8"),
)


def between_cycle_literals(
    edge_variables: dict[tuple[int, int], int],
    left_cycle: int,
    right_cycle: int,
) -> list[int]:
    left = left_cycle * PRIME
    right_start = right_cycle * PRIME
    return [
        edge_variables[(left, right_start + offset)]
        for offset in range(PRIME)
    ]


def fixed_exception_literals(
    edge_variables: dict[tuple[int, int], int],
    fixed_vertex: int,
) -> list[int]:
    offset = fixed_vertex - PRIME * CYCLES
    return [
        (
            cycle_fixed_literals(edge_variables, cycle)[offset]
            if cycle < 4
            else -cycle_fixed_literals(edge_variables, cycle)[offset]
        )
        for cycle in range(CYCLES)
    ]


def add_t4_matrix_structure(
    formula: ReferenceFormula,
    edge_variables: dict[tuple[int, int], int],
    matrix_type: str,
    exclude_zero_fixed_signatures: bool,
) -> None:
    matrix = EXPECTED_MATRICES[matrix_type]
    for triangle_cycle, row in enumerate(matrix):
        for independent_index, weight in enumerate(row):
            literals = between_cycle_literals(
                edge_variables,
                triangle_cycle,
                4 + independent_index,
            )
            formula.add_cardinality_range(literals, weight, weight)

    for other_triangle in range(1, 4):
        literals = between_cycle_literals(
            edge_variables,
            0,
            other_triangle,
        )
        for index, literal in enumerate(literals):
            formula.add_clause((literal if index else -literal,))
    for independent_index, weight in enumerate(matrix[0]):
        literals = between_cycle_literals(
            edge_variables,
            0,
            4 + independent_index,
        )
        for index, literal in enumerate(literals):
            present = index == 0 if weight == 1 else index != 0
            formula.add_clause((literal if present else -literal,))

    fixed_vertices = range(PRIME * CYCLES, ORDER)
    fixed_by_cycle = [
        cycle_fixed_literals(edge_variables, cycle)
        for cycle in range(CYCLES)
    ]
    for left, right in itertools.combinations(fixed_vertices, 2):
        left_offset = left - PRIME * CYCLES
        right_offset = right - PRIME * CYCLES
        fixed_edge = edge_variables[(left, right)]
        for cycle in range(CYCLES):
            left_exception = fixed_by_cycle[cycle][left_offset]
            right_exception = fixed_by_cycle[cycle][right_offset]
            forced_edge = -fixed_edge
            if cycle >= 4:
                left_exception = -left_exception
                right_exception = -right_exception
                forced_edge = fixed_edge
            formula.add_clause(
                (
                    -left_exception,
                    -right_exception,
                    forced_edge,
                )
            )

    for triangle_cycle in range(4):
        triangle_fixed = fixed_by_cycle[triangle_cycle]
        for independent_cycle in range(4, 8):
            independent_fixed = fixed_by_cycle[independent_cycle]
            intersections = []
            for triangle_literal, independent_literal in zip(
                triangle_fixed,
                independent_fixed,
            ):
                conjunction = formula.new_variable()
                formula.add_and_gate(
                    conjunction,
                    triangle_literal,
                    -independent_literal,
                )
                intersections.append(conjunction)
            formula.add_cardinality_range(intersections, 0, 1)

    if exclude_zero_fixed_signatures:
        for fixed_vertex in fixed_vertices:
            formula.add_clause(
                fixed_exception_literals(
                    edge_variables,
                    fixed_vertex,
                )
            )


def split_stem(root_adjacent_triangles: int, matrix_type: str) -> str:
    return (
        f"p3-c8-t4-p{root_adjacent_triangles}-z0-"
        f"m{matrix_type}"
    )


def verify_directory(directory: Path) -> dict[str, object]:
    directory = require_inside_repository(directory)
    edge_variables = build_edge_orbits()
    signatures = build_ramsey_signatures(edge_variables)
    degree_template = build_degree_template(edge_variables)
    results = []

    expected_names = {
        f"{split_stem(root, matrix)}.json"
        for root, matrix in EXPECTED_SPLIT_BRANCHES
    }
    observed_names = {
        path.name for path in directory.glob("p3-c8-t4-p*-z0-m*.json")
    }
    if observed_names != expected_names:
        raise AssertionError("t4 split metadata set mismatch")

    for root_adjacent_triangles, matrix_type in EXPECTED_SPLIT_BRANCHES:
        body = build_triangle_body(
            degree_template,
            edge_variables,
            triangle_cycles=4,
        )
        exclude_zero = root_adjacent_triangles == 1
        add_t4_matrix_structure(
            body,
            edge_variables,
            matrix_type,
            exclude_zero,
        )
        stem = split_stem(root_adjacent_triangles, matrix_type)
        metadata_path = require_inside_repository(
            directory / f"{stem}.json"
        )
        cnf_path = require_inside_repository(directory / f"{stem}.cnf")
        metadata = json.loads(
            metadata_path.read_text(encoding="ascii")
        )
        expected_fields = {
            "order": 43,
            "prime": 3,
            "cycles": 8,
            "fixed": 19,
            "homogeneous_size": 5,
            "degree_bounds": [18, 24],
            "edge_orbit_variables": 415,
            "variables": body.next_variable - 1,
            "base_signatures": len(signatures),
            "extra_clauses": len(body.clauses) + 16,
            "clauses": 2 * len(signatures) + len(body.clauses) + 16,
            "root_adjacent_cycles": None,
            "triangle_cycles": 4,
            "independent_cycles": 4,
            "root_adjacent_triangle_cycles": root_adjacent_triangles,
            "root_nonadjacent_independent_cycles": 0,
            "order_three_eight_structure": True,
            "t4_mixed_matrix": matrix_type,
            "exclude_zero_fixed_signatures": exclude_zero,
        }
        for field, expected in expected_fields.items():
            if metadata.get(field) != expected:
                raise AssertionError(
                    f"{stem}: metadata mismatch for {field}"
                )

        units = branch_units(
            edge_variables,
            (4, root_adjacent_triangles, 0),
        )
        byte_count, digest = compare_cnf(
            cnf_path,
            expected_cnf_lines(signatures, body, units),
        )
        if metadata.get("bytes") != byte_count:
            raise AssertionError(f"{stem}: byte count mismatch")
        if metadata.get("sha256") != digest:
            raise AssertionError(f"{stem}: SHA-256 mismatch")
        results.append(
            {
                "root_adjacent_triangle_cycles": (
                    root_adjacent_triangles
                ),
                "matrix_type": matrix_type,
                "exclude_zero_fixed_signatures": exclude_zero,
                "cnf": cnf_path.name,
                "bytes": byte_count,
                "sha256": digest,
                "variables": body.next_variable - 1,
                "clauses": expected_fields["clauses"],
                "semantic_match": True,
            }
        )

    return {
        "cycle_type": "3^8 1^19",
        "scope": "strengthened t=4 certificate branches",
        "generator_sha256": file_sha256(
            Path(__file__).resolve().parents[1] / "src/orbit_cnf.py"
        ),
        "reference_verifier_sha256": file_sha256(Path(__file__)),
        "branches": results,
        "all_semantically_identical": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = verify_directory(args.directory)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = require_inside_repository(args.output, must_exist=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="ascii", newline="\n") as handle:
            handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
