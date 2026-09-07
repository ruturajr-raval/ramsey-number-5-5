#!/usr/bin/env python3
"""Replay and bind the complete retained 3^6 1^25 DRAT certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import subprocess
import time
from pathlib import Path


EXPECTED_CHECKER_SOURCE_COMMIT = (
    "2e3b2dc0ecf938addbd779d42877b6ed69d9a985"
)
EXPECTED_BRANCHES = (0, 1, 2, 3)
CLAIM = (
    "No graph on 43 vertices with clique number and independence "
    "number at most 4 has an automorphism of cycle type 3^6 1^25."
)
CLAIM_BOUNDARY = (
    "This excludes one automorphism cycle type. It does not determine "
    "R(5,5), exclude asymmetric graphs, or change 43 <= R(5,5) <= 46."
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


def build_fresh_checker(
    source_directory: Path,
    log_directory: Path,
    compiler: str,
) -> tuple[Path, dict[str, object]]:
    source_path = source_directory / "drat-trim.c"
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    checker_path = log_directory / "drat-trim-fresh"
    build_log_path = log_directory / "drat-trim-fresh-build.log"
    version = subprocess.run(
        [compiler, "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    command = [
        compiler,
        str(source_path),
        "-std=c99",
        "-O2",
        "-o",
        str(checker_path),
    ]
    with build_log_path.open("w", encoding="ascii", newline="\n") as log:
        log.write("command=" + " ".join(command) + "\n")
        log.write("compiler_version=" + version.stdout.splitlines()[0] + "\n")
        completed = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log.write(f"compiler_exit_code={completed.returncode}\n")
    if completed.returncode != 0:
        raise AssertionError("fresh drat-trim build failed")
    if not checker_path.is_file():
        raise AssertionError("fresh drat-trim build produced no executable")
    return checker_path, {
        "mode": "fresh-source-build",
        "compiler": compiler,
        "compiler_version": version.stdout.splitlines()[0],
        "source": source_path.name,
        "source_sha256": file_sha256(source_path),
        "command": command,
        "log": build_log_path.name,
        "log_sha256": file_sha256(build_log_path),
    }


def replay_branch(
    checker: Path,
    cnf_directory: Path,
    evidence_directory: Path,
    log_directory: Path,
    branch: int,
) -> dict[str, object]:
    stem = f"p3-c6-k{branch}"
    metadata_path = cnf_directory / f"{stem}.json"
    cnf_path = cnf_directory / f"{stem}.cnf"
    proof_path = evidence_directory / f"{stem}.drat.xz"
    log_path = log_directory / f"{stem}-fresh-drat-trim.log"
    for path in (metadata_path, cnf_path, proof_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    if metadata.get("root_adjacent_cycles") != branch:
        raise AssertionError(f"branch metadata mismatch for {stem}")
    cnf_sha256 = file_sha256(cnf_path)
    if metadata.get("sha256") != cnf_sha256:
        raise AssertionError(f"CNF metadata hash mismatch for {stem}")

    decompressed_digest = hashlib.sha256()
    with lzma.open(proof_path, "rb") as handle:
        proof = handle.read()
    decompressed_digest.update(proof)

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
            "decompressed_bytes": len(proof),
            "decompressed_sha256": decompressed_digest.hexdigest(),
        },
        "checker": {
            "result": "VERIFIED",
            "exit_code": completed.returncode,
            "wall_seconds": round(elapsed, 6),
            "log": log_path.name,
            "log_sha256": file_sha256(log_path),
        },
    }


def index_branches(
    records: object,
    label: str,
) -> dict[int, dict[str, object]]:
    if not isinstance(records, list):
        raise AssertionError(f"{label} branch records are missing")
    if len(records) != len(EXPECTED_BRANCHES):
        raise AssertionError(f"{label} must contain exactly four branches")
    if not all(isinstance(record, dict) for record in records):
        raise AssertionError(f"{label} branch record is not an object")
    branches = [record.get("branch") for record in records]
    if len(set(branches)) != len(branches):
        raise AssertionError(f"{label} contains duplicate branches")
    if set(branches) != set(EXPECTED_BRANCHES):
        raise AssertionError(f"{label} branch inventory is unexpected")
    return {int(record["branch"]): record for record in records}


def validate_supporting_artifact(
    manifest_path: Path,
    record: object,
    label: str,
) -> None:
    if not isinstance(record, dict):
        raise AssertionError(f"certificate manifest {label} is missing")
    artifact = record.get("artifact")
    expected_sha256 = record.get("sha256")
    if not isinstance(artifact, str) or not isinstance(expected_sha256, str):
        raise AssertionError(f"certificate manifest {label} is incomplete")
    artifact_path = manifest_path.parent / artifact
    if file_sha256(artifact_path) != expected_sha256:
        raise AssertionError(f"certificate manifest {label} hash mismatch")


def validate_certificate_manifest(
    manifest_path: Path,
    replayed_branches: list[dict[str, object]],
) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    if manifest.get("verification_passed") is not True:
        raise AssertionError("certificate manifest is not verified")
    if manifest.get("claim") != CLAIM:
        raise AssertionError("certificate manifest claim changed")
    if manifest.get("claim_boundary") != CLAIM_BOUNDARY:
        raise AssertionError("certificate manifest claim boundary changed")
    validate_supporting_artifact(
        manifest_path,
        manifest.get("coverage"),
        "coverage audit",
    )
    validate_supporting_artifact(
        manifest_path,
        manifest.get("cnf_audit"),
        "CNF audit",
    )

    expected_by_branch = index_branches(
        manifest.get("branches"),
        "certificate manifest",
    )
    observed_by_branch = index_branches(
        replayed_branches,
        "proof replay",
    )
    for branch in EXPECTED_BRANCHES:
        expected = expected_by_branch[branch]
        observed = observed_by_branch[branch]
        if observed["cnf"] != expected.get("cnf"):
            raise AssertionError(f"manifest CNF mismatch for branch {branch}")
        if observed["proof"] != expected.get("proof"):
            raise AssertionError(f"manifest proof mismatch for branch {branch}")
        checker = observed.get("checker")
        if (
            not isinstance(checker, dict)
            or checker.get("result") != "VERIFIED"
            or checker.get("exit_code") != 0
        ):
            raise AssertionError(f"fresh replay failed for branch {branch}")
    return file_sha256(manifest_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cnf_directory", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("--checker", type=Path)
    parser.add_argument("--checker-source", type=Path, required=True)
    parser.add_argument(
        "--checker-sha256",
        help=(
            "optional platform-specific checker binary hash; the pinned "
            "clean source commit is always required"
        ),
    )
    parser.add_argument(
        "--fresh-checker-build",
        action="store_true",
        help=(
            "compile a fresh checker from the pinned clean source; required "
            "for release-grade replay"
        ),
    )
    parser.add_argument(
        "--cc",
        default="cc",
        help="C compiler used by --fresh-checker-build",
    )
    parser.add_argument(
        "--certificate-manifest",
        type=Path,
        required=True,
    )
    parser.add_argument("--log-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.fresh_checker_build and args.checker is None:
        parser.error(
            "a prebuilt --checker is required without --fresh-checker-build"
        )
    if args.fresh_checker_build and args.checker_sha256 is not None:
        parser.error("--checker-sha256 applies only to a prebuilt checker")

    observed_checker_commit = source_commit(args.checker_source)
    if observed_checker_commit != EXPECTED_CHECKER_SOURCE_COMMIT:
        raise AssertionError("unexpected drat-trim source commit")
    require_clean_source_tree(args.checker_source)
    args.log_directory.mkdir(parents=True, exist_ok=True)
    checker_build = None
    if args.fresh_checker_build:
        checker, checker_build = build_fresh_checker(
            args.checker_source,
            args.log_directory,
            args.cc,
        )
    else:
        checker = args.checker
        if checker.resolve() != (
            args.checker_source / "drat-trim"
        ).resolve():
            raise AssertionError("checker is not the pinned source build")
    observed_checker_sha256 = file_sha256(checker)
    if (
        args.checker_sha256 is not None
        and observed_checker_sha256 != args.checker_sha256
    ):
        raise AssertionError("unexpected drat-trim binary hash")

    results = [
        replay_branch(
            checker,
            args.cnf_directory,
            args.evidence_directory,
            args.log_directory,
            branch,
        )
        for branch in EXPECTED_BRANCHES
    ]
    certificate_manifest_sha256 = validate_certificate_manifest(
        args.certificate_manifest,
        results,
    )
    release_grade_replay = args.fresh_checker_build
    record = {
        "claim": CLAIM if release_grade_replay else None,
        "claim_boundary": CLAIM_BOUNDARY,
        "scope": "complete retained certificate replay",
        "checker": checker.name,
        "checker_sha256": observed_checker_sha256,
        "checker_sha256_requirement": args.checker_sha256,
        "checker_source_commit": observed_checker_commit,
        "checker_build": checker_build,
        "proof_family": "four root-adjacency branches",
        "expected_branch_count": len(EXPECTED_BRANCHES),
        "verified_branch_count": len(results),
        "branches": results,
        "selected_branches_verified": True,
        "all_expected_branches_verified": True,
        "release_grade_replay": release_grade_replay,
        "certificate_manifest": {
            "path": args.certificate_manifest.name,
            "sha256": certificate_manifest_sha256,
        },
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
