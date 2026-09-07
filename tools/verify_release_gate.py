#!/usr/bin/env python3
"""Verify release declarations against concrete proof and paper evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from record_paper_build import build_record


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE = ROOT / "research" / "release-gate.json"
EXPECTED_CHECKER_SOURCE_COMMIT = (
    "2e3b2dc0ecf938addbd779d42877b6ed69d9a985"
)
EXPECTED_CANDIDATE_CLAIM = (
    "Fourteen previously uncovered or unfinished prime-order automorphism "
    "cycle types are excluded for hypothetical Ramsey (5,5,43) graphs."
)
C6_CLAIM = (
    "No graph on 43 vertices with clique number and independence "
    "number at most 4 has an automorphism of cycle type 3^6 1^25."
)
C8_CLAIM = (
    "No graph on 43 vertices with clique number and independence "
    "number at most 4 has an automorphism of cycle type 3^8 1^19."
)
GATE_NAMES = {
    "significant_original_result",
    "prior_art_refreshed",
    "final_release_snapshot_audit_passes",
    "claim_scope_audited",
    "limitations_documented",
    "elementary_proof_check_passes",
    "order_three_seven_cycle_audit_passes",
    "branch_coverage_audit_passes",
    "cnf_artifact_audit_passes",
    "retained_drat_checks_pass",
    "clean_environment_replay_passes",
    "paper_build_and_inspection_passes",
    "independent_package_review_passes",
}
CANDIDATE_REQUIRED_GATES = GATE_NAMES - {
    "final_release_snapshot_audit_passes",
    "paper_build_and_inspection_passes",
    "independent_package_review_passes",
}
C8_EXPECTED_KEYS = {
    (2, 0, 0, None),
    (2, 1, 0, None),
    (2, 0, 1, None),
    (3, 0, 0, None),
    (3, 1, 0, None),
    (3, 0, 1, None),
    (4, 0, 0, "two-c4"),
    (4, 0, 0, "c8"),
    (4, 1, 0, "two-c4"),
    (4, 1, 0, "c8"),
}
MANIFEST_LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")
CHECKSUM_LINE_RE = re.compile(
    r"^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$"
)
VERSION_RE = re.compile(
    r"^version:\s*[\"']?([^\"' \n]+)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class EvidencePaths:
    root: Path
    c6_replay: Path
    c8_replay: Path
    c6_manifest: Path
    c8_manifest: Path
    paper_source: Path
    paper_pdf: Path
    paper_log: Path
    paper_record: Path
    release_manifest: Path
    release_dir: Path


def default_evidence_paths(root: Path = ROOT) -> EvidencePaths:
    return EvidencePaths(
        root=root,
        c6_replay=root / "build/proof-replay-c6/fresh-proof-replay.json",
        c8_replay=root / "build/proof-replay-c8/fresh-proof-replay.json",
        c6_manifest=root / "evidence/orbit-p3-c6/certificate-manifest.json",
        c8_manifest=root / "evidence/orbit-p3-c8/certificate-manifest.json",
        paper_source=root / "paper/main.tex",
        paper_pdf=root / "build/paper/main.pdf",
        paper_log=root / "build/paper/main.log",
        paper_record=root / "build/paper/paper-build.json",
        release_manifest=root / "release-manifest.sha256",
        release_dir=root / "dist/release",
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(
    path: Path,
    label: str,
    errors: list[str],
) -> dict[str, object] | None:
    if not path.is_file():
        errors.append(f"{label} is missing: {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"{label} is invalid JSON: {error}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return value


def valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def declaration_errors(record: object, mode: str) -> list[str]:
    if not isinstance(record, dict):
        return ["release gate must be a JSON object"]

    errors: list[str] = []
    if record.get("schema_version") != 2:
        errors.append("release-gate schema version must be 2")
    if record.get("project") != "ramsey-number-5-5":
        errors.append("unexpected release-gate project")
    if record.get("candidate_claim") != EXPECTED_CANDIDATE_CLAIM:
        errors.append("release-gate candidate claim changed")

    gates = record.get("gates")
    if not isinstance(gates, dict):
        errors.append("release-gate checks are missing")
        gates = {}
    else:
        names = set(gates)
        missing = sorted(GATE_NAMES - names)
        unexpected = sorted(names - GATE_NAMES)
        if missing:
            errors.append("release-gate checks are missing: " + ", ".join(missing))
        if unexpected:
            errors.append(
                "release-gate checks are unexpected: " + ", ".join(unexpected)
            )

    required = GATE_NAMES if mode == "final" else CANDIDATE_REQUIRED_GATES
    incomplete = sorted(
        name for name in required if gates.get(name) is not True
    )
    if incomplete:
        errors.append("incomplete release-gate checks: " + ", ".join(incomplete))

    decision = record.get("decision")
    if mode == "final":
        if decision != "release":
            errors.append("release-gate decision is not release")
        if record.get("artifact_reproducibility_ready") is not True:
            errors.append("artifact reproducibility is not ready")
        if record.get("theorem_announcement_ready") is not True:
            errors.append("theorem announcement is not ready")
    elif decision not in {"hold", "release"}:
        errors.append("candidate decision must be hold or release")
    return errors


def replay_manifest_errors(
    replay_path: Path,
    manifest_path: Path,
    family: str,
) -> list[str]:
    errors: list[str] = []
    replay = load_json(replay_path, f"{family} replay", errors)
    manifest = load_json(manifest_path, f"{family} manifest", errors)
    if replay is None or manifest is None:
        return errors

    expected_count = 4 if family == "c6" else 10
    expected_claim = C6_CLAIM if family == "c6" else C8_CLAIM
    for field, expected in (
        ("claim", expected_claim),
        ("scope", "complete retained certificate replay"),
        ("checker_source_commit", EXPECTED_CHECKER_SOURCE_COMMIT),
        ("expected_branch_count", expected_count),
        ("verified_branch_count", expected_count),
        ("selected_branches_verified", True),
        ("all_expected_branches_verified", True),
        ("release_grade_replay", True),
    ):
        if replay.get(field) != expected:
            errors.append(f"{family} replay has unexpected {field}")

    checker_build = replay.get("checker_build")
    if (
        not isinstance(checker_build, dict)
        or checker_build.get("mode") != "fresh-source-build"
    ):
        errors.append(f"{family} replay lacks a fresh checker build")
    else:
        if not valid_sha256(checker_build.get("source_sha256")):
            errors.append(f"{family} checker source hash is invalid")
        build_log = checker_build.get("log")
        build_log_sha256 = checker_build.get("log_sha256")
        if not isinstance(build_log, str) or not valid_sha256(build_log_sha256):
            errors.append(f"{family} checker build log record is invalid")
        else:
            build_log_path = replay_path.parent / build_log
            if (
                not build_log_path.is_file()
                or file_sha256(build_log_path) != build_log_sha256
            ):
                errors.append(f"{family} checker build log hash mismatch")

    checker = replay.get("checker")
    checker_sha256 = replay.get("checker_sha256")
    if not isinstance(checker, str) or not valid_sha256(checker_sha256):
        errors.append(f"{family} checker record is invalid")
    else:
        checker_path = replay_path.parent / checker
        if (
            not checker_path.is_file()
            or file_sha256(checker_path) != checker_sha256
        ):
            errors.append(f"{family} checker binary hash mismatch")

    manifest_binding = replay.get("certificate_manifest")
    manifest_sha256 = file_sha256(manifest_path)
    if not isinstance(manifest_binding, dict):
        errors.append(f"{family} replay has no certificate-manifest binding")
    else:
        if manifest_binding.get("path") != manifest_path.name:
            errors.append(f"{family} replay manifest path changed")
        if manifest_binding.get("sha256") != manifest_sha256:
            errors.append(f"{family} replay manifest hash mismatch")
    if manifest.get("verification_passed") is not True:
        errors.append(f"{family} certificate manifest is not verified")

    replay_branches = replay.get("branches")
    manifest_branches = manifest.get("branches")
    if not isinstance(replay_branches, list):
        errors.append(f"{family} replay branches are missing")
        return errors
    if not isinstance(manifest_branches, list):
        errors.append(f"{family} manifest branches are missing")
        return errors
    if len(replay_branches) != expected_count:
        errors.append(f"{family} replay branch count changed")
    if len(manifest_branches) != expected_count:
        errors.append(f"{family} manifest branch count changed")

    if family == "c6":
        replay_by_key = {
            branch.get("branch"): branch
            for branch in replay_branches
            if isinstance(branch, dict)
        }
        manifest_by_key = {
            branch.get("branch"): branch
            for branch in manifest_branches
            if isinstance(branch, dict)
        }
        if set(replay_by_key) != {0, 1, 2, 3}:
            errors.append("c6 replay branch inventory changed")
        if set(manifest_by_key) != {0, 1, 2, 3}:
            errors.append("c6 manifest branch inventory changed")
        for key in sorted(set(replay_by_key) & set(manifest_by_key)):
            observed = replay_by_key[key]
            expected = manifest_by_key[key]
            for field in ("cnf", "proof"):
                if observed.get(field) != expected.get(field):
                    errors.append(f"c6 branch {key} {field} binding mismatch")
    else:
        family_record = manifest.get("certificate_family")
        if family_record != {
            "canonical_branches": 6,
            "strengthened_t4_branches": 4,
            "total_branches": 10,
        }:
            errors.append("c8 certificate family changed")

        def c8_key(branch: dict[str, object]) -> tuple[object, ...]:
            value = branch.get("branch")
            if not isinstance(value, list):
                return ("invalid",)
            return (*value, branch.get("matrix_type"))

        replay_by_key = {
            c8_key(branch): branch
            for branch in replay_branches
            if isinstance(branch, dict)
        }
        manifest_by_key = {
            c8_key(branch): branch
            for branch in manifest_branches
            if isinstance(branch, dict)
        }
        if set(replay_by_key) != C8_EXPECTED_KEYS:
            errors.append("c8 replay branch inventory changed")
        if set(manifest_by_key) != C8_EXPECTED_KEYS:
            errors.append("c8 manifest branch inventory changed")
        for key in sorted(
            set(replay_by_key) & set(manifest_by_key),
            key=str,
        ):
            observed = replay_by_key[key]
            expected = manifest_by_key[key]
            pairs = (
                ("cnf", "cnf"),
                ("source_proof", "source_proof"),
                ("proof", "compacted_proof"),
                ("artifact_binding", "artifact_binding"),
                ("run_record", "run_record"),
                ("compaction_record", "compaction_record"),
            )
            for observed_field, expected_field in pairs:
                if observed.get(observed_field) != expected.get(expected_field):
                    errors.append(
                        f"c8 branch {key} {observed_field} binding mismatch"
                    )
            observed_solver = observed.get("solver")
            expected_solver = expected.get("solver")
            if (
                not isinstance(observed_solver, dict)
                or not isinstance(expected_solver, dict)
                or observed_solver.get("log_sha256")
                != expected_solver.get("log_sha256")
            ):
                errors.append(f"c8 branch {key} solver-log binding mismatch")
    return errors


def paper_errors(paths: EvidencePaths) -> list[str]:
    errors: list[str] = []
    record = load_json(paths.paper_record, "paper build record", errors)
    if record is None:
        return errors
    try:
        observed = build_record(
            paths.paper_source,
            paths.paper_pdf,
            paths.paper_log,
        )
    except (AssertionError, FileNotFoundError, UnicodeDecodeError) as error:
        errors.append(f"paper build evidence failed: {error}")
        return errors

    if record.get("schema_version") != 1:
        errors.append("paper build record schema changed")
    for section in ("source", "pdf", "latex_log"):
        recorded_section = record.get(section)
        observed_section = observed[section]
        if not isinstance(recorded_section, dict):
            errors.append(f"paper build record lacks {section}")
            continue
        for field in set(observed_section) - {"path"}:
            if recorded_section.get(field) != observed_section[field]:
                errors.append(f"paper build {section} {field} mismatch")
    return errors


def release_manifest_errors(paths: EvidencePaths) -> list[str]:
    if not paths.release_manifest.is_file():
        return [f"release manifest is missing: {paths.release_manifest}"]
    entries: dict[str, str] = {}
    errors: list[str] = []
    for line_number, line in enumerate(
        paths.release_manifest.read_text(encoding="ascii").splitlines(),
        start=1,
    ):
        match = MANIFEST_LINE_RE.fullmatch(line)
        if match is None:
            errors.append(f"invalid release manifest line {line_number}")
            continue
        digest, relative = match.groups()
        if relative in entries:
            errors.append(f"duplicate release manifest path: {relative}")
        entries[relative] = digest

    required = (
        paths.root / "README.md",
        paths.root / "CITATION.cff",
        paths.root / ".zenodo.json",
        paths.root / "PUBLICATION.md",
        paths.root / "research/release-gate.json",
        paths.c6_manifest,
        paths.c8_manifest,
        paths.paper_source,
        paths.root / "tools/replay_proofs.py",
        paths.root / "tools/replay_c8_proofs.py",
        paths.root / "tools/record_paper_build.py",
        paths.root / "tools/build_release_assets.py",
        paths.root / "tools/verify_release_gate.py",
    )
    for path in required:
        try:
            relative = path.relative_to(paths.root).as_posix()
        except ValueError:
            errors.append(f"required release path escapes repository: {path}")
            continue
        expected = entries.get(relative)
        if expected is None:
            errors.append(f"release manifest lacks required path: {relative}")
        elif not path.is_file() or file_sha256(path) != expected:
            errors.append(f"release manifest hash mismatch: {relative}")
    return errors


def release_asset_errors(paths: EvidencePaths) -> list[str]:
    errors: list[str] = []
    citation = paths.root / "CITATION.cff"
    if not citation.is_file():
        return [f"release metadata is missing: {citation}"]
    try:
        citation_text = citation.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return [f"release metadata is not UTF-8: {error}"]
    match = VERSION_RE.search(citation_text)
    if match is None:
        return ["CITATION.cff has no release version"]
    version = match.group(1).removeprefix("v")
    expected_names = {
        f"ramsey-number-5-5-paper-v{version}.pdf",
        f"ramsey-number-5-5-source-v{version}.tar.gz",
        "SHA256SUMS",
    }
    if not paths.release_dir.is_dir() or paths.release_dir.is_symlink():
        return [f"release asset directory is missing or unsafe: {paths.release_dir}"]
    observed_paths = list(paths.release_dir.iterdir())
    observed_names = {path.name for path in observed_paths}
    if observed_names != expected_names:
        errors.append("release asset set does not match the declared version")
    if any(not path.is_file() or path.is_symlink() for path in observed_paths):
        errors.append("release asset directory contains a non-file or symlink")

    checksum_path = paths.release_dir / "SHA256SUMS"
    checksums: dict[str, str] = {}
    if not checksum_path.is_file() or checksum_path.is_symlink():
        errors.append("release checksum manifest is missing or unsafe")
    else:
        for line_number, line in enumerate(
            checksum_path.read_text(encoding="ascii").splitlines(),
            start=1,
        ):
            checksum_match = CHECKSUM_LINE_RE.fullmatch(line)
            if checksum_match is None:
                errors.append(
                    f"invalid release checksum line {line_number}"
                )
                continue
            digest, name = checksum_match.groups()
            if name in checksums:
                errors.append(f"duplicate release checksum entry: {name}")
            checksums[name] = digest

    payload_names = expected_names - {"SHA256SUMS"}
    if set(checksums) != payload_names:
        errors.append("release checksums do not list the exact payload set")
    for name in sorted(payload_names & set(checksums)):
        path = paths.release_dir / name
        if not path.is_file() or path.is_symlink():
            errors.append(f"release payload is missing or unsafe: {name}")
        elif file_sha256(path) != checksums[name]:
            errors.append(f"release payload hash mismatch: {name}")

    paper_name = f"ramsey-number-5-5-paper-v{version}.pdf"
    release_paper = paths.release_dir / paper_name
    if (
        release_paper.is_file()
        and paths.paper_pdf.is_file()
        and file_sha256(release_paper) != file_sha256(paths.paper_pdf)
    ):
        errors.append("release paper does not match the inspected paper")
    return errors


def repository_clean_errors(root: Path) -> list[str]:
    if not (root / ".git").is_dir():
        return []
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip():
        return ["final release snapshot has tracked or untracked changes"]
    return []


def validation_errors(
    record: object,
    evidence: EvidencePaths | None = None,
    mode: str = "final",
) -> list[str]:
    if mode not in {"candidate", "final"}:
        raise ValueError(f"unexpected release-gate mode: {mode}")
    paths = evidence if evidence is not None else default_evidence_paths()
    errors = declaration_errors(record, mode)
    errors.extend(
        replay_manifest_errors(
            paths.c6_replay,
            paths.c6_manifest,
            "c6",
        )
    )
    errors.extend(
        replay_manifest_errors(
            paths.c8_replay,
            paths.c8_manifest,
            "c8",
        )
    )
    errors.extend(paper_errors(paths))
    if mode == "final":
        errors.extend(release_manifest_errors(paths))
        errors.extend(release_asset_errors(paths))
        errors.extend(repository_clean_errors(paths.root))
    return errors


def git_state(root: Path) -> tuple[str | None, bool | None]:
    if not (root / ".git").is_dir():
        return None, None
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return commit, bool(status.strip())


def evidence_record(
    gate: dict[str, object],
    paths: EvidencePaths,
    mode: str,
) -> dict[str, object]:
    commit, dirty = git_state(paths.root)
    record = {
        "schema_version": 1,
        "project": "ramsey-number-5-5",
        "mode": mode,
        "evaluated_at": gate.get("evaluated_at"),
        "result": "verified",
        "git_commit": commit,
        "working_tree_dirty": dirty,
        "evidence": {
            "c6_replay_sha256": file_sha256(paths.c6_replay),
            "c8_replay_sha256": file_sha256(paths.c8_replay),
            "c6_manifest_sha256": file_sha256(paths.c6_manifest),
            "c8_manifest_sha256": file_sha256(paths.c8_manifest),
            "paper_source_sha256": file_sha256(paths.paper_source),
            "paper_pdf_sha256": file_sha256(paths.paper_pdf),
            "paper_build_record_sha256": file_sha256(paths.paper_record),
        },
    }
    if mode == "final":
        record["evidence"]["release_assets"] = {
            path.name: file_sha256(path)
            for path in sorted(paths.release_dir.iterdir())
            if path.is_file() and not path.is_symlink()
        }
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", nargs="?", type=Path, default=DEFAULT_GATE)
    parser.add_argument(
        "--mode",
        choices=("candidate", "final"),
        default="final",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    paths = default_evidence_paths()
    errors: list[str] = []
    gate = load_json(args.gate, "release gate", errors)
    if gate is not None:
        errors.extend(validation_errors(gate, paths, args.mode))
    if errors:
        for error in errors:
            print("error: " + error)
        return 1

    if args.output is not None:
        record = evidence_record(gate, paths, args.mode)
        text = json.dumps(record, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="ascii", newline="\n") as handle:
            handle.write(text)
    print(f"release {args.mode} evidence verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
