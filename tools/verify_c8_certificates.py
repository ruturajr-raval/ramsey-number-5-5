#!/usr/bin/env python3
"""Verify the retained 3^8 1^19 certificate package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from c8_certificate_branches import (
    RETAINED_CANONICAL_BRANCHES,
    RETAINED_T4_SPLIT_BRANCHES,
    ROOT_BRANCHES,
    CanonicalBranch,
    canonical_stem,
    t4_split_stem,
)
from c8_proof_artifacts import (
    decompressed_details,
    resolve_compressed_proof,
    validate_source_proof_record,
)
from record_c8_solver_run import classify_artifact_binding


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOLVER_SOURCE_COMMIT = (
    "8af8e56f174b778aef3aa45af9f739b2a5f492c2"
)
EXPECTED_SOLVER_SHA256 = (
    "c86c7ccc2f727e1ef4716fd2fcf69539fbe0e8b1da8d89341fb48d643a3aeb28"
)
EXPECTED_CHECKER_SOURCE_COMMIT = (
    "2e3b2dc0ecf938addbd779d42877b6ed69d9a985"
)
EXPECTED_CHECKER_SHA256 = (
    "f58f63b0f76945d4c4c9ff6e87afaf870f579e67c0f7cca589492df8fc7ebd47"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def require_equal(
    observed: object,
    expected: object,
    label: str,
) -> None:
    if observed != expected:
        raise AssertionError(
            f"{label} mismatch: observed={observed!r}, "
            f"expected={expected!r}"
        )


def verify_audits(
    canonical_formula_directory: Path,
    t4_formula_directory: Path,
    coverage_path: Path,
    canonical_audit_path: Path,
    canonical_semantic_path: Path,
    t4_reduction_path: Path,
    t4_semantic_path: Path,
) -> dict[str, object]:
    coverage = load_json(coverage_path)
    canonical_audit = load_json(canonical_audit_path)
    canonical_semantic = load_json(canonical_semantic_path)
    t4_reduction = load_json(t4_reduction_path)
    t4_semantic = load_json(t4_semantic_path)

    require_equal(
        coverage.get("arithmetic_coverage_complete"),
        True,
        "arithmetic coverage",
    )
    require_equal(
        coverage.get("verifier_sha256"),
        file_sha256(ROOT / "tools/verify_c8_branch_coverage.py"),
        "coverage verifier",
    )
    require_equal(
        {tuple(branch) for branch in coverage["solved_branches"]},
        set(ROOT_BRANCHES),
        "coverage root branches",
    )
    require_equal(
        canonical_audit.get("audit_passed"),
        True,
        "canonical CNF audit",
    )
    require_equal(
        canonical_audit.get("provenance"),
        {
            "auditor": "tools/verify_c8_branch_artifacts.py",
            "auditor_sha256": file_sha256(
                ROOT / "tools/verify_c8_branch_artifacts.py"
            ),
        },
        "canonical audit provenance",
    )
    require_equal(
        {
            tuple(branch["branch"])
            for branch in canonical_audit["branches"]
        },
        set(ROOT_BRANCHES),
        "canonical audit branches",
    )
    require_equal(
        canonical_semantic.get("all_semantically_identical"),
        True,
        "canonical semantic audit",
    )
    require_equal(
        canonical_semantic.get("provenance"),
        {
            "generator": "src/orbit_cnf.py",
            "generator_sha256": file_sha256(ROOT / "src/orbit_cnf.py"),
            "reference_verifier": (
                "tools/verify_c8_formula_semantics.py"
            ),
            "reference_verifier_sha256": file_sha256(
                ROOT / "tools/verify_c8_formula_semantics.py"
            ),
        },
        "canonical semantic provenance",
    )
    require_equal(
        {
            tuple(branch["branch"])
            for branch in canonical_semantic["branches"]
            if branch.get("semantic_match") is True
        },
        set(ROOT_BRANCHES),
        "canonical semantic branches",
    )
    require_equal(t4_reduction.get("verified"), True, "t4 reduction")
    require_equal(
        t4_reduction.get("verifier_sha256"),
        file_sha256(ROOT / "tools/verify_c8_t4_reduction.py"),
        "t4 reduction verifier",
    )
    require_equal(
        t4_reduction.get("labeled_matrices"),
        90,
        "t4 labeled matrix count",
    )
    require_equal(
        t4_reduction.get("distinguished_row_matrix_classes"),
        2,
        "t4 distinguished matrix classes",
    )
    require_equal(
        t4_semantic.get("all_semantically_identical"),
        True,
        "t4 semantic audit",
    )
    require_equal(
        t4_semantic.get("generator_sha256"),
        file_sha256(ROOT / "src/orbit_cnf.py"),
        "t4 semantic generator",
    )
    require_equal(
        t4_semantic.get("reference_verifier_sha256"),
        file_sha256(ROOT / "tools/verify_c8_t4_formula_semantics.py"),
        "t4 semantic verifier",
    )
    observed_split = {
        (
            int(branch["root_adjacent_triangle_cycles"]),
            str(branch["matrix_type"]),
        )
        for branch in t4_semantic["branches"]
        if branch.get("semantic_match") is True
    }
    require_equal(
        observed_split,
        set(RETAINED_T4_SPLIT_BRANCHES),
        "t4 semantic branches",
    )

    canonical_audit_by_branch = {
        tuple(branch["branch"]): branch
        for branch in canonical_audit["branches"]
    }
    canonical_semantic_by_branch = {
        tuple(branch["branch"]): branch
        for branch in canonical_semantic["branches"]
    }
    for branch in ROOT_BRANCHES:
        stem = canonical_stem(branch)
        cnf_path = canonical_formula_directory / f"{stem}.cnf"
        metadata_path = canonical_formula_directory / f"{stem}.json"
        metadata = load_json(metadata_path)
        actual = {
            "bytes": cnf_path.stat().st_size,
            "sha256": file_sha256(cnf_path),
            "variables": int(metadata["variables"]),
            "clauses": int(metadata["clauses"]),
        }
        for label, audited in (
            ("canonical CNF audit", canonical_audit_by_branch[branch]),
            (
                "canonical semantic audit",
                canonical_semantic_by_branch[branch],
            ),
        ):
            for field, expected in actual.items():
                require_equal(
                    audited.get(field),
                    expected,
                    f"{stem} {label} {field}",
                )

    t4_semantic_by_branch = {
        (
            int(branch["root_adjacent_triangle_cycles"]),
            str(branch["matrix_type"]),
        ): branch
        for branch in t4_semantic["branches"]
    }
    for branch in RETAINED_T4_SPLIT_BRANCHES:
        stem = t4_split_stem(branch)
        cnf_path = t4_formula_directory / f"{stem}.cnf"
        metadata_path = t4_formula_directory / f"{stem}.json"
        metadata = load_json(metadata_path)
        audited = t4_semantic_by_branch[branch]
        actual = {
            "bytes": cnf_path.stat().st_size,
            "sha256": file_sha256(cnf_path),
            "variables": int(metadata["variables"]),
            "clauses": int(metadata["clauses"]),
        }
        for field, expected in actual.items():
            require_equal(
                audited.get(field),
                expected,
                f"{stem} t4 semantic audit {field}",
            )

    return {
        "coverage": {
            "artifact": coverage_path.name,
            "sha256": file_sha256(coverage_path),
            "root_branches": len(ROOT_BRANCHES),
            "low_exception_configurations": coverage[
                "low_exception_configurations_total"
            ],
            "certificate_configurations": coverage[
                "certificate_configurations"
            ],
        },
        "canonical_cnf_audit": {
            "artifact": canonical_audit_path.name,
            "sha256": file_sha256(canonical_audit_path),
            "branches": len(canonical_audit["branches"]),
        },
        "canonical_semantic_audit": {
            "artifact": canonical_semantic_path.name,
            "sha256": file_sha256(canonical_semantic_path),
            "branches": len(canonical_semantic["branches"]),
        },
        "t4_matrix_reduction": {
            "artifact": t4_reduction_path.name,
            "sha256": file_sha256(t4_reduction_path),
            "labeled_matrices": t4_reduction["labeled_matrices"],
            "matrix_classes": t4_reduction[
                "distinguished_row_matrix_classes"
            ],
        },
        "t4_semantic_audit": {
            "artifact": t4_semantic_path.name,
            "sha256": file_sha256(t4_semantic_path),
            "branches": len(t4_semantic["branches"]),
        },
    }


def verify_branch(
    formula_directory: Path,
    solver_log_directory: Path,
    certificate_directory: Path,
    branch: CanonicalBranch,
    stem: str,
    matrix_type: str | None,
) -> dict[str, object]:
    cnf_path = formula_directory / f"{stem}.cnf"
    metadata_path = formula_directory / f"{stem}.json"
    solver_log_path = solver_log_directory / f"{stem}-proof.log"
    run_path = certificate_directory / f"{stem}-run.json"
    compaction_path = certificate_directory / f"{stem}-compaction.json"
    logical_proof_name = f"{stem}.drat.xz"
    extraction_log_path = certificate_directory / f"{stem}-extract.log"
    verification_log_path = certificate_directory / f"{stem}-verify.log"
    for path in (
        cnf_path,
        metadata_path,
        solver_log_path,
        run_path,
        compaction_path,
        extraction_log_path,
        verification_log_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    metadata = load_json(metadata_path)
    run = load_json(run_path)
    compaction = load_json(compaction_path)
    observed_branch = (
        int(metadata["triangle_cycles"]),
        int(metadata["root_adjacent_triangle_cycles"]),
        int(metadata["root_nonadjacent_independent_cycles"]),
    )
    require_equal(observed_branch, branch, f"{stem} metadata branch")
    require_equal(run.get("branch"), list(branch), f"{stem} run branch")
    require_equal(
        metadata.get("order_three_eight_structure"),
        True,
        f"{stem} structure marker",
    )
    require_equal(
        metadata.get("t4_mixed_matrix"),
        matrix_type,
        f"{stem} matrix type",
    )
    require_equal(run.get("matrix_type"), matrix_type, f"{stem} run matrix")
    if matrix_type is not None:
        require_equal(
            metadata.get("exclude_zero_fixed_signatures"),
            branch[1] == 1,
            f"{stem} zero-signature exclusion",
        )

    cnf_sha256 = file_sha256(cnf_path)
    require_equal(metadata.get("sha256"), cnf_sha256, f"{stem} CNF hash")
    require_equal(
        metadata.get("bytes"),
        cnf_path.stat().st_size,
        f"{stem} CNF bytes",
    )
    expected_cnf = {
        "path": cnf_path.name,
        "bytes": cnf_path.stat().st_size,
        "sha256": cnf_sha256,
        "variables": int(metadata["variables"]),
        "clauses": int(metadata["clauses"]),
    }
    require_equal(run.get("cnf"), expected_cnf, f"{stem} run CNF")
    require_equal(
        compaction.get("cnf"),
        {
            "path": cnf_path.name,
            "bytes": cnf_path.stat().st_size,
            "sha256": cnf_sha256,
        },
        f"{stem} compaction CNF",
    )

    solver = run["solver"]
    require_equal(
        solver.get("result"),
        "UNSATISFIABLE",
        f"{stem} solver result",
    )
    require_equal(solver.get("exit_code"), 20, f"{stem} solver exit")
    require_equal(
        solver.get("source_commit"),
        EXPECTED_SOLVER_SOURCE_COMMIT,
        f"{stem} solver source",
    )
    require_equal(
        solver.get("binary_sha256"),
        EXPECTED_SOLVER_SHA256,
        f"{stem} solver binary",
    )
    require_equal(
        solver.get("log"),
        solver_log_path.name,
        f"{stem} solver log path",
    )
    require_equal(
        solver.get("log_sha256"),
        file_sha256(solver_log_path),
        f"{stem} solver log hash",
    )
    solver_log = solver_log_path.read_text(encoding="ascii")
    if "s UNSATISFIABLE" not in solver_log:
        raise AssertionError(f"{stem} solver log lost UNSAT result")
    artifact_binding = classify_artifact_binding(
        solver_log,
        cnf_sha256,
        int(run["proof"]["compressed_bytes"]),
        str(run["proof"]["compressed_sha256"]),
        allow_post_run_attestation=True,
    )
    require_equal(
        run.get("artifact_binding"),
        artifact_binding,
        f"{stem} artifact binding",
    )

    source_proof = compaction.get("source_proof")
    if not isinstance(source_proof, dict):
        raise AssertionError(f"{stem} source proof record is missing")
    validate_source_proof_record(
        source_proof,
        run.get("proof"),
        extraction_log_path.read_text(
            encoding="ascii",
            errors="replace",
        ),
        stem,
    )
    checker = compaction["checker"]
    require_equal(
        checker.get("source_commit"),
        EXPECTED_CHECKER_SOURCE_COMMIT,
        f"{stem} checker source",
    )
    require_equal(
        checker.get("sha256"),
        EXPECTED_CHECKER_SHA256,
        f"{stem} checker binary",
    )
    require_equal(compaction.get("verified"), True, f"{stem} compaction")

    compacted = compaction["compacted_proof"]
    proof_artifact = resolve_compressed_proof(
        certificate_directory,
        logical_proof_name,
        compacted,
    )
    require_equal(
        compacted.get("role"),
        "retained-core",
        f"{stem} compact proof role",
    )
    require_equal(
        compacted.get("path"),
        logical_proof_name,
        f"{stem} compact proof path",
    )
    require_equal(
        compacted.get("compressed_bytes"),
        proof_artifact.compressed_bytes,
        f"{stem} compact proof bytes",
    )
    require_equal(
        compacted.get("compressed_sha256"),
        proof_artifact.compressed_sha256,
        f"{stem} compact proof hash",
    )
    decompressed_bytes, decompressed_sha256 = decompressed_details(
        proof_artifact
    )
    require_equal(
        compacted.get("decompressed_bytes"),
        decompressed_bytes,
        f"{stem} decompressed proof bytes",
    )
    require_equal(
        compacted.get("decompressed_sha256"),
        decompressed_sha256,
        f"{stem} decompressed proof hash",
    )
    if proof_artifact.parts is None:
        require_equal(
            compacted.get("parts"),
            None,
            f"{stem} compact proof parts",
        )
    else:
        require_equal(
            compacted.get("parts"),
            [dict(part) for part in proof_artifact.parts],
            f"{stem} compact proof parts",
        )

    for field, log_path in (
        ("extraction", extraction_log_path),
        ("verification", verification_log_path),
    ):
        details = compaction[field]
        require_equal(
            details.get("log"),
            log_path.name,
            f"{stem} {field} log path",
        )
        require_equal(
            details.get("log_sha256"),
            file_sha256(log_path),
            f"{stem} {field} log hash",
        )
        if field == "extraction" and details.get("strategy") not in {
            "single-pass",
            "fixpoint",
        }:
            raise AssertionError(
                f"{stem} extraction strategy is not recognized"
            )
        log_text = log_path.read_text(encoding="ascii", errors="replace")
        if "s VERIFIED" not in log_text:
            raise AssertionError(f"{stem} {field} log is not verified")
        if "drat_trim_exit_code=0" not in log_text:
            raise AssertionError(f"{stem} {field} checker exit changed")

    result = {
        "branch": list(branch),
        "cnf": expected_cnf,
        "source_proof": source_proof,
        "compacted_proof": compacted,
        "solver": solver,
        "artifact_binding": artifact_binding,
        "checker": checker,
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
        result["matrix_type"] = matrix_type
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical_formula_directory", type=Path)
    parser.add_argument("t4_formula_directory", type=Path)
    parser.add_argument("certificate_directory", type=Path)
    parser.add_argument("--canonical-solver-log-directory", type=Path)
    parser.add_argument("--t4-solver-log-directory", type=Path)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--canonical-cnf-audit", type=Path, required=True)
    parser.add_argument(
        "--canonical-semantic-audit",
        type=Path,
        required=True,
    )
    parser.add_argument("--t4-reduction", type=Path, required=True)
    parser.add_argument("--t4-semantic-audit", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    canonical_solver_logs = (
        args.canonical_solver_log_directory
        if args.canonical_solver_log_directory is not None
        else args.certificate_directory
    )
    t4_solver_logs = (
        args.t4_solver_log_directory
        if args.t4_solver_log_directory is not None
        else args.certificate_directory
    )
    audits = verify_audits(
        args.canonical_formula_directory,
        args.t4_formula_directory,
        args.coverage,
        args.canonical_cnf_audit,
        args.canonical_semantic_audit,
        args.t4_reduction,
        args.t4_semantic_audit,
    )
    branches = [
        verify_branch(
            args.canonical_formula_directory,
            canonical_solver_logs,
            args.certificate_directory,
            branch,
            canonical_stem(branch),
            None,
        )
        for branch in RETAINED_CANONICAL_BRANCHES
    ]
    branches.extend(
        verify_branch(
            args.t4_formula_directory,
            t4_solver_logs,
            args.certificate_directory,
            (4, branch[0], 0),
            t4_split_stem(branch),
            branch[1],
        )
        for branch in RETAINED_T4_SPLIT_BRANCHES
    )

    manifest = {
        "claim": (
            "No graph on 43 vertices with clique number and independence "
            "number at most 4 admits an automorphism of cycle type "
            "3^8 1^19."
        ),
        "claim_boundary": (
            "The exclusion combines elementary incidence reductions with "
            "proof-checked orbit-CNF branches. It does not determine R(5,5), "
            "change 43 <= R(5,5) <= 46, establish asymmetry, or exclude "
            "graphs with trivial automorphism group."
        ),
        "certificate_family": {
            "canonical_branches": len(RETAINED_CANONICAL_BRANCHES),
            "strengthened_t4_branches": len(
                RETAINED_T4_SPLIT_BRANCHES
            ),
            "total_branches": len(branches),
        },
        "audits": audits,
        "tools": {
            "kissat_source_commit": EXPECTED_SOLVER_SOURCE_COMMIT,
            "kissat_sha256": EXPECTED_SOLVER_SHA256,
            "drat_trim_source_commit": EXPECTED_CHECKER_SOURCE_COMMIT,
            "drat_trim_sha256": EXPECTED_CHECKER_SHA256,
        },
        "branches": branches,
        "verification_passed": True,
    }
    if args.expected_manifest is not None:
        expected = load_json(args.expected_manifest)
        require_equal(manifest, expected, "certificate manifest")

    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
