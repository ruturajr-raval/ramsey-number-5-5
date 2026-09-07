#!/usr/bin/env python3
"""Focused tests for the independent c8 formula reference."""

from __future__ import annotations

import itertools
import unittest

from verify_c8_formula_semantics import (
    EXPECTED_BRANCHES,
    ReferenceFormula,
    branch_units,
    build_degree_template,
    build_edge_orbits,
    build_ramsey_signatures,
    build_triangle_body,
    exception_count,
    normalize_branch,
    normalized_branch_counts,
    shifted_edge,
    structure_bounds,
)
from verify_c8_t4_formula_semantics import add_t4_matrix_structure


def satisfiable(
    clauses: list[tuple[int, ...]],
    assumptions: list[int],
) -> bool:
    assignment = {abs(literal): literal > 0 for literal in assumptions}

    def search(values: dict[int, bool]) -> bool:
        values = values.copy()
        while True:
            unit = None
            for clause in clauses:
                satisfied_clause = False
                unassigned = []
                for literal in clause:
                    variable = abs(literal)
                    if variable in values:
                        if values[variable] == (literal > 0):
                            satisfied_clause = True
                            break
                    else:
                        unassigned.append(literal)
                if satisfied_clause:
                    continue
                if not unassigned:
                    return False
                if len(unassigned) == 1:
                    unit = unassigned[0]
                    break
            if unit is None:
                break
            variable = abs(unit)
            required = unit > 0
            if variable in values and values[variable] != required:
                return False
            values[variable] = required

        for clause in clauses:
            if not any(
                abs(literal) in values
                and values[abs(literal)] == (literal > 0)
                for literal in clause
            ):
                variable = next(
                    abs(literal)
                    for literal in clause
                    if abs(literal) not in values
                )
                for value in (False, True):
                    branch = values.copy()
                    branch[variable] = value
                    if search(branch):
                        return True
                return False
        return True

    return search(assignment)


class C8FormulaSemanticsTests(unittest.TestCase):
    def test_signed_cardinality_reference_is_exact(self) -> None:
        formula = ReferenceFormula(4)
        formula.add_cardinality_range([1, -2, 3], 1, 2)

        for first, second, third in itertools.product(
            (False, True),
            repeat=3,
        ):
            assumptions = [
                variable if value else -variable
                for variable, value in (
                    (1, first),
                    (2, second),
                    (3, third),
                )
            ]
            expected = 1 <= first + (not second) + third <= 2
            self.assertEqual(
                expected,
                satisfiable(formula.clauses, assumptions),
            )

    def test_normalization_covers_exactly_eight_branches(self) -> None:
        counts = normalized_branch_counts()
        self.assertEqual(set(EXPECTED_BRANCHES), set(counts))
        self.assertEqual(2142, sum(counts.values()))
        self.assertEqual(
            {
                (2, 0, 0): 56,
                (2, 1, 0): 112,
                (2, 0, 1): 336,
                (3, 0, 0): 112,
                (3, 1, 0): 336,
                (3, 0, 1): 560,
                (4, 0, 0): 70,
                (4, 1, 0): 560,
            },
            dict(counts),
        )

        triangles = (True, True, True, True, False, False, False, False)
        root = (False, False, False, False, False, True, True, True)
        self.assertEqual(1, exception_count(triangles, root))
        self.assertEqual((4, 1, 0), normalize_branch(triangles, root))

    def test_edge_orbit_reference_is_shift_invariant(self) -> None:
        edge_variables = build_edge_orbits()
        self.assertEqual(415, max(edge_variables.values()))
        self.assertEqual(43 * 42 // 2, len(edge_variables))
        for edge, variable in edge_variables.items():
            self.assertEqual(
                variable,
                edge_variables[shifted_edge(edge, 1)],
            )

    def test_structure_bounds_are_the_derived_integer_bounds(self) -> None:
        self.assertEqual(
            (4, 28, 2, 20, 24, 10, 14, 0, 4),
            tuple(structure_bounds(2).__dict__.values()),
        )
        self.assertEqual(
            (1, 31, 0, 24, 25, 8, 9, 4, 5),
            tuple(structure_bounds(3).__dict__.values()),
        )
        self.assertEqual(
            (0, 32, 0, 24, 24, 6, 6, 6, 6),
            tuple(structure_bounds(4).__dict__.values()),
        )

    def test_full_reference_construction_counts_without_artifacts(self) -> None:
        edge_variables = build_edge_orbits()
        signatures = build_ramsey_signatures(edge_variables)
        self.assertEqual(328438, len(signatures))

        degree_template = build_degree_template(edge_variables)
        expected = {
            2: (76728, 223810, 880702),
            3: (76440, 222976, 879868),
            4: (76195, 222258, 879150),
        }
        for triangles, (
            variables,
            body_clauses,
            total_clauses,
        ) in expected.items():
            body = build_triangle_body(
                degree_template,
                edge_variables,
                triangles,
            )
            self.assertEqual(variables, body.next_variable - 1)
            self.assertEqual(body_clauses, len(body.clauses))
            self.assertEqual(
                total_clauses,
                2 * len(signatures) + body_clauses + 16,
            )

        units = branch_units(edge_variables, (4, 1, 0))
        self.assertEqual(16, len(units))
        self.assertTrue(all(len(unit) == 1 for unit in units))

    def test_t4_split_reference_counts_without_artifacts(self) -> None:
        edge_variables = build_edge_orbits()
        signatures = build_ramsey_signatures(edge_variables)
        degree_template = build_degree_template(edge_variables)

        expected = {
            False: (78411, 229431, 886323),
            True: (78411, 229450, 886342),
        }
        for exclude_zero, (
            variables,
            body_clauses,
            total_clauses,
        ) in expected.items():
            body = build_triangle_body(
                degree_template,
                edge_variables,
                4,
            )
            add_t4_matrix_structure(
                body,
                edge_variables,
                "two-c4",
                exclude_zero,
            )
            self.assertEqual(variables, body.next_variable - 1)
            self.assertEqual(body_clauses, len(body.clauses))
            self.assertEqual(
                total_clauses,
                2 * len(signatures) + body_clauses + 16,
            )


if __name__ == "__main__":
    unittest.main()
