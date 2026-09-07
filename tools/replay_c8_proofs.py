#!/usr/bin/env python3
"""Stream and verify compressed 3^8 1^19 DRAT proofs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from c8_certificate_branches import (
    RETAINED_CANONICAL_BRANCHES,
    RETAINED_T4_SPLIT_BRANCHES,
    ROOT_BRANCHES,
    CanonicalBranch,
    T4SplitBranch,
    canonical_stem,
    t4_split_stem,
)
from c8_proof_artifacts import (
    open_decompressed_proof,
    resolve_compressed_proof,
    validate_source_proof_record,
)
from record_c8_solver_run import classify_artifact_binding
from verify_c8_branch_coverage import EXPECTED_BRANCHES
from verify_c8_certificates import verify_audits


EXPECTED_CHECKER_SOURCE_COMMIT = (
    "2e3b2dc0ecf938addbd779d42877b6ed69d9a985"
)
EXPECTED_HISTORICAL_CHECKER_SHA256 = (
    "f58f63b0f76945d4c4c9ff6e87afaf870f579e67c0f7cca589492df8fc7ebd47"
)
EXPECTED_SOLVER_SOURCE_COMMIT = (
    "8af8e56f174b778aef3aa45af9f739b2a5f492c2"
)
EXPECTED_SOLVER_SHA256 = (
    "c86c7ccc2f727e1ef4716fd2fcf69539fbe0e8b1da8d89341fb48d643a3aeb28"
)

if ROOT_BRANCHES != EXPECTED_BRANCHES:
    raise AssertionError("shared c8 root branch inventory changed")


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


def parse_solver_exit_code(solver_log: str) -> int:
    values = {
        int(value)
        for value in re.findall(
            r"^(?:c exit |kissat_exit=)([0-9]+)$",
            solver_log,
            re.MULTILINE,
        )
    }
    if not values:
        raise AssertionError("solver exit marker is missing")
    if values != {20}:
        raise AssertionError(f"unexpected solver exit markers: {values}")
    return 20


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


def certificate_key(record: dict[str, object]) -> tuple[object, ...]:
    return (
        *tuple(record["branch"]),
        record.get("matrix_type"),
    )


def index_certificate_records(
    records: object,
    label: str,
) -> dict[tuple[object, ...], dict[str, object]]:
    expected_keys = {
        (*branch, None)
        for branch in RETAINED_CANONICAL_BRANCHES
    } | {
        (4, root, 0, matrix_type)
        for root, matrix_type in RETAINED_T4_SPLIT_BRANCHES
    }
    if not isinstance(records, list):
        raise AssertionError(f"{label} branch records are missing")
    if len(records) != len(expected_keys):
        raise AssertionError(f"{label} must contain exactly ten branches")
    if not all(isinstance(record, dict) for record in records):
        raise AssertionError(f"{label} branch record is not an object")
    keys = [certificate_key(record) for record in records]
    if len(set(keys)) != len(keys):
        raise AssertionError(f"{label} contains duplicate branches")
    if set(keys) != expected_keys:
        raise AssertionError(f"{label} branch inventory is unexpected")
    return {
        certificate_key(record): record
        for record in records
    }


def validate_certificate_branch_record(
    expected: dict[str, object],
    observed: dict[str, object],
    key: tuple[object, ...],
) -> None:
    for label, observed_value, expected_value in (
        ("CNF", observed["cnf"], expected["cnf"]),
        (
            "source proof",
            observed["source_proof"],
            expected["source_proof"],
        ),
        ("proof", observed["proof"], expected["compacted_proof"]),
        (
            "artifact binding",
            observed["artifact_binding"],
            expected["artifact_binding"],
        ),
        ("run record", observed["run_record"], expected["run_record"]),
        (
            "compaction record",
            observed["compaction_record"],
            expected["compaction_record"],
        ),
    ):
        if observed_value != expected_value:
            raise AssertionError(f"manifest {label} mismatch for {key}")
    if (
        observed["solver"]["log_sha256"]
        != expected["solver"]["log_sha256"]
    ):
        raise AssertionError(f"manifest solver log mismatch for {key}")


def validate_certificate_manifest(
    manifest_path: Path,
    replayed_branches: list[dict[str, object]],
    canonical_formula_directory: Path,
    t4_formula_directory: Path,
) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    if manifest.get("verification_passed") is not True:
        raise AssertionError("certificate manifest is not verified")
    family = manifest.get("certificate_family")
    if family != {
        "canonical_branches": 6,
        "strengthened_t4_branches": 4,
        "total_branches": 10,
    }:
        raise AssertionError("unexpected certificate family")

    audit_records = manifest.get("audits")
    if not isinstance(audit_records, dict):
        raise AssertionError("certificate manifest audits are missing")
    audit_root = manifest_path.parent
    observed_audits = verify_audits(
        canonical_formula_directory,
        t4_formula_directory,
        audit_root / audit_records["coverage"]["artifact"],
        audit_root / audit_records["canonical_cnf_audit"]["artifact"],
        (
            audit_root
            / audit_records["canonical_semantic_audit"]["artifact"]
        ),
        audit_root / audit_records["t4_matrix_reduction"]["artifact"],
        audit_root / audit_records["t4_semantic_audit"]["artifact"],
    )
    if observed_audits != audit_records:
        raise AssertionError(
            "certificate manifest audits differ from current formulas"
        )

    expected_by_key = index_certificate_records(
        manifest.get("branches"),
        "certificate manifest",
    )
    observed_by_key = index_certificate_records(
        replayed_branches,
        "proof replay",
    )
    for key, observed in observed_by_key.items():
        expected = expected_by_key[key]
        validate_certificate_branch_record(expected, observed, key)
    return file_sha256(manifest_path)


def parse_branch(value: str) -> CanonicalBranch:
    fields = value.replace(",", "-").split("-")
    if len(fields) != 3:
        raise argparse.ArgumentTypeError(
            "branch must have the form triangle-adjacent-missed"
        )
    try:
        branch = tuple(int(field) for field in fields)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "branch fields must be integers"
        ) from error
    if branch not in EXPECTED_BRANCHES:
        raise argparse.ArgumentTypeError(f"unexpected branch: {branch}")
    return branch


def parse_t4_split_branch(value: str) -> T4SplitBranch:
    root_text, separator, matrix_type = value.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError(
            "t4 split branch must have the form root:matrix"
        )
    try:
        branch = (int(root_text), matrix_type)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "t4 split root field must be an integer"
        ) from error
    if branch not in RETAINED_T4_SPLIT_BRANCHES:
        raise argparse.ArgumentTypeError(
            f"unexpected t4 split branch: {branch}"
        )
    return branch


def replay_artifact(
    checker: Path,
    artifact_directory: Path,
    proof_directory: Path,
    solver_log_directory: Path,
    log_directory: Path,
    stem: str,
    branch: CanonicalBranch,
    matrix_type: str | None = None,
) -> dict[str, object]:
    metadata_path = artifact_directory / f"{stem}.json"
    cnf_path = artifact_directory / f"{stem}.cnf"
    logical_proof_name = f"{stem}.drat.xz"
    run_path = proof_directory / f"{stem}-run.json"
    compaction_path = proof_directory / f"{stem}-compaction.json"
    extraction_log_path = proof_directory / f"{stem}-extract.log"
    verification_log_path = proof_directory / f"{stem}-verify.log"
    solver_log_path = solver_log_directory / f"{stem}-proof.log"
    checker_log_path = log_directory / f"{stem}-fresh-drat-trim.log"
    for path in (
        metadata_path,
        cnf_path,
        run_path,
        compaction_path,
        extraction_log_path,
        verification_log_path,
        solver_log_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    run = json.loads(run_path.read_text(encoding="ascii"))
    compaction = json.loads(compaction_path.read_text(encoding="ascii"))
    expected_metadata = {
        "order": 43,
        "prime": 3,
        "cycles": 8,
        "fixed": 19,
        "homogeneous_size": 5,
        "degree_bounds": [18, 24],
        "root_adjacent_cycles": None,
    }
    for field, expected in expected_metadata.items():
        if metadata.get(field) != expected:
            raise AssertionError(
                f"unexpected {field} metadata for {stem}"
            )
    observed_branch = (
        int(metadata["triangle_cycles"]),
        int(metadata["root_adjacent_triangle_cycles"]),
        int(metadata["root_nonadjacent_independent_cycles"]),
    )
    if observed_branch != branch:
        raise AssertionError(f"branch metadata mismatch for {stem}")
    if metadata.get("order_three_eight_structure") is not True:
        raise AssertionError(f"structured formula marker missing for {stem}")
    if matrix_type is None:
        if metadata.get("t4_mixed_matrix") is not None:
            raise AssertionError(f"unexpected matrix metadata for {stem}")
    else:
        if branch[0] != 4 or branch[2] != 0:
            raise AssertionError(f"invalid t4 split branch for {stem}")
        if metadata.get("t4_mixed_matrix") != matrix_type:
            raise AssertionError(f"matrix metadata mismatch for {stem}")
        expected_exclusion = branch[1] == 1
        if (
            metadata.get("exclude_zero_fixed_signatures")
            is not expected_exclusion
        ):
            raise AssertionError(
                f"fixed-signature exclusion mismatch for {stem}"
            )
    if file_sha256(cnf_path) != metadata["sha256"]:
        raise AssertionError(f"CNF hash mismatch for {stem}")

    solver_log = solver_log_path.read_text(encoding="ascii")
    if "s UNSATISFIABLE" not in solver_log:
        raise AssertionError(f"solver did not certify UNSAT for {stem}")
    parse_solver_exit_code(solver_log)
    if (
        f"c Solver source commit {EXPECTED_SOLVER_SOURCE_COMMIT}"
        not in solver_log
    ):
        raise AssertionError(f"solver source commit missing for {stem}")
    if f"c Solver SHA-256 {EXPECTED_SOLVER_SHA256}" not in solver_log:
        raise AssertionError(f"solver binary hash missing for {stem}")
    expected_run_cnf = {
        "path": cnf_path.name,
        "bytes": cnf_path.stat().st_size,
        "sha256": metadata["sha256"],
        "variables": metadata["variables"],
        "clauses": metadata["clauses"],
    }
    if run.get("record_complete") is not True:
        raise AssertionError(f"solver run record is incomplete for {stem}")
    if run.get("branch") != list(branch):
        raise AssertionError(f"solver run branch mismatch for {stem}")
    if run.get("matrix_type") != matrix_type:
        raise AssertionError(f"solver run matrix mismatch for {stem}")
    if run.get("cnf") != expected_run_cnf:
        raise AssertionError(f"solver run CNF mismatch for {stem}")
    solver_record = run.get("solver")
    if not isinstance(solver_record, dict):
        raise AssertionError(f"solver run details missing for {stem}")
    expected_solver_record = {
        "result": "UNSATISFIABLE",
        "exit_code": 20,
        "wall_seconds": float(
            required_match(
                r"^real ([0-9.]+)$",
                solver_log,
                f"solver time for {stem}",
            ).group(1)
        ),
        "source_commit": EXPECTED_SOLVER_SOURCE_COMMIT,
        "binary_sha256": EXPECTED_SOLVER_SHA256,
        "log": solver_log_path.name,
        "log_sha256": file_sha256(solver_log_path),
    }
    if solver_record != expected_solver_record:
        raise AssertionError(f"solver run provenance mismatch for {stem}")
    source_proof = run.get("proof")
    if not isinstance(source_proof, dict):
        raise AssertionError(f"source proof record missing for {stem}")
    artifact_binding = classify_artifact_binding(
        solver_log,
        metadata["sha256"],
        int(source_proof["compressed_bytes"]),
        str(source_proof["compressed_sha256"]),
        allow_post_run_attestation=True,
    )
    if run.get("artifact_binding") != artifact_binding:
        raise AssertionError(f"artifact binding mismatch for {stem}")
    expected_compaction_cnf = {
        "path": cnf_path.name,
        "bytes": cnf_path.stat().st_size,
        "sha256": metadata["sha256"],
    }
    if compaction.get("cnf") != expected_compaction_cnf:
        raise AssertionError(f"compaction CNF mismatch for {stem}")
    compaction_source = compaction.get("source_proof")
    if not isinstance(compaction_source, dict):
        raise AssertionError(f"compaction source proof missing for {stem}")
    validate_source_proof_record(
        compaction_source,
        source_proof,
        extraction_log_path.read_text(
            encoding="ascii",
            errors="replace",
        ),
        stem,
    )
    if compaction.get("checker") != {
        "path": "drat-trim",
        "sha256": EXPECTED_HISTORICAL_CHECKER_SHA256,
        "source_commit": EXPECTED_CHECKER_SOURCE_COMMIT,
    }:
        raise AssertionError(f"compaction checker mismatch for {stem}")
    if compaction.get("verified") is not True:
        raise AssertionError(f"compaction is not verified for {stem}")
    compacted = compaction.get("compacted_proof")
    if not isinstance(compacted, dict):
        raise AssertionError(f"compacted proof record missing for {stem}")
    proof_artifact = resolve_compressed_proof(
        proof_directory,
        logical_proof_name,
        compacted,
    )
    for field, log_path in (
        ("extraction", extraction_log_path),
        ("verification", verification_log_path),
    ):
        details = compaction.get(field)
        if not isinstance(details, dict):
            raise AssertionError(f"compaction {field} missing for {stem}")
        if details.get("log") != log_path.name:
            raise AssertionError(f"compaction {field} path mismatch for {stem}")
        if details.get("log_sha256") != file_sha256(log_path):
            raise AssertionError(f"compaction {field} hash mismatch for {stem}")
        if field == "extraction" and details.get("strategy") not in {
            "single-pass",
            "fixpoint",
        }:
            raise AssertionError(
                f"compaction extraction strategy mismatch for {stem}"
            )
        log_text = log_path.read_text(encoding="ascii", errors="replace")
        if (
            "s VERIFIED" not in log_text
            or "drat_trim_exit_code=0" not in log_text
        ):
            raise AssertionError(
                f"compaction {field} is not verified for {stem}"
            )

    started = time.perf_counter()
    proof_digest = hashlib.sha256()
    proof_bytes = 0
    with checker_log_path.open("wb") as checker_log:
        process = subprocess.Popen(
            [str(checker), str(cnf_path), "-i"],
            stdin=subprocess.PIPE,
            stdout=checker_log,
            stderr=subprocess.STDOUT,
        )
        if process.stdin is None:
            raise AssertionError("failed to open checker input pipe")
        try:
            with open_decompressed_proof(proof_artifact) as handle:
                for block in iter(
                    lambda: handle.read(1024 * 1024),
                    b"",
                ):
                    proof_digest.update(block)
                    proof_bytes += len(block)
                    process.stdin.write(block)
            process.stdin.close()
            return_code = process.wait()
        except BaseException:
            if not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
    elapsed = time.perf_counter() - started

    with checker_log_path.open("ab") as checker_log:
        checker_log.write(
            f"drat_trim_exit_code={return_code}\n".encode("ascii")
        )
    output = checker_log_path.read_text(
        encoding="ascii",
        errors="replace",
    )

    if return_code != 0:
        raise AssertionError(
            f"drat-trim returned {return_code} for {stem}"
        )
    if "s VERIFIED" not in output:
        raise AssertionError(f"drat-trim did not verify {stem}")

    checker_bytes = int(
        required_match(
            r"read ([0-9]+) bytes from proof file",
            output,
            f"checker byte count for {stem}",
        ).group(1)
    )
    if checker_bytes != proof_bytes:
        raise AssertionError(
            f"decompressed proof byte mismatch for {stem}"
        )
    expected_compacted = {
        "path": logical_proof_name,
        "role": "retained-core",
        "compressed_bytes": proof_artifact.compressed_bytes,
        "compressed_sha256": proof_artifact.compressed_sha256,
        "decompressed_bytes": proof_bytes,
        "decompressed_sha256": proof_digest.hexdigest(),
    }
    if proof_artifact.parts is not None:
        expected_compacted["parts"] = [
            dict(part)
            for part in proof_artifact.parts
        ]
    if compacted != expected_compacted:
        raise AssertionError(f"compacted proof record mismatch for {stem}")

    record = {
        "artifact_binding": artifact_binding,
        "branch": list(branch),
        "cnf": {
            "path": cnf_path.name,
            "bytes": cnf_path.stat().st_size,
            "sha256": metadata["sha256"],
            "variables": metadata["variables"],
            "clauses": metadata["clauses"],
        },
        "proof": dict(expected_compacted),
        "source_proof": dict(compaction_source),
        "solver": {
            "result": "UNSATISFIABLE",
            "exit_code": 20,
            "wall_seconds": solver_record["wall_seconds"],
            "log": solver_log_path.name,
            "log_sha256": file_sha256(solver_log_path),
            "artifact_binding": artifact_binding,
        },
        "checker": {
            "result": "VERIFIED",
            "exit_code": return_code,
            "wall_seconds": round(elapsed, 6),
            "log": checker_log_path.name,
            "log_sha256": file_sha256(checker_log_path),
        },
        "run_record": {
            "path": run_path.name,
            "sha256": file_sha256(run_path),
        },
        "compaction_record": {
            "path": compaction_path.name,
            "sha256": file_sha256(compaction_path),
        },
    }
    if matrix_type is not None:
        record["matrix_type"] = matrix_type
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument(
        "--proof-directory",
        type=Path,
        help=(
            "directory containing compressed proofs; defaults to the "
            "artifact directory"
        ),
    )
    parser.add_argument(
        "--solver-log-directory",
        type=Path,
        help=(
            "directory containing solver logs; defaults to the artifact "
            "directory"
        ),
    )
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
        "--branch",
        type=parse_branch,
        action="append",
        dest="branches",
    )
    parser.add_argument(
        "--t4-split-artifact-directory",
        type=Path,
        help="directory containing the four strengthened t=4 formulas",
    )
    parser.add_argument(
        "--t4-split-proof-directory",
        type=Path,
        help="directory containing strengthened t=4 proofs",
    )
    parser.add_argument(
        "--t4-split-solver-log-directory",
        type=Path,
        help=(
            "directory containing strengthened t=4 solver logs; defaults "
            "to the canonical solver-log directory"
        ),
    )
    parser.add_argument(
        "--t4-split-branch",
        type=parse_t4_split_branch,
        action="append",
        dest="t4_split_branches",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="permit an explicitly selected non-release replay",
    )
    parser.add_argument(
        "--direct-t4-crosscheck",
        action="store_true",
        help=(
            "replay the legacy eight direct root branches as a non-release "
            "cross-check"
        ),
    )
    parser.add_argument("--certificate-manifest", type=Path)
    parser.add_argument("--log-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    retained_mode = args.t4_split_artifact_directory is not None
    if retained_mode and args.direct_t4_crosscheck:
        parser.error(
            "split retained mode and direct t4 cross-check are exclusive"
        )
    if not retained_mode and not args.direct_t4_crosscheck:
        parser.error(
            "the retained t4 split directory is required unless the "
            "direct t4 cross-check is explicitly selected"
        )
    if retained_mode and args.t4_split_proof_directory is None:
        parser.error(
            "retained mode requires --t4-split-proof-directory"
        )
    explicit_selection = bool(args.branches or args.t4_split_branches)
    if explicit_selection and not args.allow_partial:
        parser.error("explicit branch selection requires --allow-partial")
    if retained_mode and not args.allow_partial:
        if args.certificate_manifest is None:
            parser.error(
                "complete retained replay requires --certificate-manifest"
            )
        if not args.fresh_checker_build:
            parser.error(
                "complete retained replay requires --fresh-checker-build"
            )
    elif args.certificate_manifest is not None:
        parser.error(
            "certificate manifest is accepted only for full retained replay"
        )
    if not args.fresh_checker_build and args.checker is None:
        parser.error(
            "a prebuilt --checker is required without --fresh-checker-build"
        )
    if args.fresh_checker_build and args.checker_sha256 is not None:
        parser.error(
            "--checker-sha256 applies only to a prebuilt checker"
        )

    proof_directory = (
        args.proof_directory
        if args.proof_directory is not None
        else args.artifact_directory
    )
    solver_log_directory = (
        args.solver_log_directory
        if args.solver_log_directory is not None
        else args.artifact_directory
    )
    t4_split_proof_directory = (
        args.t4_split_proof_directory
        if args.t4_split_proof_directory is not None
        else args.t4_split_artifact_directory
    )
    t4_split_solver_log_directory = (
        args.t4_split_solver_log_directory
        if args.t4_split_solver_log_directory is not None
        else solver_log_directory
    )

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
    if explicit_selection:
        selected_branches = tuple(args.branches or ())
        selected_t4_split_branches = tuple(
            args.t4_split_branches or ()
        )
    elif retained_mode:
        selected_branches = RETAINED_CANONICAL_BRANCHES
        selected_t4_split_branches = RETAINED_T4_SPLIT_BRANCHES
    else:
        selected_branches = ROOT_BRANCHES
        selected_t4_split_branches = ()
    if retained_mode and any(
        branch not in RETAINED_CANONICAL_BRANCHES
        for branch in selected_branches
    ):
        parser.error("retained mode accepts only t=2 and t=3 branches")
    if not retained_mode and selected_t4_split_branches:
        parser.error("direct t4 cross-check cannot select split branches")

    if len(set(selected_branches)) != len(selected_branches):
        raise AssertionError("duplicate replay branch")
    if (
        len(set(selected_t4_split_branches))
        != len(selected_t4_split_branches)
    ):
        raise AssertionError("duplicate t4 split replay branch")
    if (
        selected_t4_split_branches
        and args.t4_split_artifact_directory is None
    ):
        raise AssertionError(
            "t4 split branches require a split artifact directory"
        )

    branches = [
        replay_artifact(
            checker,
            args.artifact_directory,
            proof_directory,
            solver_log_directory,
            args.log_directory,
            canonical_stem(branch),
            branch,
        )
        for branch in selected_branches
    ]
    if retained_mode:
        branches.extend(
            replay_artifact(
                checker,
                args.t4_split_artifact_directory,
                t4_split_proof_directory,
                t4_split_solver_log_directory,
                args.log_directory,
                t4_split_stem(branch),
                (4, branch[0], 0),
                branch[1],
            )
            for branch in selected_t4_split_branches
        )
    expected_branch_count = (
        len(RETAINED_CANONICAL_BRANCHES)
        + len(RETAINED_T4_SPLIT_BRANCHES)
        if retained_mode
        else len(ROOT_BRANCHES)
    )
    all_expected = (
        set(selected_branches) == set(RETAINED_CANONICAL_BRANCHES)
        and set(selected_t4_split_branches)
        == set(RETAINED_T4_SPLIT_BRANCHES)
        if retained_mode
        else (
            set(selected_branches) == set(ROOT_BRANCHES)
            and not selected_t4_split_branches
        )
    )
    release_grade_replay = (
        retained_mode
        and all_expected
        and not args.allow_partial
    )
    certificate_manifest_sha256 = None
    if release_grade_replay:
        certificate_manifest_sha256 = validate_certificate_manifest(
            args.certificate_manifest,
            branches,
            args.artifact_directory,
            args.t4_split_artifact_directory,
        )

    record = {
        "claim": (
            "No graph on 43 vertices with clique number and independence "
            "number at most 4 has an automorphism of cycle type 3^8 1^19."
            if release_grade_replay
            else None
        ),
        "claim_boundary": (
            "This certificate-assisted exclusion does not determine R(5,5), "
            "change 43 <= R(5,5) <= 46, establish asymmetry, or exclude "
            "graphs with trivial automorphism group."
        ),
        "scope": (
            "complete retained certificate replay"
            if release_grade_replay
            else (
                "partial proof replay"
                if args.allow_partial
                else "legacy direct t4 cross-check"
            )
        ),
        "checker": checker.name,
        "checker_sha256": observed_checker_sha256,
        "checker_sha256_requirement": args.checker_sha256,
        "checker_source_commit": observed_checker_commit,
        "checker_build": checker_build,
        "solver_source_commit": EXPECTED_SOLVER_SOURCE_COMMIT,
        "proof_family": (
            "six canonical branches plus four strengthened t4 branches"
            if retained_mode
            else "eight normalized root branches"
        ),
        "expected_branch_count": expected_branch_count,
        "verified_branch_count": len(branches),
        "branches": branches,
        "selected_branches_verified": True,
        "all_expected_branches_verified": all_expected,
        "release_grade_replay": release_grade_replay,
        "certificate_manifest": (
            {
                "path": args.certificate_manifest.name,
                "sha256": certificate_manifest_sha256,
            }
            if certificate_manifest_sha256 is not None
            else None
        ),
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
