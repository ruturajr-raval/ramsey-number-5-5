#!/usr/bin/env python3
"""Audit the eight typed 3^8 1^19 branch CNFs independently."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import deque
from pathlib import Path

from verify_c8_branch_coverage import EXPECTED_BRANCHES


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def shifted_vertex(
    vertex: int,
    amount: int,
    prime: int,
    cycles: int,
) -> int:
    moved = prime * cycles
    if vertex >= moved:
        return vertex
    cycle, offset = divmod(vertex, prime)
    return cycle * prime + (offset + amount) % prime


def shifted_edge(
    edge: tuple[int, int],
    amount: int,
    prime: int,
    cycles: int,
) -> tuple[int, int]:
    left = shifted_vertex(edge[0], amount, prime, cycles)
    right = shifted_vertex(edge[1], amount, prime, cycles)
    return (left, right) if left < right else (right, left)


def independent_edge_variables(
    order: int,
    prime: int,
    cycles: int,
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


def expected_unit_clauses(
    metadata: dict[str, object],
    edge_variables: dict[tuple[int, int], int],
) -> list[int]:
    prime = int(metadata["prime"])
    cycles = int(metadata["cycles"])
    triangles = int(metadata["triangle_cycles"])
    adjacent_triangles = int(
        metadata["root_adjacent_triangle_cycles"]
    )
    nonadjacent_independent = int(
        metadata["root_nonadjacent_independent_cycles"]
    )
    root = prime * cycles

    internal_units = []
    root_units = []
    for cycle in range(cycles):
        first = cycle * prime
        internal = edge_variables[(first, first + 1)]
        internal_units.append(
            internal if cycle < triangles else -internal
        )

        root_edge = (first, root) if first < root else (root, first)
        root_variable = edge_variables[root_edge]
        if cycle < triangles:
            adjacent = cycle < adjacent_triangles
        else:
            independent_index = cycle - triangles
            adjacent = independent_index >= nonadjacent_independent
        root_units.append(
            root_variable if adjacent else -root_variable
        )
    return internal_units + root_units


def audit_cnf(
    cnf_path: Path,
    metadata: dict[str, object],
    edge_variables: dict[tuple[int, int], int],
) -> dict[str, object]:
    expected_units = expected_unit_clauses(metadata, edge_variables)
    raw_hash = hashlib.sha256()
    common_body_hash = hashlib.sha256()
    trailing: deque[bytes] = deque()
    header_variables = None
    header_clauses = None
    clause_count = 0
    maximum_variable = 0

    with cnf_path.open("rb") as handle:
        for raw_line in handle:
            raw_hash.update(raw_line)
            stripped = raw_line.strip()
            if not stripped or stripped.startswith(b"c"):
                continue
            if stripped.startswith(b"p "):
                fields = stripped.split()
                if len(fields) != 4 or fields[:2] != [b"p", b"cnf"]:
                    raise AssertionError(f"invalid DIMACS header in {cnf_path}")
                header_variables = int(fields[2])
                header_clauses = int(fields[3])
                continue

            fields = stripped.split()
            if fields[-1] != b"0" or b"0" in fields[:-1]:
                raise AssertionError(
                    f"invalid clause terminator in {cnf_path}"
                )
            literals = [int(field) for field in fields[:-1]]
            if literals:
                maximum_variable = max(
                    maximum_variable,
                    max(abs(literal) for literal in literals),
                )
            clause_count += 1

            trailing.append(raw_line)
            if len(trailing) > len(expected_units):
                common_body_hash.update(trailing.popleft())

    if header_variables is None or header_clauses is None:
        raise AssertionError(f"missing DIMACS header in {cnf_path}")
    if clause_count != header_clauses:
        raise AssertionError(f"clause-count mismatch in {cnf_path}")
    if maximum_variable > header_variables:
        raise AssertionError(f"literal exceeds header range in {cnf_path}")

    observed_units = []
    for raw_line in trailing:
        fields = raw_line.split()
        if len(fields) != 2 or fields[-1] != b"0":
            raise AssertionError(f"typed clause is not unit in {cnf_path}")
        observed_units.append(int(fields[0]))
    if observed_units != expected_units:
        raise AssertionError(
            f"typed unit clauses do not match metadata in {cnf_path}"
        )

    file_bytes = cnf_path.stat().st_size
    file_sha256 = raw_hash.hexdigest()
    if file_bytes != int(metadata["bytes"]):
        raise AssertionError(f"byte-count mismatch in {cnf_path}")
    if file_sha256 != metadata["sha256"]:
        raise AssertionError(f"SHA-256 mismatch in {cnf_path}")
    if header_variables != int(metadata["variables"]):
        raise AssertionError(f"variable-count mismatch in {cnf_path}")
    if header_clauses != int(metadata["clauses"]):
        raise AssertionError(
            f"metadata clause-count mismatch in {cnf_path}"
        )

    branch = (
        int(metadata["triangle_cycles"]),
        int(metadata["root_adjacent_triangle_cycles"]),
        int(metadata["root_nonadjacent_independent_cycles"]),
    )
    return {
        "branch": list(branch),
        "bytes": file_bytes,
        "sha256": file_sha256,
        "variables": header_variables,
        "clauses": header_clauses,
        "maximum_literal_variable": maximum_variable,
        "typed_unit_clauses": observed_units,
        "common_body_sha256": common_body_hash.hexdigest(),
    }


def audit_directory(directory: Path) -> dict[str, object]:
    metadata_files = sorted(directory.glob("p3-c8-t*-p*-z*.json"))
    if len(metadata_files) != len(EXPECTED_BRANCHES):
        raise AssertionError("expected exactly eight branch metadata files")

    first = json.loads(metadata_files[0].read_text(encoding="ascii"))
    expected_parameters = {
        "order": 43,
        "prime": 3,
        "cycles": 8,
        "fixed": 19,
        "homogeneous_size": 5,
        "degree_bounds": [18, 24],
        "root_adjacent_cycles": None,
        "order_three_eight_structure": True,
    }
    for field, expected in expected_parameters.items():
        if first.get(field) != expected:
            raise AssertionError(f"unexpected {field} metadata")
    order = int(first["order"])
    prime = int(first["prime"])
    cycles = int(first["cycles"])
    edge_variables = independent_edge_variables(order, prime, cycles)

    audits = []
    for metadata_path in metadata_files:
        metadata = json.loads(metadata_path.read_text(encoding="ascii"))
        for field, expected in expected_parameters.items():
            if metadata.get(field) != expected:
                raise AssertionError(
                    f"unexpected {field} metadata in {metadata_path}"
                )
        for field in (
            "order",
            "prime",
            "cycles",
            "fixed",
            "degree_bounds",
        ):
            if metadata[field] != first[field]:
                raise AssertionError(f"inconsistent {field} metadata")
        cnf_path = metadata_path.with_suffix(".cnf")
        audits.append(audit_cnf(cnf_path, metadata, edge_variables))

    branches = sorted(tuple(audit["branch"]) for audit in audits)
    if branches != sorted(EXPECTED_BRANCHES):
        raise AssertionError("branch set is incomplete")
    common_hashes_by_triangle_count = {}
    for triangle_count in (2, 3, 4):
        hashes = {
            audit["common_body_sha256"]
            for audit in audits
            if audit["branch"][0] == triangle_count
        }
        if len(hashes) != 1:
            raise AssertionError(
                "same-type branches differ outside typed clauses"
            )
        common_hashes_by_triangle_count[str(triangle_count)] = hashes.pop()

    return {
        "provenance": {
            "auditor": "tools/verify_c8_branch_artifacts.py",
            "auditor_sha256": file_sha256(Path(__file__)),
        },
        "audit_scope": (
            "DIMACS integrity, metadata, branch units, and common bodies. "
            "Exact formula semantics are checked by the independent "
            "reference verifier."
        ),
        "order": order,
        "prime": prime,
        "cycles": cycles,
        "branches": audits,
        "common_body_sha256_by_triangle_count": (
            common_hashes_by_triangle_count
        ),
        "audit_passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit_directory(args.directory)
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
