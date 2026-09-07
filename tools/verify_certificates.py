#!/usr/bin/env python3
"""Verify retained branch artifacts and build a certificate manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decompressed_xz_details(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    with lzma.open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            byte_count += len(block)
            digest.update(block)
    return byte_count, digest.hexdigest()


def required_match(pattern: str, text: str, label: str) -> re.Match[str]:
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing {label}")
    return match


def verify_branch(
    cnf_directory: Path,
    evidence_directory: Path,
    branch: int,
) -> dict[str, object]:
    stem = f"p3-c6-k{branch}"
    metadata_path = cnf_directory / f"{stem}.json"
    cnf_path = cnf_directory / f"{stem}.cnf"
    proof_path = evidence_directory / f"{stem}.drat.xz"
    solver_log_path = evidence_directory / f"{stem}-proof.log"
    checker_log_path = evidence_directory / f"{stem}-drat-trim.log"

    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    solver_log = solver_log_path.read_text(encoding="ascii")
    checker_log = checker_log_path.read_text(encoding="ascii")

    if metadata["root_adjacent_cycles"] != branch:
        raise AssertionError(f"branch metadata mismatch for {stem}")
    if "s UNSATISFIABLE" not in solver_log:
        raise AssertionError(f"solver did not report UNSAT for {stem}")
    if "solver_exit_code=20" not in solver_log:
        raise AssertionError(f"unexpected solver exit code for {stem}")
    if "s VERIFIED" not in checker_log:
        raise AssertionError(f"proof checker did not verify {stem}")
    if "drat_trim_exit_code=0" not in checker_log:
        raise AssertionError(f"unexpected checker exit code for {stem}")

    cnf_sha256 = file_sha256(cnf_path)
    if cnf_sha256 != metadata["sha256"]:
        raise AssertionError(f"CNF hash mismatch for {stem}")

    proof_bytes, proof_sha256 = decompressed_xz_details(proof_path)
    checker_bytes = int(
        required_match(
            r"read ([0-9]+) bytes from proof file",
            checker_log,
            f"proof byte count for {stem}",
        ).group(1)
    )
    if proof_bytes != checker_bytes:
        raise AssertionError(f"decompressed proof size mismatch for {stem}")

    real_seconds = float(
        required_match(
            r"^real ([0-9.]+)$",
            solver_log,
            f"solver wall time for {stem}",
        ).group(1)
    )
    checker_seconds = float(
        required_match(
            r"verification time: ([0-9.]+) seconds",
            checker_log,
            f"checker time for {stem}",
        ).group(1)
    )

    return {
        "branch": branch,
        "cnf": {
            "path": cnf_path.name,
            "bytes": cnf_path.stat().st_size,
            "sha256": cnf_sha256,
            "variables": metadata["variables"],
            "clauses": metadata["clauses"],
        },
        "proof": {
            "path": proof_path.name,
            "compressed_bytes": proof_path.stat().st_size,
            "compressed_sha256": file_sha256(proof_path),
            "decompressed_bytes": proof_bytes,
            "decompressed_sha256": proof_sha256,
        },
        "solver": {
            "result": "UNSATISFIABLE",
            "exit_code": 20,
            "wall_seconds": real_seconds,
            "log": solver_log_path.name,
            "log_sha256": file_sha256(solver_log_path),
        },
        "checker": {
            "result": "VERIFIED",
            "exit_code": 0,
            "wall_seconds": checker_seconds,
            "log": checker_log_path.name,
            "log_sha256": file_sha256(checker_log_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cnf_directory", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--cnf-audit", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    coverage = json.loads(args.coverage.read_text(encoding="ascii"))
    cnf_audit = json.loads(args.cnf_audit.read_text(encoding="ascii"))
    if not coverage["coverage_complete"]:
        raise AssertionError("branch coverage is incomplete")
    if not cnf_audit["audit_passed"]:
        raise AssertionError("CNF artifact audit failed")

    branches = [
        verify_branch(
            args.cnf_directory,
            args.evidence_directory,
            branch,
        )
        for branch in range(4)
    ]
    manifest = {
        "claim": (
            "No graph on 43 vertices with clique number and independence "
            "number at most 4 has an automorphism of cycle type 3^6 1^25."
        ),
        "claim_boundary": (
            "This excludes one automorphism cycle type. It does not determine "
            "R(5,5), exclude asymmetric graphs, or change 43 <= R(5,5) <= 46."
        ),
        "coverage": {
            "patterns_checked": coverage["patterns_checked"],
            "solved_branches": coverage["solved_branches"],
            "artifact": args.coverage.name,
            "sha256": file_sha256(args.coverage),
        },
        "cnf_audit": {
            "common_body_sha256": cnf_audit["common_body_sha256"],
            "root_cycle_variables": cnf_audit["root_cycle_variables"],
            "artifact": args.cnf_audit.name,
            "sha256": file_sha256(args.cnf_audit),
        },
        "branches": branches,
        "verification_passed": True,
    }

    expected = json.loads(args.expected_manifest.read_text(encoding="ascii"))
    tools = expected.get("tools")
    if not isinstance(tools, dict):
        raise AssertionError("expected manifest has no historical tool record")
    for name in ("kissat_sha256", "drat_trim_sha256"):
        value = tools.get(name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise AssertionError(f"invalid historical tool hash: {name}")
    manifest["tools"] = tools
    if manifest != expected:
        raise AssertionError("reconstructed certificate manifest changed")

    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
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
