from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from record_paper_build import build_record
from verify_release_gate import (
    C6_CLAIM,
    C8_CLAIM,
    EXPECTED_CANDIDATE_CLAIM,
    EXPECTED_CHECKER_SOURCE_COMMIT,
    GATE_NAMES,
    EvidencePaths,
    file_sha256,
    validation_errors,
)


ROOT = Path(__file__).resolve().parents[1]


def complete_gate() -> dict[str, object]:
    return {
        "schema_version": 2,
        "project": "ramsey-number-5-5",
        "evaluated_at": "2026-09-07",
        "candidate_claim": EXPECTED_CANDIDATE_CLAIM,
        "gates": {name: True for name in GATE_NAMES},
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
            c6_manifest=self.root / "evidence/c6/certificate-manifest.json",
            c8_manifest=self.root / "evidence/c8/certificate-manifest.json",
            paper_source=self.root / "paper/main.tex",
            paper_pdf=self.root / "build/paper/main.pdf",
            paper_log=self.root / "build/paper/main.log",
            paper_record=self.root / "build/paper/paper-build.json",
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

    def make_c6_evidence(self) -> None:
        branches = []
        for branch in range(4):
            branches.append(
                {
                    "branch": branch,
                    "cnf": self.artifact(f"p3-c6-k{branch}.cnf"),
                    "proof": self.artifact(f"p3-c6-k{branch}.drat.xz"),
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

    def make_release_manifest(self, gate: dict[str, object]) -> None:
        self.write_json(self.root / "research/release-gate.json", gate)
        required_stubs = (
            "README.md",
            "CITATION.cff",
            ".zenodo.json",
            "PUBLICATION.md",
            "tools/replay_proofs.py",
            "tools/replay_c8_proofs.py",
            "tools/record_paper_build.py",
            "tools/build_release_assets.py",
            "tools/verify_release_gate.py",
        )
        for relative in required_stubs:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(relative + "\n", encoding="ascii")
        required = (
            *(self.root / relative for relative in required_stubs),
            self.root / "research/release-gate.json",
            self.paths.c6_manifest,
            self.paths.c8_manifest,
            self.paths.paper_source,
        )
        lines = []
        for path in sorted(required):
            relative = path.relative_to(self.root).as_posix()
            lines.append(f"{file_sha256(path)}  {relative}\n")
        self.paths.release_manifest.write_text(
            "".join(lines),
            encoding="ascii",
        )

    def make_evidence(self) -> None:
        self.make_c6_evidence()
        self.make_c8_evidence()
        self.make_paper_evidence()
        self.make_release_assets()
        self.make_release_manifest(complete_gate())

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
            self.paths.paper_pdf.read_bytes()
        )
        (self.paths.release_dir / source_name).write_bytes(
            b"source archive fixture\n"
        )
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
            "release paper does not match the inspected paper",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
