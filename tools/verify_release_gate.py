#!/usr/bin/env python3
"""Verify release declarations against concrete proof and paper evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Mapping

from record_paper_build import build_record
from release_manifest import (
    EXCLUDED_NAMES as PACKAGE_EXCLUDED_NAMES,
    EXCLUDED_PARTS as PACKAGE_EXCLUDED_PARTS,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE = ROOT / "research" / "release-gate.json"
PROJECT = "ramsey-number-5-5"
EXPECTED_CHECKER_SOURCE_COMMIT = (
    "2e3b2dc0ecf938addbd779d42877b6ed69d9a985"
)
EXPECTED_CANDIDATE_CLAIM = (
    "As of 2026-09-08, fourteen cycle types marked pending, uncovered, or "
    "unfinished in audited public case lists and coverage ledgers are "
    "excluded for hypothetical Ramsey (5,5,43) graphs."
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
    "hosted_candidate_ci_passes",
}
CANDIDATE_REQUIRED_GATES = GATE_NAMES - {
    "final_release_snapshot_audit_passes",
    "paper_build_and_inspection_passes",
    "independent_package_review_passes",
    "hosted_candidate_ci_passes",
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
FINAL_RELEASE_REPOSITORY = "ruturajr-raval/ramsey-number-5-5"
FINAL_RELEASE_RULESET_ID = 22507956
HOSTED_CANDIDATE_KEYS = {
    "repository",
    "workflow",
    "run_id",
    "head_sha",
    "head_branch",
    "event",
    "conclusion",
    "url",
}
TAG_PROTECTION_KEYS = {
    "repository",
    "ruleset_id",
    "name",
    "target",
    "enforcement",
    "include",
    "bypass_actor_count",
    "rules",
}


@dataclass(frozen=True)
class EvidencePaths:
    root: Path
    c6_replay: Path
    c8_replay: Path
    retained_c6_replay: Path
    retained_c8_replay: Path
    c6_manifest: Path
    c8_manifest: Path
    paper_source: Path
    paper_pdf: Path
    paper_log: Path
    paper_record: Path
    release_pdf: Path
    release_log: Path
    release_pdf_record: Path
    release_manifest: Path
    release_dir: Path


@dataclass(frozen=True)
class ReferenceEntry:
    sha256: str
    mode: int


def default_evidence_paths(root: Path = ROOT) -> EvidencePaths:
    return EvidencePaths(
        root=root,
        c6_replay=root / "build/proof-replay-c6/fresh-proof-replay.json",
        c8_replay=root / "build/proof-replay-c8/fresh-proof-replay.json",
        retained_c6_replay=root / "evidence/replay-c6/fresh-proof-replay.json",
        retained_c8_replay=root / "evidence/replay-c8/fresh-proof-replay.json",
        c6_manifest=root / "evidence/orbit-p3-c6/certificate-manifest.json",
        c8_manifest=root / "evidence/orbit-p3-c8/certificate-manifest.json",
        paper_source=root / "paper/main.tex",
        paper_pdf=root / "build/paper/main.pdf",
        paper_log=root / "build/paper/main.log",
        paper_record=root / "build/paper/paper-build.json",
        release_pdf=root / "paper/ramsey-number-5-5-paper-v0.1.0.pdf",
        release_log=root / "paper/ramsey-number-5-5-paper-v0.1.0.log",
        release_pdf_record=root / "paper/release-pdf.json",
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


def bind_release_artifact(
    path: Path,
    digest: str,
    label: str,
    root: Path | None,
    release_entries: dict[str, str] | None,
    errors: list[str],
) -> None:
    if root is None or release_entries is None:
        return
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        errors.append(f"{label} escapes the release root")
        return
    if release_entries.get(relative) != digest:
        errors.append(f"{label} is not bound by the release manifest")


def checked_replay_artifact(
    replay_path: Path,
    name: object,
    digest: object,
    label: str,
    errors: list[str],
    root: Path | None = None,
    release_entries: dict[str, str] | None = None,
) -> Path | None:
    if (
        not isinstance(name, str)
        or not name
        or Path(name).name != name
        or name in {".", ".."}
    ):
        errors.append(f"{label} path is unsafe")
        return None
    if not valid_sha256(digest):
        errors.append(f"{label} hash is invalid")
        return None
    path = replay_path.parent / name
    try:
        confined = path.resolve().parent == replay_path.parent.resolve()
    except OSError:
        confined = False
    if not confined or path.is_symlink() or not path.is_file():
        errors.append(f"{label} is missing or unsafe")
        return None
    observed = file_sha256(path)
    if observed != digest:
        errors.append(f"{label} hash mismatch")
        return None
    bind_release_artifact(
        path,
        observed,
        label,
        root,
        release_entries,
        errors,
    )
    return path


def hosted_candidate_declaration_errors(
    record: dict[str, object],
    required: bool,
) -> list[str]:
    candidate = record.get("hosted_candidate_ci")
    if candidate is None and not required:
        return []
    if not isinstance(candidate, dict):
        return ["hosted candidate CI record is missing"]

    errors: list[str] = []
    keys = set(candidate)
    if keys != HOSTED_CANDIDATE_KEYS:
        errors.append("hosted candidate CI record has unexpected fields")
    if candidate.get("repository") != FINAL_RELEASE_REPOSITORY:
        errors.append("hosted candidate CI repository is unexpected")
    if candidate.get("workflow") != "ci":
        errors.append("hosted candidate CI workflow is unexpected")
    run_id = candidate.get("run_id")
    if not isinstance(run_id, int) or run_id <= 0:
        errors.append("hosted candidate CI run ID is invalid")
    head_sha = candidate.get("head_sha")
    if not isinstance(head_sha, str) or not re.fullmatch(
        r"[0-9a-f]{40}",
        head_sha,
    ):
        errors.append("hosted candidate CI SHA is invalid")
    if candidate.get("head_branch") != "main":
        errors.append("hosted candidate CI branch is unexpected")
    if candidate.get("event") != "push":
        errors.append("hosted candidate CI event is unexpected")
    if candidate.get("conclusion") != "success":
        errors.append("hosted candidate CI did not pass")
    expected_url = (
        f"https://github.com/{FINAL_RELEASE_REPOSITORY}/actions/runs/"
        f"{run_id}"
    )
    if candidate.get("url") != expected_url:
        errors.append("hosted candidate CI URL is inconsistent")
    return errors


def tag_protection_declaration_errors(
    record: dict[str, object],
    required: bool,
) -> list[str]:
    protection = record.get("tag_protection")
    if protection is None and not required:
        return []
    if not isinstance(protection, dict):
        return ["tag protection record is missing"]

    errors: list[str] = []
    keys = set(protection)
    if keys != TAG_PROTECTION_KEYS:
        errors.append("tag protection record has unexpected fields")
    expected = {
        "repository": FINAL_RELEASE_REPOSITORY,
        "ruleset_id": FINAL_RELEASE_RULESET_ID,
        "name": "Protect version tags",
        "target": "tag",
        "enforcement": "active",
        "include": ["refs/tags/v*"],
        "bypass_actor_count": 0,
        "rules": ["deletion", "update"],
    }
    for key, value in expected.items():
        if protection.get(key) != value:
            errors.append(f"tag protection {key} is unexpected")
    return errors


def declaration_errors(record: object, mode: str) -> list[str]:
    if not isinstance(record, dict):
        return ["release gate must be a JSON object"]

    errors: list[str] = []
    if record.get("schema_version") != 3:
        errors.append("release-gate schema version must be 3")
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
    errors.extend(
        hosted_candidate_declaration_errors(
            record,
            required=mode == "final",
        )
    )
    errors.extend(
        tag_protection_declaration_errors(
            record,
            required=mode == "final",
        )
    )
    return errors


def replay_manifest_errors(
    replay_path: Path,
    manifest_path: Path,
    family: str,
    root: Path | None = None,
    release_entries: dict[str, str] | None = None,
) -> list[str]:
    errors: list[str] = []
    replay = load_json(replay_path, f"{family} replay", errors)
    manifest = load_json(manifest_path, f"{family} manifest", errors)
    if replay is None or manifest is None:
        return errors
    if replay_path.is_symlink():
        errors.append(f"{family} replay record is unsafe")
    else:
        bind_release_artifact(
            replay_path,
            file_sha256(replay_path),
            f"{family} replay record",
            root,
            release_entries,
            errors,
        )

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
        checked_replay_artifact(
            replay_path,
            checker_build.get("log"),
            checker_build.get("log_sha256"),
            f"{family} checker build log",
            errors,
            root,
            release_entries,
        )

    checked_replay_artifact(
        replay_path,
        replay.get("checker"),
        replay.get("checker_sha256"),
        f"{family} checker binary",
        errors,
        root,
        release_entries,
    )

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

    for index, branch in enumerate(replay_branches):
        if not isinstance(branch, dict):
            errors.append(f"{family} replay branch {index} is invalid")
            continue
        branch_checker = branch.get("checker")
        if not isinstance(branch_checker, dict):
            errors.append(f"{family} replay branch {index} lacks a checker record")
            continue
        if branch_checker.get("result") != "VERIFIED":
            errors.append(f"{family} replay branch {index} is not verified")
        if branch_checker.get("exit_code") != 0:
            errors.append(
                f"{family} replay branch {index} checker exit code changed"
            )
        checked_replay_artifact(
            replay_path,
            branch_checker.get("log"),
            branch_checker.get("log_sha256"),
            f"{family} replay branch {index} checker log",
            errors,
            root,
            release_entries,
        )

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
    release_record = load_json(
        paths.release_pdf_record,
        "release PDF record",
        errors,
    )
    if record is None or release_record is None:
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

    if release_record.get("schema_version") != 1:
        errors.append("release PDF record schema changed")
    release_source = release_record.get("source")
    release_pdf = release_record.get("pdf")
    release_build = release_record.get("build")
    inspection = release_record.get("inspection")
    expected_pdf_path = paths.release_pdf.relative_to(paths.root).as_posix()
    if not isinstance(release_source, dict):
        errors.append("release PDF record lacks source binding")
    else:
        if release_source.get("path") != "paper/main.tex":
            errors.append("release PDF source path changed")
        if release_source.get("sha256") != file_sha256(paths.paper_source):
            errors.append("release PDF source hash mismatch")
    if not paths.release_pdf.is_file() or paths.release_pdf.is_symlink():
        errors.append("committed release PDF is missing or unsafe")
    elif paths.release_pdf.read_bytes()[:5] != b"%PDF-":
        errors.append("committed release PDF is not a PDF")
    if not isinstance(release_pdf, dict):
        errors.append("release PDF record lacks PDF binding")
    elif paths.release_pdf.is_file():
        release_pdf_sha256 = file_sha256(paths.release_pdf)
        for field, expected in (
            ("path", expected_pdf_path),
            ("bytes", paths.release_pdf.stat().st_size),
            ("sha256", release_pdf_sha256),
            ("pages", observed["pdf"]["pages"]),
        ):
            if release_pdf.get(field) != expected:
                errors.append(f"release PDF {field} mismatch")
        if observed["pdf"]["sha256"] != release_pdf_sha256:
            errors.append("rebuilt paper does not match committed release PDF")
    if (
        not isinstance(inspection, dict)
        or inspection.get("result") != "pass"
        or not isinstance(release_pdf, dict)
        or inspection.get("pages_inspected") != release_pdf.get("pages")
    ):
        errors.append("release PDF inspection record is incomplete")
    expected_log_path = paths.release_log.relative_to(paths.root).as_posix()
    if not isinstance(release_build, dict):
        errors.append("release PDF record lacks build provenance")
    else:
        if release_build.get("engine") != "Tectonic 0.17.0":
            errors.append("release PDF engine changed")
        if release_build.get("source_date_epoch") != 1788739200:
            errors.append("release PDF source-date epoch changed")
        if not isinstance(release_build.get("inspected_platform"), str):
            errors.append("release PDF platform record is invalid")
        for field in (
            "inspected_engine_archive_sha256",
            "inspected_engine_sha256",
        ):
            if not valid_sha256(release_build.get(field)):
                errors.append(f"release PDF {field} is invalid")
        if release_build.get("latex_log_path") != expected_log_path:
            errors.append("release PDF log path changed")
        if not valid_sha256(release_build.get("latex_log_sha256")):
            errors.append("release PDF log hash is invalid")
        elif (
            not paths.release_log.is_file()
            or paths.release_log.is_symlink()
            or file_sha256(paths.release_log)
            != release_build.get("latex_log_sha256")
        ):
            errors.append("release PDF log hash mismatch")
    return errors


def read_manifest_entries(
    path: Path,
    errors: list[str],
) -> dict[str, str]:
    entries: dict[str, str] = {}
    if not path.is_file() or path.is_symlink():
        errors.append(f"release manifest is missing or unsafe: {path}")
        return entries
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        errors.append(f"release manifest cannot be read: {error}")
        return entries
    for line_number, line in enumerate(lines, start=1):
        match = MANIFEST_LINE_RE.fullmatch(line)
        if match is None:
            errors.append(f"invalid release manifest line {line_number}")
            continue
        digest, relative = match.groups()
        if relative in entries:
            errors.append(f"duplicate release manifest path: {relative}")
        entries[relative] = digest
    return entries


def resolve_commit(
    root: Path,
    reference: str,
    label: str,
    errors: list[str],
) -> str | None:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--verify", f"{reference}^{{commit}}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        errors.append(f"{label} does not resolve")
        return None
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append(f"{label} resolved to an invalid commit")
        return None
    return commit


def git_reference_entries(
    root: Path,
    reference: str,
    errors: list[str],
) -> dict[str, ReferenceEntry]:
    commit = resolve_commit(root, reference, "release reference", errors)
    if commit is None:
        return {}
    try:
        tree = subprocess.run(
            ["git", "ls-tree", "-r", "-z", commit],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        errors.append("release reference tree cannot be read")
        return {}

    entries: dict[str, ReferenceEntry] = {}
    for record in tree.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode_text, object_type, object_id = (
                metadata.decode("ascii").split()
            )
            relative = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            errors.append("release reference contains an invalid tree entry")
            continue
        path = Path(relative)
        if (
            object_type != "blob"
            or mode_text not in {"100644", "100755"}
            or path.is_absolute()
            or ".." in path.parts
            or relative in entries
        ):
            errors.append(
                f"release reference contains an unsafe tree entry: {relative}"
            )
            continue
        try:
            data = subprocess.run(
                ["git", "cat-file", "blob", object_id],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            errors.append(f"release reference blob cannot be read: {relative}")
            continue
        entries[relative] = ReferenceEntry(
            hashlib.sha256(data).hexdigest(),
            0o755 if mode_text == "100755" else 0o644,
        )
    return entries


def packaged_reference_entries(
    entries: dict[str, ReferenceEntry],
) -> dict[str, ReferenceEntry]:
    return {
        relative: entry
        for relative, entry in entries.items()
        if not any(
            part in PACKAGE_EXCLUDED_PARTS
            for part in Path(relative).parts
        )
        and Path(relative).name not in PACKAGE_EXCLUDED_NAMES
    }


def reference_snapshot_errors(
    paths: EvidencePaths,
    reference: str,
    version: str,
) -> list[str]:
    errors: list[str] = []
    reference_entries = git_reference_entries(
        paths.root,
        reference,
        errors,
    )
    if not reference_entries:
        return errors
    manifest_errors: list[str] = []
    manifest_entries = read_manifest_entries(
        paths.release_manifest,
        manifest_errors,
    )
    errors.extend(manifest_errors)
    expected_manifest = packaged_reference_entries(reference_entries)
    expected_digests = {
        relative: entry.sha256
        for relative, entry in expected_manifest.items()
    }
    if manifest_entries != expected_digests:
        missing = sorted(set(expected_digests) - set(manifest_entries))
        stale = sorted(set(manifest_entries) - set(expected_digests))
        changed = sorted(
            relative
            for relative in set(manifest_entries) & set(expected_digests)
            if manifest_entries[relative] != expected_digests[relative]
        )
        if missing:
            errors.append(
                "release manifest omits Git-reference paths: "
                + ", ".join(missing)
            )
        if stale:
            errors.append(
                "release manifest has non-reference paths: "
                + ", ".join(stale)
            )
        if changed:
            errors.append(
                "release manifest differs from Git-reference content: "
                + ", ".join(changed)
            )

    archive_path = (
        paths.release_dir / f"{PROJECT}-source-v{version}.tar.gz"
    )
    errors.extend(
        archive_entry_errors(
            archive_path,
            f"{PROJECT}-v{version}/",
            reference_entries,
            "release source archive versus Git reference",
        )
    )
    return errors


def release_manifest_errors(paths: EvidencePaths) -> list[str]:
    errors: list[str] = []
    entries = read_manifest_entries(paths.release_manifest, errors)
    if not entries:
        return errors

    for relative, expected in sorted(entries.items()):
        path = paths.root / relative
        try:
            path.resolve().relative_to(paths.root.resolve())
        except ValueError:
            errors.append(f"release manifest path escapes repository: {relative}")
            continue
        if not path.is_file() or path.is_symlink():
            errors.append(f"release manifest path is missing or unsafe: {relative}")
        elif file_sha256(path) != expected:
            errors.append(f"release manifest hash mismatch: {relative}")

    required = (
        paths.root / "README.md",
        paths.root / "CITATION.cff",
        paths.root / ".zenodo.json",
        paths.root / "PUBLICATION.md",
        paths.root / "THIRD_PARTY_NOTICES.md",
        paths.root / "third_party/drat-trim/LICENSE",
        paths.root / "research/release-gate.json",
        paths.c6_manifest,
        paths.c8_manifest,
        paths.retained_c6_replay,
        paths.retained_c8_replay,
        paths.paper_source,
        paths.release_pdf,
        paths.release_log,
        paths.release_pdf_record,
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
    return errors


def stream_sha256(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            break
        digest.update(block)
    return digest.hexdigest()


def archive_entry_errors(
    archive_path: Path,
    prefix: str,
    expected: dict[str, ReferenceEntry],
    label: str,
) -> list[str]:
    errors: list[str] = []
    if not archive_path.is_file() or archive_path.is_symlink():
        return [f"{label} is missing or unsafe"]
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                errors.append(f"{label} has duplicate members")
            observed: dict[str, tarfile.TarInfo] = {}
            for member in members:
                path = Path(member.name)
                if (
                    not member.isfile()
                    or not member.name.startswith(prefix)
                    or path.is_absolute()
                    or ".." in path.parts
                    or bool(member.pax_headers)
                    or getattr(member, "sparse", None) is not None
                    or member.uid != 0
                    or member.gid != 0
                    or member.mtime != 0
                    or member.uname != "root"
                    or member.gname != "root"
                    or member.mode not in {0o644, 0o755}
                ):
                    errors.append(f"{label} contains an unsafe member")
                    continue
                relative = member.name[len(prefix) :]
                observed[relative] = member
            if set(observed) != set(expected):
                errors.append(f"{label} does not match the expected file set")
            for relative in sorted(set(observed) & set(expected)):
                member = observed[relative]
                entry = expected[relative]
                if member.mode != entry.mode:
                    errors.append(f"{label} mode mismatch: {relative}")
                stream = archive.extractfile(member)
                if stream is None or stream_sha256(stream) != entry.sha256:
                    errors.append(f"{label} hash mismatch: {relative}")
    except (OSError, tarfile.TarError) as error:
        errors.append(f"{label} is invalid: {error}")
    return errors


def source_archive_errors(
    paths: EvidencePaths,
    version: str,
    manifest_entries: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    archive_path = (
        paths.release_dir / f"{PROJECT}-source-v{version}.tar.gz"
    )
    expected: dict[str, ReferenceEntry] = {}
    for relative, digest in manifest_entries.items():
        path = paths.root / relative
        if not path.is_file() or path.is_symlink():
            errors.append(
                f"release source input is missing or unsafe: {relative}"
            )
            continue
        mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
        expected[relative] = ReferenceEntry(digest, mode)
    if (
        not paths.release_manifest.is_file()
        or paths.release_manifest.is_symlink()
    ):
        return errors + ["release manifest is missing or unsafe"]
    manifest_mode = (
        0o755 if paths.release_manifest.stat().st_mode & 0o111 else 0o644
    )
    expected[paths.release_manifest.name] = ReferenceEntry(
        file_sha256(paths.release_manifest),
        manifest_mode,
    )
    prefix = f"{PROJECT}-v{version}/"
    errors.extend(
        archive_entry_errors(
            archive_path,
            prefix,
            expected,
            "release source archive",
        )
    )
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
    manifest_errors: list[str] = []
    manifest_entries = read_manifest_entries(
        paths.release_manifest,
        manifest_errors,
    )
    errors.extend(manifest_errors)
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
        and paths.release_pdf.is_file()
        and file_sha256(release_paper) != file_sha256(paths.release_pdf)
    ):
        errors.append("release paper does not match the committed paper")
    committed_pdf_relative = paths.release_pdf.relative_to(
        paths.root
    ).as_posix()
    if (
        paths.release_pdf.is_file()
        and manifest_entries.get(committed_pdf_relative)
        != file_sha256(paths.release_pdf)
    ):
        errors.append("release manifest does not bind the committed paper")
    if manifest_entries:
        errors.extend(
            source_archive_errors(
                paths,
                version,
                manifest_entries,
            )
        )
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
        return ["release snapshot has tracked or untracked changes"]
    return []


def release_identity_errors(
    root: Path,
    reference: str,
    tag: str | None,
    version: str,
    mode: str,
) -> list[str]:
    if not (root / ".git").is_dir():
        return ["release identity requires a Git checkout"]
    errors: list[str] = []
    commit = resolve_commit(root, reference, "release reference", errors)
    head_commit = resolve_commit(root, "HEAD", "checked-out HEAD", errors)
    if commit is None or head_commit is None:
        return errors
    if head_commit != commit:
        errors.append(
            f"checked-out HEAD resolves to {head_commit}, expected {commit}"
        )
    if mode != "final" and tag is None:
        return errors
    if tag is None:
        errors.append("final release verification requires --tag")
        return errors
    if tag != f"v{version}":
        errors.append(
            f"release tag {tag!r} does not match version {version}"
        )
    try:
        tag_type = subprocess.run(
            ["git", "cat-file", "-t", f"refs/tags/{tag}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        tag_type = None
    if tag_type is not None and tag_type != "tag":
        errors.append("release tag must be an annotated tag object")
    tag_commit = resolve_commit(
        root,
        f"refs/tags/{tag}",
        "release tag",
        errors,
    )
    if tag_commit is not None and commit != tag_commit:
        errors.append(
            f"release tag {tag} resolves to {tag_commit}, expected {commit}"
        )
    return errors


def hosted_candidate_commit_errors(
    record: dict[str, object],
    root: Path,
    reference: str,
    mode: str,
) -> list[str]:
    if mode != "final":
        return []
    candidate = record.get("hosted_candidate_ci")
    if not isinstance(candidate, dict):
        return ["hosted candidate CI record is missing"]
    head_sha = candidate.get("head_sha")
    if not isinstance(head_sha, str) or not re.fullmatch(
        r"[0-9a-f]{40}",
        head_sha,
    ):
        return ["hosted candidate CI SHA is invalid"]

    errors: list[str] = []
    release_commit = resolve_commit(
        root,
        reference,
        "release reference",
        errors,
    )
    candidate_commit = resolve_commit(
        root,
        head_sha,
        "hosted candidate CI SHA",
        errors,
    )
    if release_commit is None or candidate_commit is None:
        return errors
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", candidate_commit, release_commit],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        errors.append(
            "hosted candidate CI SHA is not an ancestor of the release"
        )
    return errors


def hosted_environment_errors(
    root: Path,
    reference: str,
    tag: str | None,
    environment: Mapping[str, str] | None = None,
) -> list[str]:
    values = os.environ if environment is None else environment
    errors: list[str] = []
    if values.get("GITHUB_ACTIONS") != "true":
        return ["final release verification requires GitHub Actions"]
    if values.get("GITHUB_REPOSITORY") != FINAL_RELEASE_REPOSITORY:
        errors.append("hosted release repository is unexpected")
    commit = resolve_commit(root, reference, "release reference", errors)
    if commit is not None and values.get("GITHUB_SHA") != commit:
        errors.append("hosted release SHA does not match the release reference")
    if values.get("GITHUB_REF_TYPE") != "tag":
        errors.append("hosted release ref is not a tag")
    if tag is None or values.get("GITHUB_REF_NAME") != tag:
        errors.append("hosted release tag does not match --tag")
    run_id = values.get("GITHUB_RUN_ID", "")
    if not run_id.isdigit() or int(run_id) <= 0:
        errors.append("hosted release run ID is invalid")
    return errors


def validation_errors(
    record: object,
    evidence: EvidencePaths | None = None,
    mode: str = "final",
) -> list[str]:
    if mode not in {"candidate", "final"}:
        raise ValueError(f"unexpected release-gate mode: {mode}")
    paths = evidence if evidence is not None else default_evidence_paths()
    errors = declaration_errors(record, mode)
    manifest_binding_errors: list[str] = []
    parsed_release_entries = read_manifest_entries(
        paths.release_manifest,
        manifest_binding_errors,
    )
    release_entries = (
        None if manifest_binding_errors else parsed_release_entries
    )
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
    errors.extend(
        replay_manifest_errors(
            paths.retained_c6_replay,
            paths.c6_manifest,
            "c6",
            paths.root,
            release_entries,
        )
    )
    errors.extend(
        replay_manifest_errors(
            paths.retained_c8_replay,
            paths.c8_manifest,
            "c8",
            paths.root,
            release_entries,
        )
    )
    errors.extend(paper_errors(paths))
    errors.extend(release_manifest_errors(paths))
    errors.extend(repository_clean_errors(paths.root))
    if mode == "final":
        errors.extend(release_asset_errors(paths))
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
    reference: str,
    tag: str | None,
) -> dict[str, object]:
    commit, dirty = git_state(paths.root)
    record = {
        "schema_version": 1,
        "project": "ramsey-number-5-5",
        "mode": mode,
        "release_reference": reference,
        "release_tag": tag,
        "evaluated_at": gate.get("evaluated_at"),
        "result": "verified",
        "git_commit": commit,
        "working_tree_dirty": dirty,
        "evidence": {
            "c6_replay_sha256": file_sha256(paths.c6_replay),
            "c8_replay_sha256": file_sha256(paths.c8_replay),
            "retained_c6_replay_sha256": file_sha256(
                paths.retained_c6_replay
            ),
            "retained_c8_replay_sha256": file_sha256(
                paths.retained_c8_replay
            ),
            "c6_manifest_sha256": file_sha256(paths.c6_manifest),
            "c8_manifest_sha256": file_sha256(paths.c8_manifest),
            "paper_source_sha256": file_sha256(paths.paper_source),
            "paper_pdf_sha256": file_sha256(paths.paper_pdf),
            "paper_build_record_sha256": file_sha256(paths.paper_record),
            "release_manifest_sha256": file_sha256(paths.release_manifest),
            "committed_paper_sha256": file_sha256(paths.release_pdf),
            "committed_paper_log_sha256": file_sha256(paths.release_log),
            "committed_paper_record_sha256": file_sha256(
                paths.release_pdf_record
            ),
        },
    }
    if mode == "final":
        record["evidence"]["release_assets"] = {
            path.name: file_sha256(path)
            for path in sorted(paths.release_dir.iterdir())
            if path.is_file() and not path.is_symlink()
        }
        record["hosted_verification"] = {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "sha": os.environ.get("GITHUB_SHA"),
            "ref_name": os.environ.get("GITHUB_REF_NAME"),
            "ref_type": os.environ.get("GITHUB_REF_TYPE"),
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
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="Git commit or ref used for release identity",
    )
    parser.add_argument("--tag", help="release tag required in final mode")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    paths = default_evidence_paths()
    errors: list[str] = []
    gate = load_json(args.gate, "release gate", errors)
    if gate is not None:
        errors.extend(validation_errors(gate, paths, args.mode))
        errors.extend(
            hosted_candidate_commit_errors(
                gate,
                paths.root,
                args.ref,
                args.mode,
            )
        )
    citation = paths.root / "CITATION.cff"
    if not citation.is_file():
        errors.append("CITATION.cff is missing")
    else:
        version_match = VERSION_RE.search(
            citation.read_text(encoding="utf-8")
        )
        if version_match is None:
            errors.append("CITATION.cff has no release version")
        else:
            version = version_match.group(1).removeprefix("v")
            errors.extend(
                release_identity_errors(
                    paths.root,
                    args.ref,
                    args.tag,
                    version,
                    args.mode,
                )
            )
            if args.mode == "final":
                errors.extend(
                    reference_snapshot_errors(
                        paths,
                        args.ref,
                        version,
                    )
                )
                errors.extend(
                    hosted_environment_errors(
                        paths.root,
                        args.ref,
                        args.tag,
                    )
                )
    if errors:
        for error in errors:
            print("error: " + error)
        return 1

    if args.output is not None:
        record = evidence_record(
            gate,
            paths,
            args.mode,
            args.ref,
            args.tag,
        )
        text = json.dumps(record, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="ascii", newline="\n") as handle:
            handle.write(text)
    print(f"release {args.mode} evidence verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
