#!/usr/bin/env python3
"""Run one c8 certificate branch with reproducible solver provenance."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import time
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


def source_commit(source_directory: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(source_directory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def require_clean_source_tree(source_directory: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(source_directory),
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise AssertionError(f"tracked source changes in {source_directory}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", type=Path, required=True)
    parser.add_argument("--solver-source", type=Path, required=True)
    parser.add_argument("--cnf", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()

    for path, label in (
        (args.solver, "solver"),
        (args.cnf, "CNF"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    for path, label in (
        (args.proof, "proof"),
        (args.log, "log"),
    ):
        if path.exists():
            raise FileExistsError(f"{label} already exists: {path}")

    observed_commit = source_commit(args.solver_source)
    if observed_commit != EXPECTED_SOLVER_SOURCE_COMMIT:
        raise AssertionError("unexpected Kissat source commit")
    if args.solver.resolve() != (
        args.solver_source / "build" / "kissat"
    ).resolve():
        raise AssertionError("solver is not the pinned source build")
    require_clean_source_tree(args.solver_source)
    solver_sha256 = file_sha256(args.solver)
    if solver_sha256 != EXPECTED_SOLVER_SHA256:
        raise AssertionError("unexpected Kissat binary hash")

    args.proof.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with args.log.open("w", encoding="ascii", newline="\n") as log:
        log.write(
            "c Solver source commit "
            f"{observed_commit}\n"
        )
        log.write(f"c Solver SHA-256 {solver_sha256}\n")
        log.write(f"c CNF SHA-256 {file_sha256(args.cnf)}\n")
        log.flush()
        process = subprocess.run(
            [
                str(args.solver),
                "--unsat",
                str(args.cnf),
                str(args.proof),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
        elapsed = time.perf_counter() - started
        log.write(f"real {elapsed:.2f}\n")
        log.write(f"kissat_exit={process.returncode}\n")
        if args.proof.is_file():
            log.write(f"proof_bytes={args.proof.stat().st_size}\n")
            log.write(f"proof_sha256={file_sha256(args.proof)}\n")

    if process.returncode != 20:
        raise RuntimeError(
            f"expected Kissat UNSAT exit 20, got {process.returncode}"
        )


if __name__ == "__main__":
    main()
