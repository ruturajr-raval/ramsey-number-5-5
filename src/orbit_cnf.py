#!/usr/bin/env python3
"""Generate Ramsey CNFs for a prescribed prime-order automorphism."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path


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
    if args.root_adjacent_cycles is not None:
        encoding.add_root_cycle_prefix(args.root_adjacent_cycles)

    metadata = encoding.write_dimacs(args.output)
    metadata["degree_bounds"] = (
        [args.degree_lower, args.degree_upper]
        if args.degree_lower is not None
        else None
    )
    metadata["root_adjacent_cycles"] = args.root_adjacent_cycles
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
