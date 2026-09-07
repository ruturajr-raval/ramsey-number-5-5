#!/usr/bin/env python3
"""Independently rebuild and compare the canonical 3^8 1^19 CNFs."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
ORDER = 43
PRIME = 3
CYCLES = 8
FIXED = 19
HOMOGENEOUS_SIZE = 5
DEGREE_LOWER = 18
DEGREE_UPPER = 24

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


class ReferenceFormula:
    """Clause builder matching the canonical encoder's allocation order."""

    def __init__(self, first_free_variable: int) -> None:
        self.next_variable = first_free_variable
        self.clauses: list[tuple[int, ...]] = []

    def clone(self) -> "ReferenceFormula":
        result = ReferenceFormula(self.next_variable)
        result.clauses = self.clauses.copy()
        return result

    def new_variable(self) -> int:
        variable = self.next_variable
        self.next_variable += 1
        return variable

    def add_clause(self, literals: Iterable[int]) -> None:
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
        self,
        literals: list[int],
        lower: int,
        upper: int,
    ) -> None:
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


def shifted_vertex(
    vertex: int,
    amount: int,
    prime: int = PRIME,
    cycles: int = CYCLES,
) -> int:
    moved = prime * cycles
    if vertex >= moved:
        return vertex
    cycle, offset = divmod(vertex, prime)
    return cycle * prime + (offset + amount) % prime


def shifted_edge(
    edge: tuple[int, int],
    amount: int,
    prime: int = PRIME,
    cycles: int = CYCLES,
) -> tuple[int, int]:
    left = shifted_vertex(edge[0], amount, prime, cycles)
    right = shifted_vertex(edge[1], amount, prime, cycles)
    return (left, right) if left < right else (right, left)


def build_edge_orbits(
    order: int = ORDER,
    prime: int = PRIME,
    cycles: int = CYCLES,
) -> dict[tuple[int, int], int]:
    variables: dict[tuple[int, int], int] = {}
    next_variable = 1
    for edge in itertools.combinations(range(order), 2):
        if edge in variables:
            continue
        orbit = {
            shifted_edge(edge, amount, prime, cycles)
            for amount in range(prime)
        }
        for member in orbit:
            variables[member] = next_variable
        next_variable += 1
    return variables


def build_ramsey_signatures(
    edge_variables: dict[tuple[int, int], int],
) -> tuple[tuple[int, ...], ...]:
    signatures: set[tuple[int, ...]] = set()
    for vertices in itertools.combinations(range(ORDER), HOMOGENEOUS_SIZE):
        signature = tuple(
            sorted(
                {
                    edge_variables[edge]
                    for edge in itertools.combinations(vertices, 2)
                }
            )
        )
        signatures.add(signature)
    return tuple(sorted(signatures))


def vertex_orbit_representatives() -> list[int]:
    return [
        *(cycle * PRIME for cycle in range(CYCLES)),
        *range(PRIME * CYCLES, ORDER),
    ]


def add_degree_bounds(
    formula: ReferenceFormula,
    edge_variables: dict[tuple[int, int], int],
) -> None:
    for vertex in vertex_orbit_representatives():
        incident = [
            edge_variables[
                (vertex, other) if vertex < other else (other, vertex)
            ]
            for other in range(ORDER)
            if other != vertex
        ]
        formula.add_cardinality_range(
            incident,
            DEGREE_LOWER,
            DEGREE_UPPER,
        )


def cycle_internal_variable(
    edge_variables: dict[tuple[int, int], int],
    cycle: int,
) -> int:
    left = cycle * PRIME
    return edge_variables[(left, left + 1)]


def root_cycle_variable(
    edge_variables: dict[tuple[int, int], int],
    cycle: int,
) -> int:
    root = PRIME * CYCLES
    representative = cycle * PRIME
    edge = (
        (root, representative)
        if root < representative
        else (representative, root)
    )
    return edge_variables[edge]


def cycle_fixed_literals(
    edge_variables: dict[tuple[int, int], int],
    cycle: int,
) -> list[int]:
    representative = cycle * PRIME
    return [
        edge_variables[(representative, fixed_vertex)]
        for fixed_vertex in range(PRIME * CYCLES, ORDER)
    ]


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


@dataclass(frozen=True)
class StructureBounds:
    slack: int
    exception_lower: int
    same_type_deviation_upper: int
    mixed_lower: int
    mixed_upper: int
    triangle_row_lower: int
    triangle_row_upper: int
    independent_column_lower: int
    independent_column_upper: int


def structure_bounds(triangle_cycles: int) -> StructureBounds:
    if triangle_cycles not in (2, 3, 4):
        raise ValueError("normalized triangle count must be 2, 3, or 4")
    independent_cycles = CYCLES - triangle_cycles
    slack = (triangle_cycles - 4) ** 2
    mixed_lower = 2 * triangle_cycles * (7 - triangle_cycles)
    mixed_upper = independent_cycles * (triangle_cycles + 2)
    triangle_row_lower = 14 - 2 * triangle_cycles
    triangle_row_upper = (
        mixed_upper
        - (triangle_cycles - 1) * triangle_row_lower
    )
    independent_column_upper = triangle_cycles + 2
    independent_column_lower = max(
        0,
        mixed_lower
        - (independent_cycles - 1) * independent_column_upper,
    )
    return StructureBounds(
        slack=slack,
        exception_lower=32 - slack,
        same_type_deviation_upper=slack // 2,
        mixed_lower=mixed_lower,
        mixed_upper=mixed_upper,
        triangle_row_lower=triangle_row_lower,
        triangle_row_upper=triangle_row_upper,
        independent_column_lower=independent_column_lower,
        independent_column_upper=independent_column_upper,
    )


def add_c8_structure(
    formula: ReferenceFormula,
    edge_variables: dict[tuple[int, int], int],
    triangle_cycles: int,
) -> None:
    bounds = structure_bounds(triangle_cycles)
    independent_cycles = CYCLES - triangle_cycles

    # A triangle has at most four fixed neighbors, and an independent
    # triple has at most four fixed nonneighbors. Degree summation gives
    # total exceptions at least 32-(t-4)^2.
    exception_literals: list[int] = []
    for cycle in range(CYCLES):
        fixed_literals = cycle_fixed_literals(edge_variables, cycle)
        cycle_exceptions = (
            fixed_literals
            if cycle < triangle_cycles
            else [-literal for literal in fixed_literals]
        )
        formula.add_cardinality_range(
            cycle_exceptions,
            max(0, 4 - bounds.slack),
            4,
        )
        exception_literals.extend(cycle_exceptions)
    formula.add_cardinality_range(
        exception_literals,
        bounds.exception_lower,
        32,
    )

    triangle_pairs = list(
        itertools.combinations(range(triangle_cycles), 2)
    )
    independent_range = range(triangle_cycles, CYCLES)
    independent_pairs = list(
        itertools.combinations(independent_range, 2)
    )
    same_type_literals: list[int] = []
    for left, right in triangle_pairs:
        literals = between_cycle_literals(edge_variables, left, right)
        formula.add_cardinality_range(literals, 0, 2)
        same_type_literals.extend(-literal for literal in literals)
    for left, right in independent_pairs:
        literals = between_cycle_literals(edge_variables, left, right)
        formula.add_cardinality_range(literals, 1, 3)
        same_type_literals.extend(literals)

    same_type_baseline = len(triangle_pairs) + len(independent_pairs)
    formula.add_cardinality_range(
        same_type_literals,
        same_type_baseline,
        same_type_baseline + bounds.same_type_deviation_upper,
    )

    mixed_by_triangle = {
        triangle: [
            literal
            for independent in independent_range
            for literal in between_cycle_literals(
                edge_variables,
                triangle,
                independent,
            )
        ]
        for triangle in range(triangle_cycles)
    }
    mixed_by_independent = {
        independent: [
            literal
            for triangle in range(triangle_cycles)
            for literal in between_cycle_literals(
                edge_variables,
                triangle,
                independent,
            )
        ]
        for independent in independent_range
    }
    for literals in mixed_by_triangle.values():
        formula.add_cardinality_range(
            literals,
            bounds.triangle_row_lower,
            bounds.triangle_row_upper,
        )
    for literals in mixed_by_independent.values():
        formula.add_cardinality_range(
            literals,
            bounds.independent_column_lower,
            bounds.independent_column_upper,
        )

    mixed_literals = [
        literal
        for literals in mixed_by_triangle.values()
        for literal in literals
    ]
    formula.add_cardinality_range(
        mixed_literals,
        bounds.mixed_lower,
        bounds.mixed_upper,
    )

    if independent_cycles != len(mixed_by_independent):
        raise AssertionError("independent-cycle construction changed")


def branch_units(
    edge_variables: dict[tuple[int, int], int],
    branch: Branch,
) -> tuple[tuple[int, ...], ...]:
    triangle_cycles, adjacent_triangles, missed_independent = branch
    independent_cycles = CYCLES - triangle_cycles
    if not 0 <= adjacent_triangles <= triangle_cycles:
        raise ValueError("invalid adjacent triangle count")
    if not 0 <= missed_independent <= independent_cycles:
        raise ValueError("invalid missed independent count")

    units: list[tuple[int, ...]] = []
    for cycle in range(CYCLES):
        variable = cycle_internal_variable(edge_variables, cycle)
        units.append(
            (variable if cycle < triangle_cycles else -variable,)
        )
    for cycle in range(CYCLES):
        if cycle < triangle_cycles:
            adjacent = cycle < adjacent_triangles
        else:
            independent_index = cycle - triangle_cycles
            adjacent = independent_index >= missed_independent
        variable = root_cycle_variable(edge_variables, cycle)
        units.append((variable if adjacent else -variable,))
    return tuple(units)


def exception_count(
    triangle_pattern: tuple[bool, ...],
    root_adjacency: tuple[bool, ...],
) -> int:
    if len(triangle_pattern) != CYCLES or len(root_adjacency) != CYCLES:
        raise ValueError("expected eight moved cycles")
    return sum(
        adjacent if triangle else not adjacent
        for triangle, adjacent in zip(
            triangle_pattern,
            root_adjacency,
        )
    )


def normalize_branch(
    triangle_pattern: tuple[bool, ...],
    root_adjacency: tuple[bool, ...],
) -> Branch:
    if exception_count(triangle_pattern, root_adjacency) > 1:
        raise ValueError("root has more than one exceptional incidence")

    triangles = sum(triangle_pattern)
    if triangles in (0, 1, 7, 8):
        raise ValueError("elementary cases have no certificate branch")
    if triangles > 4:
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
    missed_independent = sum(
        (not triangle) and (not adjacent)
        for triangle, adjacent in zip(
            triangle_pattern,
            root_adjacency,
        )
    )
    branch = (triangles, adjacent_triangles, missed_independent)
    if branch == (4, 0, 1):
        branch = (4, 1, 0)
    if branch not in EXPECTED_BRANCHES:
        raise AssertionError(f"unexpected canonical branch: {branch}")
    return branch


def normalized_branch_counts() -> Counter[Branch]:
    counts: Counter[Branch] = Counter()
    for triangle_pattern in itertools.product((False, True), repeat=CYCLES):
        if sum(triangle_pattern) in (0, 1, 7, 8):
            continue
        for root_adjacency in itertools.product((False, True), repeat=CYCLES):
            if exception_count(triangle_pattern, root_adjacency) <= 1:
                counts[normalize_branch(triangle_pattern, root_adjacency)] += 1
    return counts


def build_degree_template(
    edge_variables: dict[tuple[int, int], int],
) -> ReferenceFormula:
    edge_variable_count = max(edge_variables.values())
    formula = ReferenceFormula(edge_variable_count + 1)
    add_degree_bounds(formula, edge_variables)
    return formula


def build_triangle_body(
    degree_template: ReferenceFormula,
    edge_variables: dict[tuple[int, int], int],
    triangle_cycles: int,
) -> ReferenceFormula:
    formula = degree_template.clone()
    add_c8_structure(formula, edge_variables, triangle_cycles)
    return formula


def render_clause(clause: tuple[int, ...]) -> bytes:
    return (" ".join(map(str, clause)) + " 0\n").encode("ascii")


def expected_cnf_lines(
    signatures: tuple[tuple[int, ...], ...],
    body: ReferenceFormula,
    units: tuple[tuple[int, ...], ...],
) -> Iterator[bytes]:
    total_clauses = 2 * len(signatures) + len(body.clauses) + len(units)
    variable_count = body.next_variable - 1
    yield (
        "c Ramsey orbit encoding: "
        f"n={ORDER} p={PRIME} cycles={CYCLES} fixed={FIXED} "
        f"homogeneous={HOMOGENEOUS_SIZE}\n"
    ).encode("ascii")
    yield f"p cnf {variable_count} {total_clauses}\n".encode("ascii")
    for signature in signatures:
        yield render_clause(tuple(-variable for variable in signature))
        yield render_clause(signature)
    for clause in body.clauses:
        yield render_clause(clause)
    yield from (render_clause(unit) for unit in units)


def branch_stem(branch: Branch) -> str:
    triangles, adjacent_triangles, missed_independent = branch
    return (
        f"p3-c8-t{triangles}-p{adjacent_triangles}"
        f"-z{missed_independent}"
    )


def require_inside_repository(path: Path, must_exist: bool = True) -> Path:
    if path.is_symlink():
        raise ValueError(f"symlinked paths are not accepted: {path}")
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"path escapes repository: {path}") from error
    if must_exist and not resolved.exists():
        raise ValueError(f"path does not exist: {path}")
    return resolved


def expected_metadata(
    branch: Branch,
    edge_variable_count: int,
    signature_count: int,
    body: ReferenceFormula,
) -> dict[str, object]:
    triangles, adjacent_triangles, missed_independent = branch
    extra_clauses = len(body.clauses) + 2 * CYCLES
    return {
        "order": ORDER,
        "prime": PRIME,
        "cycles": CYCLES,
        "fixed": FIXED,
        "homogeneous_size": HOMOGENEOUS_SIZE,
        "degree_bounds": [DEGREE_LOWER, DEGREE_UPPER],
        "edge_orbit_variables": edge_variable_count,
        "variables": body.next_variable - 1,
        "base_signatures": signature_count,
        "extra_clauses": extra_clauses,
        "clauses": 2 * signature_count + extra_clauses,
        "root_adjacent_cycles": None,
        "triangle_cycles": triangles,
        "independent_cycles": CYCLES - triangles,
        "root_adjacent_triangle_cycles": adjacent_triangles,
        "root_nonadjacent_independent_cycles": missed_independent,
        "order_three_eight_structure": True,
    }


def compare_cnf(
    cnf_path: Path,
    expected_lines: Iterable[bytes],
) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    with cnf_path.open("rb") as actual:
        for line_number, expected in enumerate(expected_lines, start=1):
            observed = actual.readline()
            digest.update(observed)
            byte_count += len(observed)
            if observed != expected:
                raise AssertionError(
                    f"{cnf_path.name}: mismatch at line {line_number}: "
                    f"expected={expected[:160]!r}, observed={observed[:160]!r}"
                )
        trailing = actual.readline()
        if trailing:
            raise AssertionError(
                f"{cnf_path.name}: unexpected trailing CNF content"
            )
    return byte_count, digest.hexdigest()


def verify_branch(
    directory: Path,
    branch: Branch,
    edge_variables: dict[tuple[int, int], int],
    signatures: tuple[tuple[int, ...], ...],
    body: ReferenceFormula,
) -> dict[str, object]:
    stem = branch_stem(branch)
    metadata_path = require_inside_repository(directory / f"{stem}.json")
    cnf_path = require_inside_repository(directory / f"{stem}.cnf")
    if not metadata_path.is_file() or not cnf_path.is_file():
        raise ValueError(f"{stem}: branch artifacts must be regular files")
    metadata = json.loads(metadata_path.read_text(encoding="ascii"))

    expected = expected_metadata(
        branch,
        max(edge_variables.values()),
        len(signatures),
        body,
    )
    for field, value in expected.items():
        if field not in metadata:
            raise AssertionError(f"{stem}: missing metadata field {field}")
        if metadata[field] != value:
            raise AssertionError(
                f"{stem}: metadata mismatch for {field}: "
                f"expected={value!r}, observed={metadata[field]!r}"
            )
    if metadata["order_three_eight_structure"] is not True:
        raise AssertionError(f"{stem}: structure marker is not boolean true")

    units = branch_units(edge_variables, branch)
    byte_count, sha256 = compare_cnf(
        cnf_path,
        expected_cnf_lines(signatures, body, units),
    )
    if metadata.get("bytes") != byte_count:
        raise AssertionError(f"{stem}: metadata byte count is incorrect")
    if metadata.get("sha256") != sha256:
        raise AssertionError(f"{stem}: metadata SHA-256 is incorrect")

    return {
        "branch": list(branch),
        "cnf": cnf_path.name,
        "bytes": byte_count,
        "sha256": sha256,
        "variables": body.next_variable - 1,
        "clauses": expected["clauses"],
        "semantic_match": True,
    }


def verify_directory(directory: Path) -> dict[str, object]:
    directory = require_inside_repository(directory)
    if not directory.is_dir():
        raise ValueError(f"artifact path is not a directory: {directory}")

    expected_names = {
        f"{branch_stem(branch)}.json" for branch in EXPECTED_BRANCHES
    }
    observed_names = {
        path.name for path in directory.glob("p3-c8-t*-p*-z*.json")
    }
    if observed_names != expected_names:
        raise AssertionError(
            "branch metadata set mismatch: "
            f"missing={sorted(expected_names - observed_names)}, "
            f"extra={sorted(observed_names - expected_names)}"
        )

    counts = normalized_branch_counts()
    if set(counts) != set(EXPECTED_BRANCHES) or sum(counts.values()) != 2142:
        raise AssertionError("canonical branch normalization changed")

    edge_variables = build_edge_orbits()
    edge_variable_count = max(edge_variables.values())
    if edge_variable_count != 415:
        raise AssertionError("edge-orbit count changed")
    signatures = build_ramsey_signatures(edge_variables)
    if len(signatures) != 328438:
        raise AssertionError("Ramsey signature count changed")
    degree_template = build_degree_template(edge_variables)

    results = []
    body_summaries = {}
    for triangle_cycles in (2, 3, 4):
        body = build_triangle_body(
            degree_template,
            edge_variables,
            triangle_cycles,
        )
        branches = [
            branch
            for branch in EXPECTED_BRANCHES
            if branch[0] == triangle_cycles
        ]
        results.extend(
            verify_branch(
                directory,
                branch,
                edge_variables,
                signatures,
                body,
            )
            for branch in branches
        )
        body_summaries[str(triangle_cycles)] = {
            "variables": body.next_variable - 1,
            "body_clauses": len(body.clauses),
            "reused_for_branches": len(branches),
        }

    return {
        "cycle_type": "3^8 1^19",
        "provenance": {
            "generator": "src/orbit_cnf.py",
            "generator_sha256": file_sha256(ROOT / "src/orbit_cnf.py"),
            "reference_verifier": "tools/verify_c8_formula_semantics.py",
            "reference_verifier_sha256": file_sha256(Path(__file__)),
        },
        "parameters": {
            "order": ORDER,
            "prime": PRIME,
            "cycles": CYCLES,
            "fixed": FIXED,
            "homogeneous_size": HOMOGENEOUS_SIZE,
            "degree_bounds": [DEGREE_LOWER, DEGREE_UPPER],
        },
        "edge_orbit_variables": edge_variable_count,
        "base_signatures": len(signatures),
        "normalized_configurations": sum(counts.values()),
        "body_summaries": body_summaries,
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
