from __future__ import annotations

import argparse
import subprocess
import sys
import unittest
from pathlib import Path

from c8_certificate_branches import (
    RETAINED_CANONICAL_BRANCHES,
    RETAINED_T4_SPLIT_BRANCHES,
    ROOT_BRANCHES,
    canonical_stem,
    t4_split_stem,
)
from replay_c8_proofs import (
    index_certificate_records,
    parse_branch,
    parse_t4_split_branch,
    validate_certificate_branch_record,
)


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "tools" / "replay_c8_proofs.py"


class C8CertificateBranchTests(unittest.TestCase):
    def test_retained_family_has_six_plus_four_branches(self) -> None:
        self.assertEqual(len(ROOT_BRANCHES), 8)
        self.assertEqual(len(RETAINED_CANONICAL_BRANCHES), 6)
        self.assertEqual(len(RETAINED_T4_SPLIT_BRANCHES), 4)
        self.assertEqual(
            {branch[0] for branch in RETAINED_CANONICAL_BRANCHES},
            {2, 3},
        )
        self.assertEqual(
            set(RETAINED_T4_SPLIT_BRANCHES),
            {
                (0, "two-c4"),
                (0, "c8"),
                (1, "two-c4"),
                (1, "c8"),
            },
        )

    def test_stems_are_unambiguous(self) -> None:
        self.assertEqual(
            canonical_stem((3, 0, 1)),
            "p3-c8-t3-p0-z1",
        )
        self.assertEqual(
            t4_split_stem((1, "two-c4")),
            "p3-c8-t4-p1-z0-mtwo-c4",
        )

    def test_manifest_inventory_rejects_duplicate_branches(self) -> None:
        records = [
            {"branch": list(branch)}
            for branch in RETAINED_CANONICAL_BRANCHES
        ]
        records.extend(
            {
                "branch": [4, root, 0],
                "matrix_type": matrix_type,
            }
            for root, matrix_type in RETAINED_T4_SPLIT_BRANCHES
        )
        self.assertEqual(
            len(index_certificate_records(records, "test manifest")),
            10,
        )
        records[-1] = records[-2]
        with self.assertRaisesRegex(
            AssertionError,
            "duplicate branches",
        ):
            index_certificate_records(records, "test manifest")

    def test_manifest_branch_roles_are_bound(self) -> None:
        expected = {
            "artifact_binding": {"mode": "solver-log"},
            "cnf": {"sha256": "a" * 64},
            "compacted_proof": {
                "role": "retained-core",
                "compressed_sha256": "b" * 64,
            },
            "compaction_record": {"sha256": "c" * 64},
            "run_record": {"sha256": "d" * 64},
            "solver": {"log_sha256": "e" * 64},
            "source_proof": {
                "role": "solver-output",
                "compressed_sha256": "f" * 64,
            },
        }
        observed = {
            "artifact_binding": dict(expected["artifact_binding"]),
            "cnf": dict(expected["cnf"]),
            "compaction_record": dict(expected["compaction_record"]),
            "proof": dict(expected["compacted_proof"]),
            "run_record": dict(expected["run_record"]),
            "solver": dict(expected["solver"]),
            "source_proof": dict(expected["source_proof"]),
        }
        key = (2, 0, 0, None)
        validate_certificate_branch_record(expected, observed, key)

        expected["source_proof"]["role"] = "retained-core"
        with self.assertRaisesRegex(AssertionError, "source proof"):
            validate_certificate_branch_record(expected, observed, key)

        expected["source_proof"]["role"] = "solver-output"
        expected["compacted_proof"]["role"] = "solver-output"
        with self.assertRaisesRegex(AssertionError, "proof"):
            validate_certificate_branch_record(expected, observed, key)

    def test_replay_parsers_accept_only_retained_shapes(self) -> None:
        self.assertEqual(parse_branch("4-1-0"), (4, 1, 0))
        self.assertEqual(
            parse_t4_split_branch("0:c8"),
            (0, "c8"),
        )
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_branch("4-0-1")
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_t4_split_branch("1:unknown")
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_t4_split_branch("two-c4")

    def test_replay_requires_an_explicit_proof_family(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPLAY),
                "missing",
                "--checker",
                "missing",
                "--checker-source",
                "missing",
                "--log-directory",
                "missing",
                "--output",
                "missing",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("retained t4 split directory", result.stderr)

    def test_partial_replay_requires_nonrelease_flag(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPLAY),
                "missing",
                "--direct-t4-crosscheck",
                "--branch",
                "3-0-0",
                "--checker",
                "missing",
                "--checker-source",
                "missing",
                "--log-directory",
                "missing",
                "--output",
                "missing",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --allow-partial", result.stderr)

    def test_full_retained_replay_requires_manifest(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPLAY),
                "missing",
                "--t4-split-artifact-directory",
                "missing",
                "--t4-split-proof-directory",
                "missing",
                "--checker",
                "missing",
                "--checker-source",
                "missing",
                "--log-directory",
                "missing",
                "--output",
                "missing",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --certificate-manifest", result.stderr)

    def test_full_retained_replay_requires_fresh_checker(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPLAY),
                "missing",
                "--t4-split-artifact-directory",
                "missing",
                "--t4-split-proof-directory",
                "missing",
                "--checker",
                "missing",
                "--checker-source",
                "missing",
                "--certificate-manifest",
                "missing",
                "--log-directory",
                "missing",
                "--output",
                "missing",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires --fresh-checker-build", result.stderr)


if __name__ == "__main__":
    unittest.main()
