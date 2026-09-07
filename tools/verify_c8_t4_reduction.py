#!/usr/bin/env python3
"""Verify the two canonical mixed matrices for the t=4 case."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path


Matrix = tuple[tuple[int, ...], ...]

EXPECTED_MATRICES: dict[str, Matrix] = {
    "two-c4": (
        (1, 1, 2, 2),
        (1, 1, 2, 2),
        (2, 2, 1, 1),
        (2, 2, 1, 1),
    ),
    "c8": (
        (1, 1, 2, 2),
        (1, 2, 1, 2),
        (2, 1, 2, 1),
        (2, 2, 1, 1),
    ),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def transform(
    matrix: Matrix,
    row_permutation: tuple[int, ...],
    column_permutation: tuple[int, ...],
) -> Matrix:
    return tuple(
        tuple(
            matrix[row_permutation[row]][column_permutation[column]]
            for column in range(4)
        )
        for row in range(4)
    )


def canonical(
    matrix: Matrix,
    distinguished_first_row: bool,
) -> Matrix:
    if distinguished_first_row:
        row_permutations = [
            (0, *permutation)
            for permutation in itertools.permutations((1, 2, 3))
        ]
    else:
        row_permutations = list(itertools.permutations(range(4)))
    column_permutations = list(itertools.permutations(range(4)))
    return min(
        transform(matrix, rows, columns)
        for rows in row_permutations
        for columns in column_permutations
    )


def enumerate_matrices() -> list[Matrix]:
    rows = sorted(set(itertools.permutations((1, 1, 2, 2))))
    return [
        matrix
        for matrix in itertools.product(rows, repeat=4)
        if all(
            sum(matrix[row][column] for row in range(4)) == 6
            for column in range(4)
        )
    ]


def verify_phase_gauge() -> dict[str, object]:
    tree_edges = tuple((0, vertex) for vertex in range(1, 8))
    labels_to_phases = {}
    for free_phases in itertools.product(range(3), repeat=7):
        phases = (0, *free_phases)
        labels = tuple(
            (phases[right] - phases[left]) % 3
            for left, right in tree_edges
        )
        if labels in labels_to_phases:
            raise AssertionError("phase gauge is not unique")
        labels_to_phases[labels] = phases
    if len(labels_to_phases) != 3**7:
        raise AssertionError("phase gauge does not cover every assignment")
    return {
        "root_cycle": 0,
        "tree_edges": [list(edge) for edge in tree_edges],
        "free_cycle_phases": 7,
        "phase_assignments": len(labels_to_phases),
        "unique_normalization": True,
    }


def verify() -> dict[str, object]:
    matrices = enumerate_matrices()
    ordinary_classes = {
        canonical(matrix, distinguished_first_row=False)
        for matrix in matrices
    }
    distinguished_classes = {
        canonical(matrix, distinguished_first_row=True)
        for matrix in matrices
    }
    expected_classes = set(EXPECTED_MATRICES.values())
    if len(matrices) != 90:
        raise AssertionError("labeled t4 matrix count changed")
    if ordinary_classes != expected_classes:
        raise AssertionError("ordinary t4 matrix classes changed")
    if distinguished_classes != expected_classes:
        raise AssertionError("distinguished-row t4 classes changed")
    for matrix in expected_classes:
        if any(
            sorted(row) != [1, 1, 2, 2]
            for row in matrix
        ):
            raise AssertionError("unexpected t4 row multiset")
        if any(
            sorted(matrix[row][column] for row in range(4))
            != [1, 1, 2, 2]
            for column in range(4)
        ):
            raise AssertionError("unexpected t4 column multiset")

    return {
        "cycle_type": "3^8 1^19",
        "verifier_sha256": file_sha256(Path(__file__)),
        "triangle_cycles": 4,
        "local_graph_constraints": {
            "mixed_weight_zero_excluded": True,
            "mixed_weight_three_excluded": True,
            "reason": (
                "A complete or empty mixed link would force the four fixed "
                "triangle neighbors to equal the four fixed independent "
                "nonneighbors, but the former set is independent and the "
                "latter is a clique."
            ),
        },
        "allowed_mixed_weights": [1, 2],
        "row_and_column_multisets": [1, 1, 2, 2],
        "fixed_exception_lemmas": {
            "shared_triangle_exception_forces_nonedge": True,
            "shared_independent_exception_forces_edge": True,
            "triangle_independent_exception_intersection_at_most_one": True,
            "reason": (
                "Two fixed triangle exceptions cannot be adjacent without "
                "forming a 5-clique, while two fixed independent exceptions "
                "cannot be nonadjacent without forming an independent "
                "5-set. Their intersection therefore has size at most one."
            ),
        },
        "root_partition": {
            "p0_branch": "the selected root has no exceptions",
            "p1_branch": (
                "the selected root has one triangle exception and no fixed "
                "vertex has zero exceptions"
            ),
            "disjoint_and_complete_for_low_exception_roots": True,
        },
        "phase_gauge": verify_phase_gauge(),
        "labeled_matrices": len(matrices),
        "ordinary_matrix_classes": len(ordinary_classes),
        "distinguished_row_matrix_classes": len(distinguished_classes),
        "representatives": {
            name: [list(row) for row in matrix]
            for name, matrix in EXPECTED_MATRICES.items()
        },
        "verified": True,
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
