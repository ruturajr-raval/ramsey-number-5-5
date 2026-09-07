#!/usr/bin/env python3
"""Audit branch CNFs independently of their generation metadata."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import deque
from pathlib import Path


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


def audit_cnf(
    cnf_path: Path,
    metadata: dict[str, object],
    root_variables: list[int],
) -> dict[str, object]:
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
                raise AssertionError(f"invalid clause terminator in {cnf_path}")
            literals = [int(field) for field in fields[:-1]]
            if literals:
                maximum_variable = max(
                    maximum_variable,
                    max(abs(literal) for literal in literals),
                )
            clause_count += 1

            trailing.append(raw_line)
            if len(trailing) > len(root_variables):
                common_body_hash.update(trailing.popleft())

    if header_variables is None or header_clauses is None:
        raise AssertionError(f"missing DIMACS header in {cnf_path}")
    if clause_count != header_clauses:
        raise AssertionError(f"clause-count mismatch in {cnf_path}")
    if maximum_variable > header_variables:
        raise AssertionError(f"literal exceeds header range in {cnf_path}")

    branch = int(metadata["root_adjacent_cycles"])
    expected_root = [
        variable if cycle < branch else -variable
        for cycle, variable in enumerate(root_variables)
    ]
    observed_root = []
    for raw_line in trailing:
        fields = raw_line.split()
        if len(fields) != 2 or fields[-1] != b"0":
            raise AssertionError(f"root clause is not unit in {cnf_path}")
        observed_root.append(int(fields[0]))
    if observed_root != expected_root:
        raise AssertionError(f"root clauses do not match branch in {cnf_path}")

    file_bytes = cnf_path.stat().st_size
    file_sha256 = raw_hash.hexdigest()
    if file_bytes != int(metadata["bytes"]):
        raise AssertionError(f"byte-count mismatch in {cnf_path}")
    if file_sha256 != metadata["sha256"]:
        raise AssertionError(f"SHA-256 mismatch in {cnf_path}")
    if header_variables != int(metadata["variables"]):
        raise AssertionError(f"variable-count mismatch in {cnf_path}")
    if header_clauses != int(metadata["clauses"]):
        raise AssertionError(f"metadata clause-count mismatch in {cnf_path}")

    return {
        "branch": branch,
        "bytes": file_bytes,
        "sha256": file_sha256,
        "variables": header_variables,
        "clauses": header_clauses,
        "maximum_literal_variable": maximum_variable,
        "root_unit_clauses": observed_root,
        "common_body_sha256": common_body_hash.hexdigest(),
    }


def audit_directory(directory: Path) -> dict[str, object]:
    metadata_files = sorted(directory.glob("p3-c6-k[0-3].json"))
    if len(metadata_files) != 4:
        raise AssertionError("expected exactly four branch metadata files")

    first = json.loads(metadata_files[0].read_text(encoding="ascii"))
    order = int(first["order"])
    prime = int(first["prime"])
    cycles = int(first["cycles"])
    edge_variables = independent_edge_variables(order, prime, cycles)
    root = prime * cycles
    root_variables = []
    for cycle in range(cycles):
        representative = prime * cycle
        edge = (
            (root, representative)
            if root < representative
            else (representative, root)
        )
        root_variables.append(edge_variables[edge])

    audits = []
    for metadata_path in metadata_files:
        metadata = json.loads(metadata_path.read_text(encoding="ascii"))
        for field in ("order", "prime", "cycles"):
            if metadata[field] != first[field]:
                raise AssertionError(f"inconsistent {field} metadata")
        cnf_path = metadata_path.with_suffix(".cnf")
        audits.append(audit_cnf(cnf_path, metadata, root_variables))

    branches = [audit["branch"] for audit in audits]
    if branches != [0, 1, 2, 3]:
        raise AssertionError("branch set is incomplete")
    common_hashes = {audit["common_body_sha256"] for audit in audits}
    if len(common_hashes) != 1:
        raise AssertionError("branch formulas differ outside root clauses")

    return {
        "order": order,
        "prime": prime,
        "cycles": cycles,
        "root_vertex": root,
        "root_cycle_variables": root_variables,
        "branches": audits,
        "common_body_sha256": common_hashes.pop(),
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
