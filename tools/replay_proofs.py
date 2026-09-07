#!/usr/bin/env python3
"""Replay compressed binary DRAT proofs against regenerated CNFs."""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import subprocess
import time
from pathlib import Path


EXPECTED_CHECKER_SOURCE_COMMIT = "2e3b2dc0ecf938addbd779d42877b6ed69d9a985"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replay_branch(
    checker: Path,
    cnf_directory: Path,
    evidence_directory: Path,
    log_directory: Path,
    branch: int,
) -> dict[str, object]:
    stem = f"p3-c6-k{branch}"
    cnf_path = cnf_directory / f"{stem}.cnf"
    proof_path = evidence_directory / f"{stem}.drat.xz"
    log_path = log_directory / f"{stem}-fresh-drat-trim.log"

    with lzma.open(proof_path, "rb") as handle:
        proof = handle.read()

    started = time.perf_counter()
    completed = subprocess.run(
        [str(checker), str(cnf_path), "-i"],
        input=proof,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    elapsed = time.perf_counter() - started
    output = completed.stdout.decode("ascii", errors="replace")
    with log_path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(output)

    if completed.returncode != 0:
        raise AssertionError(
            f"drat-trim returned {completed.returncode} for branch {branch}"
        )
    if "s VERIFIED" not in output:
        raise AssertionError(f"drat-trim did not verify branch {branch}")

    return {
        "branch": branch,
        "result": "VERIFIED",
        "checker_exit_code": completed.returncode,
        "checker_seconds": round(elapsed, 6),
        "cnf_sha256": file_sha256(cnf_path),
        "proof_compressed_sha256": file_sha256(proof_path),
        "proof_decompressed_bytes": len(proof),
        "fresh_log": log_path.name,
        "fresh_log_sha256": file_sha256(log_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cnf_directory", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--checker-source-commit", required=True)
    parser.add_argument("--log-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.checker_source_commit != EXPECTED_CHECKER_SOURCE_COMMIT:
        raise AssertionError("unexpected drat-trim source commit")

    args.log_directory.mkdir(parents=True, exist_ok=True)
    results = [
        replay_branch(
            args.checker,
            args.cnf_directory,
            args.evidence_directory,
            args.log_directory,
            branch,
        )
        for branch in range(4)
    ]
    record = {
        "claim": (
            "No graph on 43 vertices with clique number and independence "
            "number at most 4 has an automorphism of cycle type 3^6 1^25."
        ),
        "checker": args.checker.name,
        "checker_sha256": file_sha256(args.checker),
        "checker_source_commit": args.checker_source_commit,
        "branches": results,
        "all_verified": True,
    }
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
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
