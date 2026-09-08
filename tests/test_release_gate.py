from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from record_paper_build import build_record
from verify_release_gate import (
    C6_CLAIM,
    C8_CLAIM,
    EXPECTED_CANDIDATE_CLAIM,
    EXPECTED_CHECKER_SOURCE_COMMIT,
    GATE_NAMES,
    EvidencePaths,
    ReferenceEntry,
    archive_entry_errors,
    file_sha256,
    hosted_candidate_commit_errors,
    hosted_environment_errors,
    release_identity_errors,
    reference_snapshot_errors,
    repository_clean_errors,
    validation_errors,
)


ROOT = Path(__file__).resolve().parents[1]


def complete_gate() -> dict[str, object]:
    return {
        "schema_version": 3,
        "project": "ramsey-number-5-5",
        "evaluated_at": "2026-09-08",
        "candidate_claim": EXPECTED_CANDIDATE_CLAIM,
        "gates": {name: True for name in GATE_NAMES},
        "hosted_candidate_ci": {
            "repository": "ruturajr-raval/ramsey-number-5-5",
            "workflow": "ci",
            "run_id": 12345,
            "head_sha": "1" * 40,
            "head_branch": "main",
            "event": "push",
            "conclusion": "success",
            "url": (
                "https://github.com/ruturajr-raval/"
                "ramsey-number-5-5/actions/runs/12345"
            ),
        },
        "tag_protection": {
            "repository": "ruturajr-raval/ramsey-number-5-5",
            "ruleset_id": 22507956,
            "name": "Protect version tags",
            "target": "tag",
            "enforcement": "active",
            "include": ["refs/tags/v*"],
            "bypass_actor_count": 0,
            "rules": ["deletion", "update"],
        },
        "decision": "release",
        "artifact_reproducibility_ready": True,
        "theorem_announcement_ready": True,
        "reason": "Complete fixture.",
    }


class ReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=build,
            prefix="release-gate-test-",
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.paths = EvidencePaths(
            root=self.root,
            c6_replay=self.root / "build/c6/fresh-proof-replay.json",
            c8_replay=self.root / "build/c8/fresh-proof-replay.json",
            retained_c6_replay=(
                self.root / "evidence/replay-c6/fresh-proof-replay.json"
            ),
            retained_c8_replay=(
                self.root / "evidence/replay-c8/fresh-proof-replay.json"
            ),
            c6_manifest=self.root / "evidence/c6/certificate-manifest.json",
            c8_manifest=self.root / "evidence/c8/certificate-manifest.json",
            paper_source=self.root / "paper/main.tex",
            paper_pdf=self.root / "build/paper/main.pdf",
            paper_log=self.root / "build/paper/main.log",
            paper_record=self.root / "build/paper/paper-build.json",
            release_pdf=(
                self.root / "paper/ramsey-number-5-5-paper-v0.1.0.pdf"
            ),
            release_log=(
                self.root / "paper/ramsey-number-5-5-paper-v0.1.0.log"
            ),
            release_pdf_record=self.root / "paper/release-pdf.json",
            release_manifest=self.root / "release-manifest.sha256",
            release_dir=self.root / "dist/release",
        )
        self.make_evidence()

    @staticmethod
    def write_json(path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )

    @staticmethod
    def artifact(label: str) -> dict[str, object]:
        digest = hashlib.sha256(label.encode("ascii")).hexdigest()
        return {
            "path": label,
            "bytes": len(label),
            "sha256": digest,
        }

    def checker_record(self, directory: Path) -> dict[str, object]:
        directory.mkdir(parents=True, exist_ok=True)
        checker = directory / "drat-trim-fresh"
        checker.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        checker.chmod(0o755)
        build_log = directory / "drat-trim-fresh-build.log"
        build_log.write_text("compiler_exit_code=0\n", encoding="ascii")
        return {
            "checker": checker.name,
            "checker_sha256": file_sha256(checker),
            "checker_source_commit": EXPECTED_CHECKER_SOURCE_COMMIT,
            "checker_build": {
                "mode": "fresh-source-build",
                "source_sha256": "1" * 64,
                "log": build_log.name,
                "log_sha256": file_sha256(build_log),
            },
        }

    def branch_checker(
        self,
        directory: Path,
        label: str,
    ) -> dict[str, object]:
        log = directory / f"{label}-fresh-drat-trim.log"
        log.write_text("s VERIFIED\n", encoding="ascii")
        return {
            "result": "VERIFIED",
            "exit_code": 0,
            "wall_seconds": 0.1,
            "log": log.name,
            "log_sha256": file_sha256(log),
        }

    def make_c6_evidence(self) -> None:
        replay_directory = self.paths.c6_replay.parent
        replay_directory.mkdir(parents=True, exist_ok=True)
        branches = []
        for branch in range(4):
            branches.append(
                {
                    "branch": branch,
                    "cnf": self.artifact(f"p3-c6-k{branch}.cnf"),
                    "proof": self.artifact(f"p3-c6-k{branch}.drat.xz"),
                    "checker": self.branch_checker(
                        replay_directory,
                        f"p3-c6-k{branch}",
                    ),
                }
            )
        manifest = {
            "claim": C6_CLAIM,
            "branches": branches,
            "verification_passed": True,
        }
        self.write_json(self.paths.c6_manifest, manifest)
        replay = {
            "claim": C6_CLAIM,
            "scope": "complete retained certificate replay",
            "expected_branch_count": 4,
            "verified_branch_count": 4,
            "selected_branches_verified": True,
            "all_expected_branches_verified": True,
            "release_grade_replay": True,
            "branches": branches,
            "certificate_manifest": {
                "path": self.paths.c6_manifest.name,
                "sha256": file_sha256(self.paths.c6_manifest),
            },
            **self.checker_record(self.paths.c6_replay.parent),
        }
        self.write_json(self.paths.c6_replay, replay)

    def make_c8_evidence(self) -> None:
        replay_directory = self.paths.c8_replay.parent
        replay_directory.mkdir(parents=True, exist_ok=True)
        keys = (
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
        )
        manifest_branches = []
        replay_branches = []
        for index, key in enumerate(keys):
            branch = list(key[:3])
            matrix_type = key[3]
            cnf = self.artifact(f"c8-{index}.cnf")
            source_proof = self.artifact(f"c8-{index}-source.drat.xz")
            proof = self.artifact(f"c8-{index}.drat.xz")
            artifact_binding = {"mode": "test"}
            run_record = self.artifact(f"c8-{index}-run.json")
            compaction_record = self.artifact(
                f"c8-{index}-compaction.json"
            )
            solver = {"log_sha256": f"{index:064x}"}
            expected = {
                "branch": branch,
                "cnf": cnf,
                "source_proof": source_proof,
                "compacted_proof": proof,
                "artifact_binding": artifact_binding,
                "run_record": run_record,
                "compaction_record": compaction_record,
                "solver": solver,
            }
            observed = {
                "branch": branch,
                "cnf": cnf,
                "source_proof": source_proof,
                "proof": proof,
                "artifact_binding": artifact_binding,
                "run_record": run_record,
                "compaction_record": compaction_record,
                "solver": solver,
                "checker": self.branch_checker(
                    replay_directory,
                    f"c8-{index}",
                ),
            }
            if matrix_type is not None:
                expected["matrix_type"] = matrix_type
                observed["matrix_type"] = matrix_type
            manifest_branches.append(expected)
            replay_branches.append(observed)

        manifest = {
            "claim": C8_CLAIM,
            "certificate_family": {
                "canonical_branches": 6,
                "strengthened_t4_branches": 4,
                "total_branches": 10,
            },
            "branches": manifest_branches,
            "verification_passed": True,
        }
        self.write_json(self.paths.c8_manifest, manifest)
        replay = {
            "claim": C8_CLAIM,
            "scope": "complete retained certificate replay",
            "expected_branch_count": 10,
            "verified_branch_count": 10,
            "selected_branches_verified": True,
            "all_expected_branches_verified": True,
            "release_grade_replay": True,
            "branches": replay_branches,
            "certificate_manifest": {
                "path": self.paths.c8_manifest.name,
                "sha256": file_sha256(self.paths.c8_manifest),
            },
            **self.checker_record(self.paths.c8_replay.parent),
        }
        self.write_json(self.paths.c8_replay, replay)

    def make_paper_evidence(self) -> None:
        self.paths.paper_source.parent.mkdir(parents=True, exist_ok=True)
        self.paths.paper_source.write_text(
            "\\documentclass{article}\n",
            encoding="ascii",
        )
        self.paths.paper_pdf.parent.mkdir(parents=True, exist_ok=True)
        self.paths.paper_pdf.write_bytes(
            b"%PDF-1.4\n" + b"release gate fixture\n" * 10
        )
        self.paths.paper_log.write_text(
            "Output written on main.pdf (9 pages, {} bytes).\n".format(
                self.paths.paper_pdf.stat().st_size
            ),
            encoding="ascii",
        )
        self.write_json(
            self.paths.paper_record,
            build_record(
                self.paths.paper_source,
                self.paths.paper_pdf,
                self.paths.paper_log,
            ),
        )
        self.paths.release_pdf.write_bytes(self.paths.paper_pdf.read_bytes())
        self.paths.release_log.write_bytes(self.paths.paper_log.read_bytes())
        self.write_json(
            self.paths.release_pdf_record,
            {
                "schema_version": 1,
                "source": {
                    "path": "paper/main.tex",
                    "sha256": file_sha256(self.paths.paper_source),
                },
                "pdf": {
                    "path": self.paths.release_pdf.relative_to(
                        self.root
                    ).as_posix(),
                    "bytes": self.paths.release_pdf.stat().st_size,
                    "pages": 9,
                    "sha256": file_sha256(self.paths.release_pdf),
                },
                "build": {
                    "engine": "Tectonic 0.17.0",
                    "source_date_epoch": 1788825600,
                    "inspected_platform": "test-platform",
                    "inspected_engine_archive_sha256": "2" * 64,
                    "inspected_engine_sha256": "3" * 64,
                    "latex_log_path": self.paths.release_log.relative_to(
                        self.root
                    ).as_posix(),
                    "latex_log_sha256": file_sha256(
                        self.paths.release_log
                    ),
                },
                "inspection": {
                    "date": "2026-09-07",
                    "pages_inspected": 9,
                    "result": "pass",
                },
            },
        )
        (self.root / "CITATION.cff").write_text(
            "cff-version: 1.2.0\nversion: 0.1.0\n",
            encoding="ascii",
        )

    def make_release_manifest(self, gate: dict[str, object]) -> None:
        self.write_json(self.root / "research/release-gate.json", gate)
        required_stubs = (
            "README.md",
            "CITATION.cff",
            ".zenodo.json",
            "PUBLICATION.md",
            "THIRD_PARTY_NOTICES.md",
            "third_party/drat-trim/LICENSE",
            "tools/replay_proofs.py",
            "tools/replay_c8_proofs.py",
            "tools/record_paper_build.py",
            "tools/build_release_assets.py",
            "tools/verify_release_gate.py",
            "docs/detail.md",
        )
        for relative in required_stubs:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(relative + "\n", encoding="ascii")
        lines = []
        package_files = sorted(
            path
            for path in self.root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and "build" not in path.relative_to(self.root).parts
            and "dist" not in path.relative_to(self.root).parts
            and path != self.paths.release_manifest
        )
        for path in package_files:
            relative = path.relative_to(self.root).as_posix()
            lines.append(f"{file_sha256(path)}  {relative}\n")
        self.paths.release_manifest.write_text(
            "".join(lines),
            encoding="ascii",
        )

    def retain_replay_evidence(self) -> None:
        for source, destination in (
            (self.paths.c6_replay.parent, self.paths.retained_c6_replay.parent),
            (self.paths.c8_replay.parent, self.paths.retained_c8_replay.parent),
        ):
            destination.mkdir(parents=True, exist_ok=True)
            for path in source.iterdir():
                if path.is_file():
                    shutil.copy2(path, destination / path.name)

    def make_evidence(self) -> None:
        self.make_c6_evidence()
        self.make_c8_evidence()
        self.make_paper_evidence()
        self.retain_replay_evidence()
        self.make_release_manifest(complete_gate())
        self.make_release_assets()

    def make_release_assets(self) -> None:
        self.paths.release_dir.mkdir(parents=True, exist_ok=True)
        version = "0.1.0"
        paper_name = f"ramsey-number-5-5-paper-v{version}.pdf"
        source_name = f"ramsey-number-5-5-source-v{version}.tar.gz"
        (self.root / "CITATION.cff").write_text(
            f"cff-version: 1.2.0\nversion: {version}\n",
            encoding="ascii",
        )
        (self.paths.release_dir / paper_name).write_bytes(
            self.paths.release_pdf.read_bytes()
        )
        manifest_entries = []
        for line in self.paths.release_manifest.read_text(
            encoding="ascii"
        ).splitlines():
            _, relative = line.split("  ", maxsplit=1)
            manifest_entries.append(relative)
        source_path = self.paths.release_dir / source_name
        prefix = f"ramsey-number-5-5-v{version}"
        with source_path.open("wb") as raw_stream:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_stream,
                mtime=0,
            ) as gzip_stream:
                with tarfile.open(
                    fileobj=gzip_stream,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as archive:
                    for relative in (
                        *manifest_entries,
                        self.paths.release_manifest.name,
                    ):
                        data = (self.root / relative).read_bytes()
                        info = tarfile.TarInfo(f"{prefix}/{relative}")
                        info.size = len(data)
                        source_mode = (self.root / relative).stat().st_mode
                        info.mode = 0o755 if source_mode & 0o111 else 0o644
                        info.mtime = 0
                        info.uid = 0
                        info.gid = 0
                        info.uname = "root"
                        info.gname = "root"
                        archive.addfile(info, io.BytesIO(data))
        lines = []
        for name in sorted((paper_name, source_name)):
            lines.append(
                f"{file_sha256(self.paths.release_dir / name)}  {name}\n"
            )
        (self.paths.release_dir / "SHA256SUMS").write_text(
            "".join(lines),
            encoding="ascii",
        )

    def test_candidate_hold_is_accepted_with_complete_technical_evidence(
        self,
    ) -> None:
        gate = complete_gate()
        gate["decision"] = "hold"
        gate["artifact_reproducibility_ready"] = False
        gate["theorem_announcement_ready"] = False
        for name in (
            "final_release_snapshot_audit_passes",
            "paper_build_and_inspection_passes",
            "independent_package_review_passes",
            "hosted_candidate_ci_passes",
        ):
            gate["gates"][name] = False

        self.assertEqual(
            [],
            validation_errors(gate, self.paths, mode="candidate"),
        )

    def test_missing_c6_replay_is_rejected(self) -> None:
        self.paths.c6_replay.unlink()
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertTrue(any("c6 replay is missing" in error for error in errors))

    def test_partial_c8_replay_is_rejected(self) -> None:
        replay = json.loads(self.paths.c8_replay.read_text(encoding="ascii"))
        replay["branches"].pop()
        replay["verified_branch_count"] = 9
        self.write_json(self.paths.c8_replay, replay)

        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertTrue(any("c8 replay" in error for error in errors))

    def test_wrong_certificate_manifest_hash_is_rejected(self) -> None:
        replay = json.loads(self.paths.c6_replay.read_text(encoding="ascii"))
        replay["certificate_manifest"]["sha256"] = "0" * 64
        self.write_json(self.paths.c6_replay, replay)

        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertIn("c6 replay manifest hash mismatch", errors)

    def test_manifest_checks_nonrequired_file_hashes(self) -> None:
        (self.root / "docs/detail.md").write_text(
            "changed\n",
            encoding="ascii",
        )
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertIn(
            "release manifest hash mismatch: docs/detail.md",
            errors,
        )

    def test_tampered_retained_branch_log_is_rejected(self) -> None:
        log = (
            self.paths.retained_c6_replay.parent
            / "p3-c6-k0-fresh-drat-trim.log"
        )
        log.write_text("changed\n", encoding="ascii")
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertTrue(
            any(
                "checker log hash mismatch" in error
                for error in errors
            )
        )

    def test_retained_replay_rejects_traversal_log_path(self) -> None:
        replay = json.loads(
            self.paths.retained_c6_replay.read_text(encoding="ascii")
        )
        replay["branches"][0]["checker"]["log"] = "../outside.log"
        self.write_json(self.paths.retained_c6_replay, replay)
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertTrue(
            any("checker log path is unsafe" in error for error in errors)
        )

    def test_retained_replay_rejects_traversal_checker_path(self) -> None:
        replay = json.loads(
            self.paths.retained_c6_replay.read_text(encoding="ascii")
        )
        replay["checker"] = "../outside"
        self.write_json(self.paths.retained_c6_replay, replay)
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertIn("c6 checker binary path is unsafe", errors)

    def test_retained_replay_rejects_symlinked_log(self) -> None:
        replay = json.loads(
            self.paths.retained_c6_replay.read_text(encoding="ascii")
        )
        source = (
            self.paths.retained_c6_replay.parent
            / "p3-c6-k0-fresh-drat-trim.log"
        )
        alias = self.paths.retained_c6_replay.parent / "alias.log"
        alias.symlink_to(source.name)
        replay["branches"][0]["checker"]["log"] = alias.name
        replay["branches"][0]["checker"]["log_sha256"] = file_sha256(source)
        self.write_json(self.paths.retained_c6_replay, replay)
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertTrue(
            any(
                "checker log is missing or unsafe" in error
                for error in errors
            )
        )

    def test_retained_replay_log_requires_manifest_binding(self) -> None:
        omitted = "evidence/replay-c6/p3-c6-k0-fresh-drat-trim.log"
        lines = [
            line
            for line in self.paths.release_manifest.read_text(
                encoding="ascii"
            ).splitlines()
            if not line.endswith("  " + omitted)
        ]
        self.paths.release_manifest.write_text(
            "\n".join(lines) + "\n",
            encoding="ascii",
        )
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertIn(
            "c6 replay branch 0 checker log is not bound by the release manifest",
            errors,
        )

    def test_stale_paper_is_rejected(self) -> None:
        self.paths.paper_source.write_text(
            "\\documentclass{book}\n",
            encoding="ascii",
        )
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="candidate",
        )
        self.assertTrue(
            any("paper build evidence failed" in error for error in errors)
        )

    def test_final_mode_requires_release_declarations(self) -> None:
        gate = complete_gate()
        gate["decision"] = "hold"
        gate["artifact_reproducibility_ready"] = False
        gate["gates"]["independent_package_review_passes"] = False

        errors = validation_errors(gate, self.paths, mode="final")
        self.assertIn("release-gate decision is not release", errors)
        self.assertIn("artifact reproducibility is not ready", errors)
        self.assertTrue(
            any(
                "independent_package_review_passes" in error
                for error in errors
            )
        )

    def test_complete_final_release_is_accepted(self) -> None:
        self.assertEqual(
            [],
            validation_errors(
                complete_gate(),
                self.paths,
                mode="final",
            ),
        )

    def test_release_paper_drift_is_rejected(self) -> None:
        release_paper = (
            self.paths.release_dir
            / "ramsey-number-5-5-paper-v0.1.0.pdf"
        )
        release_paper.write_bytes(b"%PDF-1.4\nchanged\n")
        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="final",
        )
        self.assertIn(
            "release paper does not match the committed paper",
            errors,
        )

    def test_invalid_source_archive_is_rejected(self) -> None:
        source_name = "ramsey-number-5-5-source-v0.1.0.tar.gz"
        source_path = self.paths.release_dir / source_name
        source_path.write_bytes(b"not a tar archive\n")
        paper_name = "ramsey-number-5-5-paper-v0.1.0.pdf"
        (self.paths.release_dir / "SHA256SUMS").write_text(
            (
                f"{file_sha256(self.paths.release_dir / paper_name)}  "
                f"{paper_name}\n"
                f"{file_sha256(source_path)}  {source_name}\n"
            ),
            encoding="ascii",
        )

        errors = validation_errors(
            complete_gate(),
            self.paths,
            mode="final",
        )
        self.assertTrue(
            any(
                "release source archive is invalid" in error
                for error in errors
            )
        )

    def test_final_release_requires_hosted_candidate_ci(self) -> None:
        gate = complete_gate()
        gate["gates"]["hosted_candidate_ci_passes"] = False
        errors = validation_errors(gate, self.paths, mode="final")
        self.assertTrue(
            any(
                "hosted_candidate_ci_passes" in error
                for error in errors
            )
        )

    def test_release_identity_is_bound_to_exact_tag(self) -> None:
        repository = self.root / "identity-repository"
        repository.mkdir()
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Release Fixture"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture.invalid"],
            cwd=repository,
            check=True,
        )
        payload = repository / "payload"
        payload.write_text("first\n", encoding="ascii")
        subprocess.run(["git", "add", "payload"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "first"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "tag", "-a", "v0.1.0", "-m", "Release v0.1.0"],
            cwd=repository,
            check=True,
        )

        self.assertEqual(
            [],
            release_identity_errors(
                repository,
                "HEAD",
                "v0.1.0",
                "0.1.0",
                "final",
            ),
        )
        self.assertEqual(
            [],
            release_identity_errors(
                repository,
                "HEAD",
                None,
                "0.1.0",
                "candidate",
            ),
        )
        payload.write_text("second\n", encoding="ascii")
        subprocess.run(["git", "add", "payload"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "second"],
            cwd=repository,
            check=True,
        )
        errors = release_identity_errors(
            repository,
            "HEAD",
            "v0.1.0",
            "0.1.0",
            "final",
        )
        self.assertTrue(
            any("expected" in error for error in errors)
        )
        errors = release_identity_errors(
            repository,
            "v0.1.0",
            "v0.1.0",
            "0.1.0",
            "final",
        )
        self.assertTrue(
            any("checked-out HEAD" in error for error in errors)
        )

    def test_final_release_rejects_lightweight_tag(self) -> None:
        repository = self.root / "lightweight-tag-repository"
        repository.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Release Fixture"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture.invalid"],
            cwd=repository,
            check=True,
        )
        (repository / "payload").write_text("payload\n", encoding="ascii")
        subprocess.run(["git", "add", "payload"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "payload"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "tag", "v0.1.0"],
            cwd=repository,
            check=True,
        )
        errors = release_identity_errors(
            repository,
            "HEAD",
            "v0.1.0",
            "0.1.0",
            "final",
        )
        self.assertIn("release tag must be an annotated tag object", errors)

    def test_hosted_candidate_record_must_report_success(self) -> None:
        gate = complete_gate()
        gate["hosted_candidate_ci"]["conclusion"] = "failure"
        errors = validation_errors(gate, self.paths, mode="final")
        self.assertIn("hosted candidate CI did not pass", errors)

    def test_hosted_candidate_sha_must_ancestor_release(self) -> None:
        repository = self.root / "candidate-ancestor-repository"
        repository.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Release Fixture"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture.invalid"],
            cwd=repository,
            check=True,
        )
        payload = repository / "payload"
        payload.write_text("candidate\n", encoding="ascii")
        subprocess.run(["git", "add", "payload"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "candidate"],
            cwd=repository,
            check=True,
        )
        candidate = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        payload.write_text("release\n", encoding="ascii")
        subprocess.run(["git", "add", "payload"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "release"],
            cwd=repository,
            check=True,
        )
        gate = complete_gate()
        gate["hosted_candidate_ci"]["head_sha"] = candidate
        self.assertEqual(
            [],
            hosted_candidate_commit_errors(
                gate,
                repository,
                "HEAD",
                "final",
            ),
        )

    def test_release_snapshot_requires_a_clean_checkout(self) -> None:
        repository = self.root / "clean-repository"
        repository.mkdir()
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Release Fixture"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture.invalid"],
            cwd=repository,
            check=True,
        )
        payload = repository / "payload"
        payload.write_text("clean\n", encoding="ascii")
        subprocess.run(["git", "add", "payload"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "clean"],
            cwd=repository,
            check=True,
        )
        self.assertEqual([], repository_clean_errors(repository))
        payload.write_text("dirty\n", encoding="ascii")
        self.assertEqual(
            ["release snapshot has tracked or untracked changes"],
            repository_clean_errors(repository),
        )

    def test_hosted_environment_is_bound_to_release_identity(self) -> None:
        repository = self.root / "hosted-repository"
        repository.mkdir()
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Release Fixture"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture.invalid"],
            cwd=repository,
            check=True,
        )
        (repository / "payload").write_text("payload\n", encoding="ascii")
        subprocess.run(["git", "add", "payload"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "payload"],
            cwd=repository,
            check=True,
        )
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        environment = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "ruturajr-raval/ramsey-number-5-5",
            "GITHUB_SHA": commit,
            "GITHUB_REF_TYPE": "tag",
            "GITHUB_REF_NAME": "v0.1.0",
            "GITHUB_RUN_ID": "12345",
        }
        self.assertEqual(
            [],
            hosted_environment_errors(
                repository,
                "HEAD",
                "v0.1.0",
                environment,
            ),
        )
        environment["GITHUB_SHA"] = "0" * 40
        errors = hosted_environment_errors(
            repository,
            "HEAD",
            "v0.1.0",
            environment,
        )
        self.assertIn(
            "hosted release SHA does not match the release reference",
            errors,
        )
        environment["GITHUB_SHA"] = commit
        environment["GITHUB_REPOSITORY"] = (
            "ruturajr-raval/ramsey-number-5-5-research-workbench"
        )
        errors = hosted_environment_errors(
            repository,
            "HEAD",
            "v0.1.0",
            environment,
        )
        self.assertIn("hosted release repository is unexpected", errors)

    def test_hosted_environment_requires_github_actions(self) -> None:
        self.assertEqual(
            ["final release verification requires GitHub Actions"],
            hosted_environment_errors(
                self.root,
                "HEAD",
                "v0.1.0",
                {},
            ),
        )

    def test_reference_snapshot_uses_git_tree_not_local_manifest(self) -> None:
        repository = self.root / "reference-repository"
        repository.mkdir()
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Release Fixture"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture.invalid"],
            cwd=repository,
            check=True,
        )
        citation = repository / "CITATION.cff"
        citation.write_text(
            "cff-version: 1.2.0\nversion: 0.1.0\n",
            encoding="ascii",
        )
        payload = repository / "payload"
        payload.write_text("payload\n", encoding="ascii")
        manifest = repository / "release-manifest.sha256"
        manifest.write_text(
            (
                f"{file_sha256(citation)}  CITATION.cff\n"
                f"{file_sha256(payload)}  payload\n"
            ),
            encoding="ascii",
        )
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "snapshot"],
            cwd=repository,
            check=True,
        )
        manifest.write_text(
            (
                f"{'0' * 64}  CITATION.cff\n"
                f"{file_sha256(payload)}  payload\n"
            ),
            encoding="ascii",
        )
        paths = replace(
            self.paths,
            root=repository,
            release_manifest=manifest,
            release_dir=repository / "dist/release",
        )
        errors = reference_snapshot_errors(paths, "HEAD", "0.1.0")
        self.assertTrue(
            any(
                "differs from Git-reference content" in error
                for error in errors
            )
        )

    def test_reference_snapshot_rejects_archive_content_drift(self) -> None:
        repository = self.root / "archive-reference-repository"
        repository.mkdir()
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Release Fixture"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "fixture.invalid"],
            cwd=repository,
            check=True,
        )
        citation = repository / "CITATION.cff"
        citation.write_text(
            "cff-version: 1.2.0\nversion: 0.1.0\n",
            encoding="ascii",
        )
        payload = repository / "payload"
        payload.write_text("payload\n", encoding="ascii")
        manifest = repository / "release-manifest.sha256"
        manifest.write_text(
            (
                f"{file_sha256(citation)}  CITATION.cff\n"
                f"{file_sha256(payload)}  payload\n"
            ),
            encoding="ascii",
        )
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "snapshot"],
            cwd=repository,
            check=True,
        )

        release_dir = repository / "dist/release"
        release_dir.mkdir(parents=True)
        archive_path = (
            release_dir / "ramsey-number-5-5-source-v0.1.0.tar.gz"
        )
        prefix = "ramsey-number-5-5-v0.1.0"
        with archive_path.open("wb") as raw_stream:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_stream,
                mtime=0,
            ) as gzip_stream:
                with tarfile.open(
                    fileobj=gzip_stream,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as archive:
                    for relative in (
                        "CITATION.cff",
                        "payload",
                        "release-manifest.sha256",
                    ):
                        data = (repository / relative).read_bytes()
                        if relative == "payload":
                            data = b"changed\n"
                        info = tarfile.TarInfo(f"{prefix}/{relative}")
                        info.size = len(data)
                        info.mode = 0o644
                        info.mtime = 0
                        info.uid = 0
                        info.gid = 0
                        info.uname = "root"
                        info.gname = "root"
                        archive.addfile(info, io.BytesIO(data))

        paths = replace(
            self.paths,
            root=repository,
            release_manifest=manifest,
            release_dir=release_dir,
        )
        errors = reference_snapshot_errors(paths, "HEAD", "0.1.0")
        self.assertIn(
            (
                "release source archive versus Git reference hash mismatch: "
                "payload"
            ),
            errors,
        )

    def test_final_archive_checker_rejects_unsafe_member_shapes(self) -> None:
        prefix = "ramsey-number-5-5-v0.1.0/"
        expected = {
            "payload": ReferenceEntry(
                hashlib.sha256(b"payload\n").hexdigest(),
                0o644,
            )
        }
        cases = (
            "symlink",
            "hardlink",
            "traversal",
            "absolute",
            "metadata",
            "mode",
            "pax",
        )
        for case in cases:
            with self.subTest(case=case):
                archive_path = self.root / f"final-{case}.tar.gz"
                name = f"{prefix}payload"
                if case == "traversal":
                    name = f"{prefix}../escape"
                elif case == "absolute":
                    name = "/escape"
                info = tarfile.TarInfo(name)
                info.mode = 0o600 if case == "mode" else 0o644
                info.mtime = 0
                info.uid = 1 if case == "metadata" else 0
                info.gid = 0
                info.uname = "root"
                info.gname = "root"
                if case == "pax":
                    info.pax_headers = {"GNU.sparse.map": "0,8"}
                data: io.BytesIO | None = io.BytesIO(b"payload\n")
                info.size = len(b"payload\n")
                if case == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = "payload"
                    info.size = 0
                    data = None
                elif case == "hardlink":
                    info.type = tarfile.LNKTYPE
                    info.linkname = f"{prefix}payload"
                    info.size = 0
                    data = None
                with tarfile.open(
                    archive_path,
                    mode="w:gz",
                    format=tarfile.PAX_FORMAT,
                ) as archive:
                    archive.addfile(info, data)
                errors = archive_entry_errors(
                    archive_path,
                    prefix,
                    expected,
                    "final archive",
                )
                self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
