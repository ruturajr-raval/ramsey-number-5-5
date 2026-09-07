#!/usr/bin/env python3
"""Small exhaustive checks for the independent orbit-CNF generator."""

from __future__ import annotations

import itertools
import unittest

from orbit_cnf import (
    T4_MIXED_MATRICES,
    Formula,
    OrbitRamseyEncoding,
)
from verify_branch_coverage import canonical_prefix, representative_branch, verify
from verify_c8_branch_coverage import (
    EXPECTED_BRANCHES,
    exception_count,
    representative_branch as c8_representative_branch,
    verify as verify_c8,
)
from verify_c8_t4_reduction import verify as verify_c8_t4


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

    def test_cardinality_range_with_signed_literals(self) -> None:
        try:
            from pysat.solvers import Cadical195
        except ImportError as error:
            self.fail(f"PySAT is required for semantic tests: {error}")

        formula = Formula(4)
        formula.add_cardinality_range([1, -2, 3], 1, 2)
        with Cadical195(bootstrap_with=formula.clauses) as solver:
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
                signed_sum = first + (not second) + third
                self.assertEqual(
                    1 <= signed_sum <= 2,
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

    def test_order_three_cycle_type_units(self) -> None:
        encoding = OrbitRamseyEncoding(13, 3, 4, 3)
        encoding.add_order_three_cycle_types(2)
        expected = [
            (encoding.cycle_internal_variable(cycle),)
            if cycle < 2
            else (-encoding.cycle_internal_variable(cycle),)
            for cycle in range(4)
        ]
        self.assertEqual(expected, encoding.formula.clauses)

    def test_typed_root_signature_units(self) -> None:
        encoding = OrbitRamseyEncoding(13, 3, 4, 3)
        encoding.add_typed_root_signature(
            triangle_cycles=2,
            adjacent_triangle_cycles=1,
            nonadjacent_independent_cycles=1,
        )
        expected_signs = (True, False, False, True)
        expected = [
            (
                encoding.root_cycle_variable(cycle)
                if adjacent
                else -encoding.root_cycle_variable(cycle),
            )
            for cycle, adjacent in enumerate(expected_signs)
        ]
        self.assertEqual(expected, encoding.formula.clauses)

    def test_c8_structural_constraints_accept_forced_t4_profile(self) -> None:
        try:
            from pysat.solvers import Cadical195
        except ImportError as error:
            self.fail(f"PySAT is required for semantic tests: {error}")

        encoding = OrbitRamseyEncoding(43, 3, 8)
        encoding.add_order_three_eight_structure(4)

        primary_assignment = {
            variable: False
            for variable in range(1, encoding.edge_variable_count + 1)
        }
        for cycle in range(8):
            fixed_literals = encoding.cycle_fixed_literals(cycle)
            for index, variable in enumerate(fixed_literals):
                primary_assignment[variable] = (
                    index < 4 if cycle < 4 else index >= 4
                )

        for left, right in itertools.combinations(range(4), 2):
            for variable in encoding.between_cycle_literals(left, right)[:2]:
                primary_assignment[variable] = True
        for left, right in itertools.combinations(range(4, 8), 2):
            variable = encoding.between_cycle_literals(left, right)[0]
            primary_assignment[variable] = True

        mixed_pairs = list(itertools.product(range(4), range(4, 8)))
        for left, right in mixed_pairs:
            take = 2 if (left + right) % 2 == 0 else 1
            for variable in encoding.between_cycle_literals(left, right)[:take]:
                primary_assignment[variable] = True

        assumptions = [
            variable if value else -variable
            for variable, value in primary_assignment.items()
        ]
        with Cadical195(bootstrap_with=encoding.formula.clauses) as solver:
            self.assertTrue(solver.solve(assumptions=assumptions))

            first_triangle_fixed = encoding.cycle_fixed_literals(0)[0]
            violating = [
                literal
                for literal in assumptions
                if abs(literal) != first_triangle_fixed
            ]
            violating.append(-first_triangle_fixed)
            self.assertFalse(solver.solve(assumptions=violating))

    def test_c8_t4_matrix_reduction_accepts_a_valid_profile(self) -> None:
        try:
            from pysat.solvers import Cadical195
        except ImportError as error:
            self.fail(f"PySAT is required for semantic tests: {error}")

        encoding = OrbitRamseyEncoding(43, 3, 8)
        encoding.add_order_three_eight_structure(4)
        encoding.add_order_three_eight_t4_matrix(
            "two-c4",
            exclude_zero_fixed_signatures=False,
        )

        assignment = {
            variable: False
            for variable in range(1, encoding.edge_variable_count + 1)
        }
        triangle_sets = [
            set(range(4 * cycle, 4 * cycle + 4))
            for cycle in range(4)
        ]
        independent_sets = [
            {column + 4 * row for row in range(4)}
            for column in range(4)
        ]
        for cycle, offsets in enumerate(triangle_sets):
            for offset, variable in enumerate(
                encoding.cycle_fixed_literals(cycle)
            ):
                assignment[variable] = offset in offsets
        for index, offsets in enumerate(independent_sets):
            cycle = 4 + index
            for offset, variable in enumerate(
                encoding.cycle_fixed_literals(cycle)
            ):
                assignment[variable] = offset not in offsets

        for left, right in itertools.combinations(range(4), 2):
            literals = encoding.between_cycle_literals(left, right)
            selected = (1, 2) if left == 0 else (0, 1)
            for index in selected:
                assignment[literals[index]] = True
        for left, right in itertools.combinations(range(4, 8), 2):
            literals = encoding.between_cycle_literals(left, right)
            assignment[literals[0]] = True
        for triangle, row in enumerate(T4_MIXED_MATRICES["two-c4"]):
            for independent, weight in enumerate(row):
                literals = encoding.between_cycle_literals(
                    triangle,
                    4 + independent,
                )
                selected = (0,) if weight == 1 else (1, 2)
                for index in selected:
                    assignment[literals[index]] = True

        fixed_start = 24
        for offsets in independent_sets:
            vertices = [fixed_start + offset for offset in offsets]
            for left, right in itertools.combinations(vertices, 2):
                edge = (
                    (left, right)
                    if left < right
                    else (right, left)
                )
                assignment[encoding.edge_variables[edge]] = True

        assumptions = [
            variable if value else -variable
            for variable, value in assignment.items()
        ]
        with Cadical195(bootstrap_with=encoding.formula.clauses) as solver:
            self.assertTrue(solver.solve(assumptions=assumptions))

        no_zero = OrbitRamseyEncoding(43, 3, 8)
        no_zero.add_order_three_eight_structure(4)
        no_zero.add_order_three_eight_t4_matrix(
            "two-c4",
            exclude_zero_fixed_signatures=True,
        )
        with Cadical195(bootstrap_with=no_zero.formula.clauses) as solver:
            self.assertFalse(solver.solve(assumptions=assumptions))

    def test_c8_eight_branches_cover_all_low_exception_roots(self) -> None:
        result = verify_c8()
        self.assertTrue(result["arithmetic_coverage_complete"])
        self.assertEqual(
            2304,
            result["low_exception_configurations_total"],
        )
        self.assertEqual(162, result["elementary_configurations"])
        self.assertEqual(2142, result["certificate_configurations"])
        self.assertTrue(result["elementary_audit"]["verified"])
        self.assertEqual(
            [list(branch) for branch in EXPECTED_BRANCHES],
            result["solved_branches"],
        )
        self.assertEqual(1, result["guaranteed_root_exception_upper"])

        triangles = (True, True, True, True, False, False, False, False)
        root = (False, False, False, False, False, True, True, True)
        self.assertEqual(1, exception_count(triangles, root))
        branch, _ = c8_representative_branch(triangles, root)
        self.assertEqual((4, 1, 0), branch)

    def test_c8_t4_matrix_reduction_has_two_classes(self) -> None:
        result = verify_c8_t4()
        self.assertTrue(result["verified"])
        self.assertEqual(90, result["labeled_matrices"])
        self.assertEqual(2, result["ordinary_matrix_classes"])
        self.assertEqual(
            2,
            result["distinguished_row_matrix_classes"],
        )
        self.assertEqual(
            3**7,
            result["phase_gauge"]["phase_assignments"],
        )
        self.assertTrue(
            result["phase_gauge"]["unique_normalization"],
        )
        self.assertTrue(
            result["fixed_exception_lemmas"][
                "triangle_independent_exception_intersection_at_most_one"
            ],
        )
        self.assertTrue(
            result["root_partition"][
                "disjoint_and_complete_for_low_exception_roots"
            ],
        )


if __name__ == "__main__":
    unittest.main()
