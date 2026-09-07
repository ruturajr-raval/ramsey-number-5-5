#!/usr/bin/env python3
"""Generate Ramsey CNFs for a prescribed prime-order automorphism."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path


T4_MIXED_MATRICES = {
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


class Formula:
    def __init__(self, first_free_variable: int) -> None:
        self.next_variable = first_free_variable
        self.clauses: list[tuple[int, ...]] = []

    def new_variable(self) -> int:
        variable = self.next_variable
        self.next_variable += 1
        return variable

    def add_clause(self, literals: list[int] | tuple[int, ...]) -> None:
        values = set(literals)
        if any(-literal in values for literal in values):
            return
        self.clauses.append(
            tuple(sorted(values, key=lambda literal: (abs(literal), literal < 0)))
        )

    def add_and_gate(self, output: int, left: int, right: int) -> None:
        self.add_clause((-output, left))
        self.add_clause((-output, right))
        self.add_clause((output, -left, -right))

    def add_or_gate(self, output: int, left: int, right: int) -> None:
        self.add_clause((-left, output))
        self.add_clause((-right, output))
        self.add_clause((left, right, -output))

    def add_cardinality_range(
        self, literals: list[int], lower: int, upper: int
    ) -> None:
        """Encode lower <= sum(literals) <= upper with an exact DP counter."""
        count = len(literals)
        lower = max(0, lower)
        upper = min(count, upper)
        if lower > upper:
            self.add_clause(())
            return

        threshold = upper + 1
        previous = [self.new_variable() for _ in range(threshold + 1)]
        self.add_clause((previous[0],))
        for level in range(1, threshold + 1):
            self.add_clause((-previous[level],))

        for literal in literals:
            current = [self.new_variable() for _ in range(threshold + 1)]
            self.add_clause((current[0],))
            for level in range(1, threshold + 1):
                conjunction = self.new_variable()
                self.add_and_gate(
                    conjunction,
                    literal,
                    previous[level - 1],
                )
                self.add_or_gate(
                    current[level],
                    previous[level],
                    conjunction,
                )
            previous = current

        if lower:
            self.add_clause((previous[lower],))
        self.add_clause((-previous[upper + 1],))


class OrbitRamseyEncoding:
    def __init__(
        self,
        order: int,
        prime: int,
        cycles: int,
        homogeneous_size: int = 5,
    ) -> None:
        if prime < 2:
            raise ValueError("prime must be at least 2")
        if cycles < 1 or prime * cycles > order:
            raise ValueError("invalid cycle count")
        if homogeneous_size < 2 or homogeneous_size > order:
            raise ValueError("invalid homogeneous-set size")

        self.order = order
        self.prime = prime
        self.cycles = cycles
        self.fixed = order - prime * cycles
        self.homogeneous_size = homogeneous_size
        self.edge_variables = self._build_edge_orbits()
        self.edge_variable_count = max(self.edge_variables.values())
        self.formula = Formula(self.edge_variable_count + 1)
        self.base_signatures: set[tuple[int, ...]] = set()

    def shifted_vertex(self, vertex: int, amount: int = 1) -> int:
        moved = self.prime * self.cycles
        if vertex >= moved:
            return vertex
        cycle, offset = divmod(vertex, self.prime)
        return cycle * self.prime + (offset + amount) % self.prime

    def shifted_edge(self, edge: tuple[int, int], amount: int) -> tuple[int, int]:
        left = self.shifted_vertex(edge[0], amount)
        right = self.shifted_vertex(edge[1], amount)
        return (left, right) if left < right else (right, left)

    def _build_edge_orbits(self) -> dict[tuple[int, int], int]:
        result: dict[tuple[int, int], int] = {}
        next_variable = 1
        for edge in itertools.combinations(range(self.order), 2):
            if edge in result:
                continue
            orbit = {
                self.shifted_edge(edge, amount)
                for amount in range(self.prime)
            }
            for member in orbit:
                result[member] = next_variable
            next_variable += 1
        return result

    def add_ramsey_clauses(self) -> None:
        for vertices in itertools.combinations(
            range(self.order), self.homogeneous_size
        ):
            signature = tuple(
                sorted(
                    {
                        self.edge_variables[edge]
                        for edge in itertools.combinations(vertices, 2)
                    }
                )
            )
            self.base_signatures.add(signature)

    def vertex_orbit_representatives(self) -> list[int]:
        moved_representatives = [
            cycle * self.prime for cycle in range(self.cycles)
        ]
        fixed_vertices = list(
            range(self.prime * self.cycles, self.order)
        )
        return moved_representatives + fixed_vertices

    def add_degree_bounds(self, lower: int, upper: int) -> None:
        for vertex in self.vertex_orbit_representatives():
            incident = [
                self.edge_variables[
                    (vertex, other) if vertex < other else (other, vertex)
                ]
                for other in range(self.order)
                if other != vertex
            ]
            self.formula.add_cardinality_range(incident, lower, upper)

    def add_root_cycle_prefix(self, adjacent_cycles: int) -> None:
        if self.fixed == 0:
            raise ValueError("the automorphism has no fixed vertex")
        if not 0 <= adjacent_cycles <= self.cycles:
            raise ValueError("invalid root cycle count")

        root = self.prime * self.cycles
        for cycle in range(self.cycles):
            representative = cycle * self.prime
            edge = (
                (root, representative)
                if root < representative
                else (representative, root)
            )
            variable = self.edge_variables[edge]
            self.formula.add_clause(
                (variable if cycle < adjacent_cycles else -variable,)
            )

    def cycle_internal_variable(self, cycle: int) -> int:
        if not 0 <= cycle < self.cycles:
            raise ValueError("invalid cycle index")
        left = cycle * self.prime
        right = left + 1
        return self.edge_variables[(left, right)]

    def root_cycle_variable(self, cycle: int) -> int:
        if self.fixed == 0:
            raise ValueError("the automorphism has no fixed vertex")
        if not 0 <= cycle < self.cycles:
            raise ValueError("invalid cycle index")

        root = self.prime * self.cycles
        representative = cycle * self.prime
        edge = (
            (root, representative)
            if root < representative
            else (representative, root)
        )
        return self.edge_variables[edge]

    def cycle_fixed_literals(self, cycle: int) -> list[int]:
        if not 0 <= cycle < self.cycles:
            raise ValueError("invalid cycle index")
        representative = cycle * self.prime
        return [
            self.edge_variables[
                (
                    (representative, fixed_vertex)
                    if representative < fixed_vertex
                    else (fixed_vertex, representative)
                )
            ]
            for fixed_vertex in range(
                self.prime * self.cycles,
                self.order,
            )
        ]

    def between_cycle_literals(
        self,
        left_cycle: int,
        right_cycle: int,
    ) -> list[int]:
        if not (
            0 <= left_cycle < right_cycle < self.cycles
        ):
            raise ValueError("invalid ordered cycle pair")
        left = left_cycle * self.prime
        right_start = right_cycle * self.prime
        return [
            self.edge_variables[(left, right_start + offset)]
            for offset in range(self.prime)
        ]

    def add_order_three_cycle_types(self, triangle_cycles: int) -> None:
        if self.prime != 3:
            raise ValueError("cycle-type constraints require prime 3")
        if not 0 <= triangle_cycles <= self.cycles:
            raise ValueError("invalid triangle-cycle count")

        for cycle in range(self.cycles):
            variable = self.cycle_internal_variable(cycle)
            self.formula.add_clause(
                (variable if cycle < triangle_cycles else -variable,)
            )

    def add_typed_root_signature(
        self,
        triangle_cycles: int,
        adjacent_triangle_cycles: int,
        nonadjacent_independent_cycles: int,
    ) -> None:
        if self.prime != 3:
            raise ValueError("typed root constraints require prime 3")
        if self.fixed == 0:
            raise ValueError("the automorphism has no fixed vertex")
        if not 0 <= triangle_cycles <= self.cycles:
            raise ValueError("invalid triangle-cycle count")

        independent_cycles = self.cycles - triangle_cycles
        if not 0 <= adjacent_triangle_cycles <= triangle_cycles:
            raise ValueError("invalid adjacent triangle-cycle count")
        if not (
            0
            <= nonadjacent_independent_cycles
            <= independent_cycles
        ):
            raise ValueError("invalid nonadjacent independent-cycle count")

        for cycle in range(self.cycles):
            if cycle < triangle_cycles:
                adjacent = cycle < adjacent_triangle_cycles
            else:
                independent_index = cycle - triangle_cycles
                adjacent = (
                    independent_index >= nonadjacent_independent_cycles
                )
            variable = self.root_cycle_variable(cycle)
            self.formula.add_clause((variable if adjacent else -variable,))

    def add_order_three_eight_structure(
        self,
        triangle_cycles: int,
    ) -> None:
        if (
            self.order != 43
            or self.prime != 3
            or self.cycles != 8
            or self.fixed != 19
        ):
            raise ValueError(
                "3^8 1^19 structure requires order 43 and eight 3-cycles"
            )
        if triangle_cycles not in (2, 3, 4):
            raise ValueError("normalized triangle count must be 2, 3, or 4")

        independent_cycles = self.cycles - triangle_cycles
        slack_budget = (triangle_cycles - 4) ** 2

        exception_literals = []
        for cycle in range(self.cycles):
            fixed_literals = self.cycle_fixed_literals(cycle)
            cycle_exceptions = (
                fixed_literals
                if cycle < triangle_cycles
                else [-literal for literal in fixed_literals]
            )
            self.formula.add_cardinality_range(
                cycle_exceptions,
                max(0, 4 - slack_budget),
                4,
            )
            exception_literals.extend(cycle_exceptions)
        self.formula.add_cardinality_range(
            exception_literals,
            32 - slack_budget,
            32,
        )

        same_type_budget_literals = []
        triangle_pairs = list(
            itertools.combinations(range(triangle_cycles), 2)
        )
        independent_range = range(
            triangle_cycles,
            self.cycles,
        )
        independent_pairs = list(
            itertools.combinations(independent_range, 2)
        )
        for left, right in triangle_pairs:
            literals = self.between_cycle_literals(left, right)
            self.formula.add_cardinality_range(literals, 0, 2)
            same_type_budget_literals.extend(-literal for literal in literals)
        for left, right in independent_pairs:
            literals = self.between_cycle_literals(left, right)
            self.formula.add_cardinality_range(literals, 1, 3)
            same_type_budget_literals.extend(literals)

        same_type_baseline = (
            len(triangle_pairs) + len(independent_pairs)
        )
        self.formula.add_cardinality_range(
            same_type_budget_literals,
            same_type_baseline,
            same_type_baseline + slack_budget // 2,
        )

        mixed_by_triangle = {
            triangle_cycle: [
                literal
                for independent_cycle in independent_range
                for literal in self.between_cycle_literals(
                    triangle_cycle,
                    independent_cycle,
                )
            ]
            for triangle_cycle in range(triangle_cycles)
        }
        mixed_by_independent = {
            independent_cycle: [
                literal
                for triangle_cycle in range(triangle_cycles)
                for literal in self.between_cycle_literals(
                    triangle_cycle,
                    independent_cycle,
                )
            ]
            for independent_cycle in independent_range
        }
        triangle_mixed_lower = 14 - 2 * triangle_cycles
        independent_mixed_upper = triangle_cycles + 2
        mixed_lower = 2 * triangle_cycles * (
            7 - triangle_cycles
        )
        mixed_upper = independent_cycles * (
            triangle_cycles + 2
        )
        triangle_mixed_upper = (
            mixed_upper
            - (triangle_cycles - 1) * triangle_mixed_lower
        )
        independent_mixed_lower = max(
            0,
            mixed_lower
            - (independent_cycles - 1) * independent_mixed_upper,
        )
        for literals in mixed_by_triangle.values():
            self.formula.add_cardinality_range(
                literals,
                triangle_mixed_lower,
                triangle_mixed_upper,
            )
        for literals in mixed_by_independent.values():
            self.formula.add_cardinality_range(
                literals,
                independent_mixed_lower,
                independent_mixed_upper,
            )

        mixed_literals = [
            literal
            for literals in mixed_by_triangle.values()
            for literal in literals
        ]
        self.formula.add_cardinality_range(
            mixed_literals,
            mixed_lower,
            mixed_upper,
        )

    def fixed_exception_literals(
        self,
        fixed_vertex: int,
        triangle_cycles: int,
    ) -> list[int]:
        moved = self.prime * self.cycles
        if not moved <= fixed_vertex < self.order:
            raise ValueError("invalid fixed vertex")
        offset = fixed_vertex - moved
        return [
            (
                self.cycle_fixed_literals(cycle)[offset]
                if cycle < triangle_cycles
                else -self.cycle_fixed_literals(cycle)[offset]
            )
            for cycle in range(self.cycles)
        ]

    def add_order_three_eight_t4_matrix(
        self,
        matrix_type: str,
        exclude_zero_fixed_signatures: bool,
    ) -> None:
        if (
            self.order != 43
            or self.prime != 3
            or self.cycles != 8
            or self.fixed != 19
        ):
            raise ValueError(
                "t4 matrix structure requires order 43 and eight 3-cycles"
            )
        try:
            matrix = T4_MIXED_MATRICES[matrix_type]
        except KeyError as error:
            raise ValueError("unknown t4 mixed matrix type") from error

        for triangle_cycle, row in enumerate(matrix):
            for independent_index, weight in enumerate(row):
                independent_cycle = 4 + independent_index
                literals = self.between_cycle_literals(
                    triangle_cycle,
                    independent_cycle,
                )
                self.formula.add_cardinality_range(
                    literals,
                    weight,
                    weight,
                )

        # Independent rotations of the seven nonroot cycles fix the
        # exceptional matching on a spanning star through triangle cycle 0.
        for other_triangle in range(1, 4):
            literals = self.between_cycle_literals(0, other_triangle)
            for index, literal in enumerate(literals):
                self.formula.add_clause(
                    (literal if index else -literal,)
                )
        for independent_index, weight in enumerate(matrix[0]):
            literals = self.between_cycle_literals(
                0,
                4 + independent_index,
            )
            for index, literal in enumerate(literals):
                present = (
                    index == 0 if weight == 1 else index != 0
                )
                self.formula.add_clause(
                    (literal if present else -literal,)
                )

        fixed_vertices = range(self.prime * self.cycles, self.order)
        fixed_literals_by_cycle = [
            self.cycle_fixed_literals(cycle)
            for cycle in range(self.cycles)
        ]
        for left, right in itertools.combinations(fixed_vertices, 2):
            left_offset = left - self.prime * self.cycles
            right_offset = right - self.prime * self.cycles
            fixed_edge = self.edge_variables[(left, right)]
            for cycle in range(self.cycles):
                left_exception = fixed_literals_by_cycle[cycle][left_offset]
                right_exception = fixed_literals_by_cycle[cycle][right_offset]
                forced_edge = -fixed_edge
                if cycle >= 4:
                    left_exception = -left_exception
                    right_exception = -right_exception
                    forced_edge = fixed_edge
                self.formula.add_clause(
                    (
                        -left_exception,
                        -right_exception,
                        forced_edge,
                    )
                )

        for triangle_cycle in range(4):
            triangle_fixed = fixed_literals_by_cycle[triangle_cycle]
            for independent_cycle in range(4, 8):
                independent_fixed = fixed_literals_by_cycle[
                    independent_cycle
                ]
                intersections = []
                for triangle_literal, independent_literal in zip(
                    triangle_fixed,
                    independent_fixed,
                ):
                    conjunction = self.formula.new_variable()
                    self.formula.add_and_gate(
                        conjunction,
                        triangle_literal,
                        -independent_literal,
                    )
                    intersections.append(conjunction)
                self.formula.add_cardinality_range(
                    intersections,
                    0,
                    1,
                )

        if exclude_zero_fixed_signatures:
            for fixed_vertex in fixed_vertices:
                self.formula.add_clause(
                    self.fixed_exception_literals(
                        fixed_vertex,
                        triangle_cycles=4,
                    )
                )

    def decode_primary_assignment(self, true_variables: set[int]) -> list[int]:
        adjacency = [0] * self.order
        for (left, right), variable in self.edge_variables.items():
            if variable in true_variables:
                adjacency[left] |= 1 << right
                adjacency[right] |= 1 << left
        return adjacency

    def has_homogeneous_set(
        self, adjacency: list[int], clique: bool
    ) -> bool:
        for vertices in itertools.combinations(
            range(self.order), self.homogeneous_size
        ):
            edges = [
                bool(adjacency[left] & (1 << right))
                for left, right in itertools.combinations(vertices, 2)
            ]
            if clique and all(edges):
                return True
            if not clique and not any(edges):
                return True
        return False

    def write_dimacs(self, path: Path) -> dict[str, object]:
        path.parent.mkdir(parents=True, exist_ok=True)
        total_clauses = 2 * len(self.base_signatures) + len(
            self.formula.clauses
        )
        variable_count = self.formula.next_variable - 1

        with path.open("w", encoding="ascii", newline="\n") as handle:
            handle.write(
                "c Ramsey orbit encoding: "
                f"n={self.order} p={self.prime} cycles={self.cycles} "
                f"fixed={self.fixed} homogeneous={self.homogeneous_size}\n"
            )
            handle.write(f"p cnf {variable_count} {total_clauses}\n")
            for signature in sorted(self.base_signatures):
                handle.write(
                    " ".join(str(-variable) for variable in signature)
                    + " 0\n"
                )
                handle.write(
                    " ".join(str(variable) for variable in signature)
                    + " 0\n"
                )
            for clause in self.formula.clauses:
                handle.write(" ".join(map(str, clause)) + " 0\n")

        raw = path.read_bytes()
        return {
            "order": self.order,
            "prime": self.prime,
            "cycles": self.cycles,
            "fixed": self.fixed,
            "homogeneous_size": self.homogeneous_size,
            "edge_orbit_variables": self.edge_variable_count,
            "variables": variable_count,
            "base_signatures": len(self.base_signatures),
            "extra_clauses": len(self.formula.clauses),
            "clauses": total_clauses,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", type=int, default=43)
    parser.add_argument("--prime", type=int, required=True)
    parser.add_argument("--cycles", type=int, required=True)
    parser.add_argument("--homogeneous-size", type=int, default=5)
    parser.add_argument("--degree-lower", type=int)
    parser.add_argument("--degree-upper", type=int)
    parser.add_argument("--root-adjacent-cycles", type=int)
    parser.add_argument("--triangle-cycles", type=int)
    parser.add_argument("--root-adjacent-triangle-cycles", type=int)
    parser.add_argument("--root-nonadjacent-independent-cycles", type=int)
    parser.add_argument(
        "--order-three-eight-structure",
        action="store_true",
    )
    parser.add_argument(
        "--t4-mixed-matrix",
        choices=tuple(T4_MIXED_MATRICES),
    )
    parser.add_argument(
        "--exclude-zero-fixed-signatures",
        action="store_true",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()

    encoding = OrbitRamseyEncoding(
        args.order,
        args.prime,
        args.cycles,
        args.homogeneous_size,
    )
    encoding.add_ramsey_clauses()

    if (args.degree_lower is None) != (args.degree_upper is None):
        raise ValueError("both degree bounds must be supplied")
    if args.degree_lower is not None:
        encoding.add_degree_bounds(args.degree_lower, args.degree_upper)

    typed_root_values = (
        args.root_adjacent_triangle_cycles,
        args.root_nonadjacent_independent_cycles,
    )
    typed_root_requested = any(
        value is not None for value in typed_root_values
    )
    if typed_root_requested and any(
        value is None for value in typed_root_values
    ):
        raise ValueError("both typed root counts must be supplied")
    if typed_root_requested and args.triangle_cycles is None:
        raise ValueError("typed root constraints require triangle cycles")
    if typed_root_requested and args.root_adjacent_cycles is not None:
        raise ValueError("root constraint modes are mutually exclusive")

    if args.order_three_eight_structure:
        if args.triangle_cycles is None:
            raise ValueError("c8 structure requires triangle cycles")
        encoding.add_order_three_eight_structure(args.triangle_cycles)
    if args.t4_mixed_matrix is not None:
        if not args.order_three_eight_structure:
            raise ValueError("t4 matrix requires c8 structure")
        if args.triangle_cycles != 4:
            raise ValueError("t4 matrix requires four triangle cycles")
        if not typed_root_requested:
            raise ValueError("t4 matrix requires a typed root branch")
        if args.exclude_zero_fixed_signatures and (
            args.root_adjacent_triangle_cycles != 1
            or args.root_nonadjacent_independent_cycles != 0
        ):
            raise ValueError(
                "zero-signature exclusion requires the p1-z0 branch"
            )
        encoding.add_order_three_eight_t4_matrix(
            args.t4_mixed_matrix,
            args.exclude_zero_fixed_signatures,
        )
    elif args.exclude_zero_fixed_signatures:
        raise ValueError("zero-signature exclusion requires a t4 matrix")
    if args.triangle_cycles is not None:
        encoding.add_order_three_cycle_types(args.triangle_cycles)
    if args.root_adjacent_cycles is not None:
        encoding.add_root_cycle_prefix(args.root_adjacent_cycles)
    if typed_root_requested:
        encoding.add_typed_root_signature(
            args.triangle_cycles,
            args.root_adjacent_triangle_cycles,
            args.root_nonadjacent_independent_cycles,
        )

    metadata = encoding.write_dimacs(args.output)
    metadata["degree_bounds"] = (
        [args.degree_lower, args.degree_upper]
        if args.degree_lower is not None
        else None
    )
    metadata["root_adjacent_cycles"] = args.root_adjacent_cycles
    if args.triangle_cycles is not None:
        metadata["triangle_cycles"] = args.triangle_cycles
        metadata["independent_cycles"] = (
            args.cycles - args.triangle_cycles
        )
    if typed_root_requested:
        metadata["root_adjacent_triangle_cycles"] = (
            args.root_adjacent_triangle_cycles
        )
        metadata["root_nonadjacent_independent_cycles"] = (
            args.root_nonadjacent_independent_cycles
        )
    if args.order_three_eight_structure:
        metadata["order_three_eight_structure"] = True
    if args.t4_mixed_matrix is not None:
        metadata["t4_mixed_matrix"] = args.t4_mixed_matrix
        metadata["exclude_zero_fixed_signatures"] = (
            args.exclude_zero_fixed_signatures
        )
    text = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        with args.metadata.open(
            "w",
            encoding="ascii",
            newline="\n",
        ) as handle:
            handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
