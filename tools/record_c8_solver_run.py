#!/usr/bin/env python3
"""Record and validate one completed c8 solver run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


EXPECTED_SOLVER_SOURCE_COMMIT = (
    "8af8e56f174b778aef3aa45af9f739b2a5f492c2"
)
EXPECTED_SOLVER_SHA256 = (
    "c86c7ccc2f727e1ef4716fd2fcf69539fbe0e8b1da8d89341fb48d643a3aeb28"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_match(pattern: str, text: str, label: str) -> re.Match[str]:
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing {label}")
    return match


def optional_match(pattern: str, text: str) -> re.Match[str] | None:
    return re.search(pattern, text, re.MULTILINE)


def classify_artifact_binding(
    solver_log: str,
    cnf_sha256: str,
    proof_bytes: int,
    proof_sha256: str,
    allow_post_run_attestation: bool,
) -> dict[str, object]:
    logged_cnf = optional_match(
        r"^c CNF SHA-256 ([0-9a-f]{64})$",
        solver_log,
    )
    logged_proof_bytes = optional_match(
        r"^proof_bytes=([0-9]+)$",
        solver_log,
    )
    logged_proof_hash = optional_match(
        r"^proof_sha256=([0-9a-f]{64})$",
        solver_log,
    )
    present = (
        logged_cnf is not None,
        logged_proof_bytes is not None,
        logged_proof_hash is not None,
    )
    if any(present) and not all(present):
        raise AssertionError("solver log has incomplete artifact binding")
    if all(present):
        if logged_cnf.group(1) != cnf_sha256:
            raise AssertionError("logged CNF hash mismatch")
        if int(logged_proof_bytes.group(1)) != proof_bytes:
            raise AssertionError("logged proof byte count mismatch")
        if logged_proof_hash.group(1) != proof_sha256:
            raise AssertionError("logged proof hash mismatch")
        return {
            "mode": "solver-log",
            "cnf_sha256_logged": True,
            "proof_bytes_logged": True,
            "proof_sha256_logged": True,
        }
    if not allow_post_run_attestation:
        raise AssertionError(
            "solver log lacks artifact hashes; use the explicit legacy "
            "post-run attestation option"
        )
    return {
        "mode": "post-run-attestation",
        "cnf_sha256_logged": False,
        "proof_bytes_logged": False,
        "proof_sha256_logged": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cnf", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--solver-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-post-run-attestation",
        action="store_true",
        help=(
            "accept a legacy solver log without embedded CNF/proof hashes "
            "and label the binding explicitly"
        ),
    )
    args = parser.parse_args()

    for path, label in (
        (args.cnf, "CNF"),
        (args.metadata, "metadata"),
        (args.proof, "proof"),
        (args.solver_log, "solver log"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")

    metadata = json.loads(args.metadata.read_text(encoding="ascii"))
    cnf_sha256 = file_sha256(args.cnf)
    if metadata.get("sha256") != cnf_sha256:
        raise AssertionError("CNF hash does not match metadata")
    if metadata.get("bytes") != args.cnf.stat().st_size:
        raise AssertionError("CNF byte count does not match metadata")

    solver_log = args.solver_log.read_text(
        encoding="ascii",
        errors="strict",
    )
    if "s UNSATISFIABLE" not in solver_log:
        raise AssertionError("solver log does not report UNSAT")
    source_commit = required_match(
        r"^c Solver source commit ([0-9a-f]{40})$",
        solver_log,
        "solver source commit",
    ).group(1)
    solver_sha256 = required_match(
        r"^c Solver SHA-256 ([0-9a-f]{64})$",
        solver_log,
        "solver SHA-256",
    ).group(1)
    if source_commit != EXPECTED_SOLVER_SOURCE_COMMIT:
        raise AssertionError("unexpected solver source commit")
    if solver_sha256 != EXPECTED_SOLVER_SHA256:
        raise AssertionError("unexpected solver binary hash")

    exit_match = optional_match(
        r"^kissat_exit=([0-9]+)$",
        solver_log,
    )
    exit_code = int(
        exit_match.group(1)
        if exit_match is not None
        else required_match(
            r"^c exit ([0-9]+)$",
            solver_log,
            "solver exit code",
        ).group(1)
    )
    if exit_code != 20:
        raise AssertionError(f"unexpected solver exit code: {exit_code}")
    wall_seconds = float(
        required_match(
            r"^real ([0-9.]+)$",
            solver_log,
            "solver wall time",
        ).group(1)
    )

    proof_bytes = args.proof.stat().st_size
    proof_sha256 = file_sha256(args.proof)
    artifact_binding = classify_artifact_binding(
        solver_log,
        cnf_sha256,
        proof_bytes,
        proof_sha256,
        args.allow_post_run_attestation,
    )

    record: dict[str, object] = {
        "artifact_binding": artifact_binding,
        "branch": [
            int(metadata["triangle_cycles"]),
            int(metadata["root_adjacent_triangle_cycles"]),
            int(metadata["root_nonadjacent_independent_cycles"]),
        ],
        "cnf": {
            "path": args.cnf.name,
            "bytes": args.cnf.stat().st_size,
            "sha256": cnf_sha256,
            "variables": int(metadata["variables"]),
            "clauses": int(metadata["clauses"]),
        },
        "proof": {
            "path": args.proof.name,
            "compressed_bytes": proof_bytes,
            "compressed_sha256": proof_sha256,
        },
        "solver": {
            "result": "UNSATISFIABLE",
            "exit_code": exit_code,
            "wall_seconds": wall_seconds,
            "source_commit": source_commit,
            "binary_sha256": solver_sha256,
            "log": args.solver_log.name,
            "log_sha256": file_sha256(args.solver_log),
        },
        "record_complete": True,
    }
    matrix_type = metadata.get("t4_mixed_matrix")
    if matrix_type is not None:
        record["matrix_type"] = matrix_type

    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
