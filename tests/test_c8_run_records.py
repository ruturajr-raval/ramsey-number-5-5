from __future__ import annotations

import unittest

from record_c8_solver_run import classify_artifact_binding
from replay_c8_proofs import parse_solver_exit_code


class C8RunRecordTests(unittest.TestCase):
    cnf_sha256 = "a" * 64
    proof_sha256 = "b" * 64

    def test_runner_exit_marker_is_accepted(self) -> None:
        self.assertEqual(parse_solver_exit_code("kissat_exit=20\n"), 20)
        self.assertEqual(
            parse_solver_exit_code("c exit 20\nkissat_exit=20\n"),
            20,
        )

    def test_conflicting_exit_marker_is_rejected(self) -> None:
        with self.assertRaises(AssertionError):
            parse_solver_exit_code("c exit 20\nkissat_exit=10\n")

    def test_complete_solver_log_binding_is_verified(self) -> None:
        log = (
            f"c CNF SHA-256 {self.cnf_sha256}\n"
            "proof_bytes=123\n"
            f"proof_sha256={self.proof_sha256}\n"
        )
        self.assertEqual(
            classify_artifact_binding(
                log,
                self.cnf_sha256,
                123,
                self.proof_sha256,
                allow_post_run_attestation=False,
            ),
            {
                "mode": "solver-log",
                "cnf_sha256_logged": True,
                "proof_bytes_logged": True,
                "proof_sha256_logged": True,
            },
        )

    def test_incomplete_solver_log_binding_is_rejected(self) -> None:
        log = f"c CNF SHA-256 {self.cnf_sha256}\n"
        with self.assertRaises(AssertionError):
            classify_artifact_binding(
                log,
                self.cnf_sha256,
                123,
                self.proof_sha256,
                allow_post_run_attestation=True,
            )

    def test_legacy_attestation_requires_explicit_opt_in(self) -> None:
        with self.assertRaises(AssertionError):
            classify_artifact_binding(
                "",
                self.cnf_sha256,
                123,
                self.proof_sha256,
                allow_post_run_attestation=False,
            )
        self.assertEqual(
            classify_artifact_binding(
                "",
                self.cnf_sha256,
                123,
                self.proof_sha256,
                allow_post_run_attestation=True,
            )["mode"],
            "post-run-attestation",
        )


if __name__ == "__main__":
    unittest.main()
