from __future__ import annotations

import hashlib
import json
import lzma
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from compact_c8_proof import extraction_arguments
from replay_c8_proofs import (
    EXPECTED_CHECKER_SOURCE_COMMIT,
    EXPECTED_HISTORICAL_CHECKER_SHA256,
    EXPECTED_SOLVER_SHA256,
    EXPECTED_SOLVER_SOURCE_COMMIT,
    replay_artifact,
)


ROOT = Path(__file__).resolve().parents[1]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class C8ReplayProvenanceTests(unittest.TestCase):
    def test_compaction_defaults_to_single_pass(self) -> None:
        core_path = Path("core.drat")
        self.assertEqual(
            extraction_arguments(core_path, False),
            ["-C", "-l", "core.drat"],
        )
        self.assertEqual(
            extraction_arguments(core_path, True),
            ["-O", "-C", "-l", "core.drat"],
        )

    def setUp(self) -> None:
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=build,
            prefix="c8-replay-test-",
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.formulas = self.root / "formulas"
        self.evidence = self.root / "evidence"
        self.logs = self.root / "logs"
        for directory in (self.formulas, self.evidence, self.logs):
            directory.mkdir()

        self.stem = "p3-c8-t3-p0-z0"
        self.branch = (3, 0, 0)
        self.cnf_path = self.formulas / f"{self.stem}.cnf"
        self.cnf_path.write_bytes(b"p cnf 1 1\n1 0\n")
        self.cnf_sha256 = sha256_file(self.cnf_path)
        metadata = {
            "clauses": 1,
            "cycles": 8,
            "degree_bounds": [18, 24],
            "fixed": 19,
            "homogeneous_size": 5,
            "order": 43,
            "order_three_eight_structure": True,
            "prime": 3,
            "root_adjacent_cycles": None,
            "root_adjacent_triangle_cycles": 0,
            "root_nonadjacent_independent_cycles": 0,
            "sha256": self.cnf_sha256,
            "t4_mixed_matrix": None,
            "triangle_cycles": 3,
            "variables": 1,
        }
        self.write_json(
            self.formulas / f"{self.stem}.json",
            metadata,
        )

        source_proof = b"source proof payload\n"
        source_compressed = lzma.compress(source_proof)
        self.source_proof_sha256 = sha256_bytes(source_compressed)
        self.source_proof_bytes = len(source_compressed)

        compacted_proof = b"0\n"
        self.proof_path = self.evidence / f"{self.stem}.drat.xz"
        self.proof_path.write_bytes(lzma.compress(compacted_proof))

        self.solver_log_path = (
            self.evidence / f"{self.stem}-proof.log"
        )
        self.solver_log_path.write_text(
            "\n".join(
                (
                    f"c Solver source commit {EXPECTED_SOLVER_SOURCE_COMMIT}",
                    f"c Solver SHA-256 {EXPECTED_SOLVER_SHA256}",
                    f"c CNF SHA-256 {self.cnf_sha256}",
                    f"proof_bytes={self.source_proof_bytes}",
                    f"proof_sha256={self.source_proof_sha256}",
                    "s UNSATISFIABLE",
                    "real 1.25",
                    "kissat_exit=20",
                    "",
                )
            ),
            encoding="ascii",
        )
        self.artifact_binding = {
            "cnf_sha256_logged": True,
            "mode": "solver-log",
            "proof_bytes_logged": True,
            "proof_sha256_logged": True,
        }

        self.run_path = self.evidence / f"{self.stem}-run.json"
        self.write_json(
            self.run_path,
            {
                "artifact_binding": self.artifact_binding,
                "branch": list(self.branch),
                "cnf": {
                    "bytes": self.cnf_path.stat().st_size,
                    "clauses": 1,
                    "path": self.cnf_path.name,
                    "sha256": self.cnf_sha256,
                    "variables": 1,
                },
                "proof": {
                    "compressed_bytes": self.source_proof_bytes,
                    "compressed_sha256": self.source_proof_sha256,
                    "path": self.proof_path.name,
                },
                "record_complete": True,
                "solver": {
                    "binary_sha256": EXPECTED_SOLVER_SHA256,
                    "exit_code": 20,
                    "log": self.solver_log_path.name,
                    "log_sha256": sha256_file(self.solver_log_path),
                    "result": "UNSATISFIABLE",
                    "source_commit": EXPECTED_SOLVER_SOURCE_COMMIT,
                    "wall_seconds": 1.25,
                },
            },
        )

        self.extraction_log_path = (
            self.evidence / f"{self.stem}-extract.log"
        )
        self.verification_log_path = (
            self.evidence / f"{self.stem}-verify.log"
        )
        self.extraction_log_path.write_text(
            (
                "c finished parsing, read {} bytes from proof file\n"
                "s VERIFIED\n"
                "drat_trim_exit_code=0\n"
            ).format(len(source_proof)),
            encoding="ascii",
        )
        self.verification_log_path.write_text(
            "s VERIFIED\ndrat_trim_exit_code=0\n",
            encoding="ascii",
        )

        self.compaction_path = (
            self.evidence / f"{self.stem}-compaction.json"
        )
        self.write_json(
            self.compaction_path,
            {
                "checker": {
                    "path": "drat-trim",
                    "sha256": EXPECTED_HISTORICAL_CHECKER_SHA256,
                    "source_commit": EXPECTED_CHECKER_SOURCE_COMMIT,
                },
                "cnf": {
                    "bytes": self.cnf_path.stat().st_size,
                    "path": self.cnf_path.name,
                    "sha256": self.cnf_sha256,
                },
                "compacted_proof": {
                    "compressed_bytes": self.proof_path.stat().st_size,
                    "compressed_sha256": sha256_file(self.proof_path),
                    "decompressed_bytes": len(compacted_proof),
                    "decompressed_sha256": sha256_bytes(compacted_proof),
                    "path": self.proof_path.name,
                    "role": "retained-core",
                },
                "extraction": {
                    "log": self.extraction_log_path.name,
                    "log_sha256": sha256_file(
                        self.extraction_log_path
                    ),
                    "strategy": "single-pass",
                    "wall_seconds": 0.1,
                },
                "source_proof": {
                    "compressed_bytes": self.source_proof_bytes,
                    "compressed_sha256": self.source_proof_sha256,
                    "decompressed_bytes": len(source_proof),
                    "decompressed_sha256": sha256_bytes(source_proof),
                    "path": self.proof_path.name,
                    "role": "solver-output",
                },
                "verification": {
                    "log": self.verification_log_path.name,
                    "log_sha256": sha256_file(
                        self.verification_log_path
                    ),
                    "wall_seconds": 0.1,
                },
                "verified": True,
            },
        )

        self.checker = self.root / "checker"
        self.checker.write_text(
            "#!/bin/sh\n"
            "bytes=$(wc -c | tr -d ' ')\n"
            "printf 'c read %s bytes from proof file\\n' \"$bytes\"\n"
            "printf 's VERIFIED\\n'\n",
            encoding="ascii",
        )
        self.checker.chmod(0o755)

    @staticmethod
    def write_json(path: Path, value: dict[str, object]) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )

    def replay(self) -> dict[str, object]:
        return replay_artifact(
            self.checker,
            self.formulas,
            self.evidence,
            self.evidence,
            self.logs,
            self.stem,
            self.branch,
        )

    def test_complete_provenance_chain_is_accepted(self) -> None:
        record = self.replay()
        self.assertEqual(record["artifact_binding"], self.artifact_binding)
        self.assertEqual(
            record["run_record"]["sha256"],
            sha256_file(self.run_path),
        )
        self.assertEqual(
            record["compaction_record"]["sha256"],
            sha256_file(self.compaction_path),
        )

    def test_tampered_run_record_is_rejected(self) -> None:
        run = json.loads(self.run_path.read_text(encoding="ascii"))
        run["solver"]["log_sha256"] = "0" * 64
        self.write_json(self.run_path, run)
        with self.assertRaisesRegex(
            AssertionError,
            "solver run provenance mismatch",
        ):
            self.replay()

    def test_tampered_compaction_log_is_rejected(self) -> None:
        self.verification_log_path.write_text(
            "s VERIFIED\ndrat_trim_exit_code=0\ntampered\n",
            encoding="ascii",
        )
        with self.assertRaisesRegex(
            AssertionError,
            "compaction verification hash mismatch",
        ):
            self.replay()

    def test_incomplete_source_proof_record_is_rejected(self) -> None:
        compaction = json.loads(
            self.compaction_path.read_text(encoding="ascii")
        )
        del compaction["source_proof"]["decompressed_sha256"]
        self.write_json(self.compaction_path, compaction)
        with self.assertRaisesRegex(
            AssertionError,
            "source proof fields are incomplete",
        ):
            self.replay()

    def test_source_proof_byte_attestation_is_checked(self) -> None:
        compaction = json.loads(
            self.compaction_path.read_text(encoding="ascii")
        )
        compaction["source_proof"]["decompressed_bytes"] += 1
        self.write_json(self.compaction_path, compaction)
        with self.assertRaisesRegex(
            AssertionError,
            "decompressed byte count mismatch",
        ):
            self.replay()

    def test_multipart_compacted_proof_is_replayed(self) -> None:
        payload = self.proof_path.read_bytes()
        split_at = max(1, len(payload) // 2)
        parts = (payload[:split_at], payload[split_at:])
        part_records = []
        for index, part in enumerate(parts):
            path = self.evidence / (
                f"{self.proof_path.name}.part-{index:03d}"
            )
            path.write_bytes(part)
            part_records.append(
                {
                    "bytes": len(part),
                    "path": path.name,
                    "sha256": sha256_bytes(part),
                }
            )
        compaction = json.loads(
            self.compaction_path.read_text(encoding="ascii")
        )
        compaction["compacted_proof"]["parts"] = part_records
        self.write_json(self.compaction_path, compaction)
        self.proof_path.unlink()

        record = self.replay()
        self.assertEqual(record["proof"]["parts"], part_records)

    def test_tampered_multipart_proof_is_rejected(self) -> None:
        payload = self.proof_path.read_bytes()
        part_records = []
        for index, part in enumerate((payload[:1], payload[1:])):
            path = self.evidence / (
                f"{self.proof_path.name}.part-{index:03d}"
            )
            path.write_bytes(part)
            part_records.append(
                {
                    "bytes": len(part),
                    "path": path.name,
                    "sha256": sha256_bytes(part),
                }
            )
        compaction = json.loads(
            self.compaction_path.read_text(encoding="ascii")
        )
        compaction["compacted_proof"]["parts"] = part_records
        self.write_json(self.compaction_path, compaction)
        self.proof_path.unlink()
        first_part = self.evidence / part_records[0]["path"]
        first_part.write_bytes(b"tampered")

        with self.assertRaisesRegex(
            AssertionError,
            "part metadata mismatch",
        ):
            self.replay()

    def test_orphan_part_is_rejected_for_single_file(self) -> None:
        orphan = self.evidence / f"{self.proof_path.name}.part-000"
        orphan.write_bytes(b"orphan")
        with self.assertRaisesRegex(
            AssertionError,
            "unreferenced multipart artifacts",
        ):
            self.replay()

    def test_orphan_multipart_part_is_rejected(self) -> None:
        payload = self.proof_path.read_bytes()
        part_records = []
        for index, part in enumerate((payload[:1], payload[1:])):
            path = self.evidence / (
                f"{self.proof_path.name}.part-{index:03d}"
            )
            path.write_bytes(part)
            part_records.append(
                {
                    "bytes": len(part),
                    "path": path.name,
                    "sha256": sha256_bytes(part),
                }
            )
        compaction = json.loads(
            self.compaction_path.read_text(encoding="ascii")
        )
        compaction["compacted_proof"]["parts"] = part_records
        self.write_json(self.compaction_path, compaction)
        self.proof_path.unlink()
        (
            self.evidence / f"{self.proof_path.name}.part-002"
        ).write_bytes(b"orphan")

        with self.assertRaisesRegex(
            AssertionError,
            "unreferenced or missing parts",
        ):
            self.replay()

    def test_splitter_publishes_exact_transactional_parts(self) -> None:
        output_directory = self.root / "split-output"
        output_record = output_directory / "split-compaction.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "split_c8_proof.py"),
                "--proof",
                str(self.proof_path),
                "--compaction-record",
                str(self.compaction_path),
                "--output-directory",
                str(output_directory),
                "--output-record",
                str(output_record),
                "--part-bytes",
                "10",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        compacted = json.loads(
            output_record.read_text(encoding="ascii")
        )["compacted_proof"]
        parts = compacted["parts"]
        self.assertGreaterEqual(len(parts), 2)
        self.assertTrue(all(part["bytes"] <= 10 for part in parts))
        reassembled = b"".join(
            (output_directory / part["path"]).read_bytes()
            for part in parts
        )
        self.assertEqual(reassembled, self.proof_path.read_bytes())
        self.assertFalse(any(output_directory.glob("*.tmp")))

    def test_splitter_rejects_broken_output_symlink(self) -> None:
        output_directory = self.root / "split-output"
        output_directory.symlink_to(self.root / "missing-target")
        output_record = output_directory / "split-compaction.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "split_c8_proof.py"),
                "--proof",
                str(self.proof_path),
                "--compaction-record",
                str(self.compaction_path),
                "--output-directory",
                str(output_directory),
                "--output-record",
                str(output_record),
                "--part-bytes",
                "10",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "missing-target").exists())

    def test_unknown_extraction_strategy_is_rejected(self) -> None:
        compaction = json.loads(
            self.compaction_path.read_text(encoding="ascii")
        )
        compaction["extraction"]["strategy"] = "unknown"
        self.write_json(self.compaction_path, compaction)
        with self.assertRaisesRegex(
            AssertionError,
            "compaction extraction strategy mismatch",
        ):
            self.replay()

    def test_unexpected_historical_checker_is_rejected(self) -> None:
        compaction = json.loads(
            self.compaction_path.read_text(encoding="ascii")
        )
        compaction["checker"]["sha256"] = "0" * 64
        self.write_json(self.compaction_path, compaction)
        with self.assertRaisesRegex(
            AssertionError,
            "compaction checker mismatch",
        ):
            self.replay()


if __name__ == "__main__":
    unittest.main()
