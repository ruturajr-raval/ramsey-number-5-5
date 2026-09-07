#!/usr/bin/env python3
"""Small exhaustive checks for the independent orbit-CNF generator."""

from __future__ import annotations

import itertools
import unittest

from orbit_cnf import Formula, OrbitRamseyEncoding
from verify_branch_coverage import canonical_prefix, representative_branch, verify


def clause_satisfied(clause: tuple[int, ...], assignment: dict[int, bool]) -> bool:
    return any(
        assignment[abs(literal)] == (literal > 0)
        for literal in clause
    )


def base_clauses_satisfied(
    signatures: set[tuple[int, ...]], true_variables: set[int]
) -> bool:
    return all(
        any(variable not in true_variables for variable in signature)
        and any(variable in true_variables for variable in signature)
        for signature in signatures
    )


class OrbitEncodingTests(unittest.TestCase):
    def test_edge_variables_are_shift_invariant(self) -> None:
        encoding = OrbitRamseyEncoding(11, 3, 3, 3)
        for edge, variable in encoding.edge_variables.items():
            shifted = encoding.shifted_edge(edge, 1)
            self.assertEqual(variable, encoding.edge_variables[shifted])

    def test_c5_is_an_invariant_ramsey_3_3_graph(self) -> None:
        encoding = OrbitRamseyEncoding(5, 5, 1, 3)
        encoding.add_ramsey_clauses()
        self.assertEqual(2, encoding.edge_variable_count)

        valid_assignments = 0
        for values in itertools.product((False, True), repeat=2):
            true_variables = {
                variable
                for variable, value in enumerate(values, start=1)
                if value
            }
            adjacency = encoding.decode_primary_assignment(true_variables)
            has_triangle = encoding.has_homogeneous_set(adjacency, True)
            has_independent_three = encoding.has_homogeneous_set(
                adjacency, False
            )
            graph_is_valid = not has_triangle and not has_independent_three
            self.assertEqual(
                graph_is_valid,
                base_clauses_satisfied(
                    encoding.base_signatures, true_variables
                ),
            )
            if graph_is_valid:
                valid_assignments += 1
        self.assertEqual(2, valid_assignments)

    def test_r_3_3_at_order_six_has_no_invariant_model(self) -> None:
        encoding = OrbitRamseyEncoding(6, 2, 3, 3)
        encoding.add_ramsey_clauses()

        for values in itertools.product(
            (False, True), repeat=encoding.edge_variable_count
        ):
            true_variables = {
                variable
                for variable, value in enumerate(values, start=1)
                if value
            }
            adjacency = encoding.decode_primary_assignment(true_variables)
            graph_is_invalid = (
                encoding.has_homogeneous_set(adjacency, True)
                or encoding.has_homogeneous_set(adjacency, False)
            )
            self.assertTrue(graph_is_invalid)
            self.assertFalse(
                base_clauses_satisfied(
                    encoding.base_signatures, true_variables
                )
            )

    def test_and_gate_truth_table(self) -> None:
        formula = Formula(4)
        formula.add_and_gate(3, 1, 2)
        for left, right, output in itertools.product((False, True), repeat=3):
            assignment = {1: left, 2: right, 3: output}
            accepted = all(
                clause_satisfied(clause, assignment)
                for clause in formula.clauses
            )
            self.assertEqual(output == (left and right), accepted)

    def test_or_gate_truth_table(self) -> None:
        formula = Formula(4)
        formula.add_or_gate(3, 1, 2)
        for left, right, output in itertools.product((False, True), repeat=3):
            assignment = {1: left, 2: right, 3: output}
            accepted = all(
                clause_satisfied(clause, assignment)
                for clause in formula.clauses
            )
            self.assertEqual(output == (left or right), accepted)

    def test_cardinality_range_with_repeated_literals(self) -> None:
        try:
            from pysat.solvers import Cadical195
        except ImportError as error:
            self.fail(f"PySAT is required for semantic tests: {error}")

        formula = Formula(4)
        formula.add_cardinality_range([1, 1, 2, 3], 2, 3)
        with Cadical195(bootstrap_with=formula.clauses) as solver:
            for first, second, third in itertools.product(
                (False, True), repeat=3
            ):
                assumptions = [
                    variable if value else -variable
                    for variable, value in (
                        (1, first),
                        (2, second),
                        (3, third),
                    )
                ]
                weighted_sum = 2 * first + second + third
                self.assertEqual(
                    2 <= weighted_sum <= 3,
                    solver.solve(assumptions=assumptions),
                )

    def test_cardinality_ranges_exhaustively(self) -> None:
        try:
            from pysat.solvers import Cadical195
        except ImportError as error:
            self.fail(f"PySAT is required for semantic tests: {error}")

        literal_lists = (
            [1],
            [1, 1],
            [1, 2],
            [1, 1, 2],
            [1, 2, 2, 3, 3],
        )
        for literals in literal_lists:
            primary_count = max(literals)
            for lower in range(len(literals) + 1):
                for upper in range(lower, len(literals) + 1):
                    formula = Formula(primary_count + 1)
                    formula.add_cardinality_range(literals, lower, upper)
                    with Cadical195(
                        bootstrap_with=formula.clauses
                    ) as solver:
                        for values in itertools.product(
                            (False, True),
                            repeat=primary_count,
                        ):
                            assumptions = [
                                variable if value else -variable
                                for variable, value in enumerate(
                                    values,
                                    start=1,
                                )
                            ]
                            weighted_sum = sum(
                                values[literal - 1]
                                for literal in literals
                            )
                            self.assertEqual(
                                lower <= weighted_sum <= upper,
                                solver.solve(assumptions=assumptions),
                            )

    def test_root_prefix_is_canonical_under_cycle_relabeling(self) -> None:
        for pattern in itertools.product((False, True), repeat=6):
            adjacent = sum(pattern)
            self.assertEqual(
                (True,) * adjacent + (False,) * (6 - adjacent),
                canonical_prefix(pattern),
            )

    def test_four_branches_cover_all_six_cycle_patterns(self) -> None:
        result = verify(6)
        self.assertTrue(result["coverage_complete"])
        self.assertEqual(64, result["patterns_checked"])
        self.assertEqual([0, 1, 2, 3], result["solved_branches"])

        for pattern in itertools.product((False, True), repeat=6):
            branch, complemented = representative_branch(pattern)
            self.assertIn(branch, (0, 1, 2, 3))
            self.assertEqual(sum(pattern) > 3, complemented)


if __name__ == "__main__":
    unittest.main()
