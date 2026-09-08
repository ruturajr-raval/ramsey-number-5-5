from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from verify_tag_release_recovery import (
    ARTIFACT_DIGEST,
    ARTIFACT_EXPIRES_AT,
    ARTIFACT_ID,
    ARTIFACT_NAME,
    ARTIFACT_SIZE,
    FAILED_JOB_ID,
    FAILED_RUN_ID,
    OWNER_AUDITED_AT,
    OWNER_AUDIT_VALID_UNTIL,
    PAPER_LOG_SHA256,
    PUBLICATION_AUTHORIZATION,
    RELEASE_COMMIT,
    REPOSITORY,
    RULESET_ID,
    SUCCESSFUL_STEPS,
    TAG,
    TAG_OBJECT_SHA,
    exact_release_asset_errors,
    expected_ruleset,
    failed_run_errors,
    load_tagged_release_gate_module,
    owner_audit_freshness_errors,
    preflight_evidence_errors,
    record_errors,
    recovery_environment_errors,
    release_checkout_errors,
    restore_tagged_paper_log,
    ruleset_errors,
    ruleset_security_field_sources,
    tag_errors,
)


def valid_record() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": "ramsey-number-5-5",
        "audited_at": OWNER_AUDITED_AT,
        "owner_audit_valid_until": OWNER_AUDIT_VALID_UNTIL,
        "reason": "x" * 120,
        "release": {
            "tag": TAG,
            "tag_object_sha": TAG_OBJECT_SHA,
            "commit_sha": RELEASE_COMMIT,
            "tag_message": "Release v0.1.0",
            "tagger_name": "Ruturaj R Raval",
            "tagger_date": "2026-09-08T16:41:27Z",
            "signature_status": "unsigned",
        },
        "failed_tag_run": {
            "run_id": FAILED_RUN_ID,
            "job_id": FAILED_JOB_ID,
            "event": "push",
            "head_branch": TAG,
            "head_sha": RELEASE_COMMIT,
            "conclusion": "failure",
            "failure_step": "Verify final release gate",
            "candidate_artifact_id": ARTIFACT_ID,
            "candidate_artifact_name": ARTIFACT_NAME,
            "candidate_artifact_size": ARTIFACT_SIZE,
            "candidate_artifact_digest": ARTIFACT_DIGEST,
            "candidate_artifact_expires_at": ARTIFACT_EXPIRES_AT,
            "candidate_evidence_sha256": (
                "012be8884e4e171c00d17b5b1bc0ddf5e44296752f46fc5d251eb4a7f88e6a73"
            ),
            "paper_sha256": (
                "391228329992b56fdad739404940d2fa31a6beb21bb9faee098481b59c5cb512"
            ),
            "paper_build_record_sha256": (
                "559e59b6d98b6c94183a22929cb7e51686ae1c52d7f2ede668ab80b0207fde2b"
            ),
        },
        "ruleset_owner_audit": expected_ruleset(),
    }


def valid_run_payloads() -> tuple[dict[str, object], ...]:
    run = {
        "id": FAILED_RUN_ID,
        "name": "ci",
        "event": "push",
        "status": "completed",
        "conclusion": "failure",
        "head_branch": TAG,
        "head_sha": RELEASE_COMMIT,
    }
    steps = [
        {"name": name, "conclusion": "success"}
        for name in sorted(SUCCESSFUL_STEPS)
    ]
    steps.extend(
        [
            {"name": "Verify final release gate", "conclusion": "failure"},
            {"name": "Upload tag-verified release", "conclusion": "skipped"},
        ]
    )
    jobs = {
        "jobs": [
            {
                "id": FAILED_JOB_ID,
                "name": "verify",
                "conclusion": "failure",
                "steps": steps,
            }
        ]
    }
    artifacts = {
        "artifacts": [
            {
                "id": ARTIFACT_ID,
                "name": ARTIFACT_NAME,
                "size_in_bytes": ARTIFACT_SIZE,
                "digest": ARTIFACT_DIGEST,
                "expired": False,
                "expires_at": ARTIFACT_EXPIRES_AT,
            }
        ]
    }
    return run, jobs, artifacts


class TagReleaseRecoveryTests(unittest.TestCase):
    def test_expected_record_is_accepted(self) -> None:
        self.assertEqual([], record_errors(valid_record()))

    def test_bypass_actor_is_rejected(self) -> None:
        record = valid_record()
        record["ruleset_owner_audit"]["bypass_actors"] = [{"actor_id": 1}]
        self.assertIn(
            "owner-authenticated ruleset audit is unexpected",
            record_errors(record),
        )

    def test_permission_limited_live_ruleset_is_accepted(self) -> None:
        audited = expected_ruleset()
        live = copy.deepcopy(audited)
        del live["bypass_actors"]
        del live["current_user_can_bypass"]
        self.assertEqual([], ruleset_errors(live, audited))
        self.assertEqual(
            {
                "bypass_actors": "owner_audit_only",
                "current_user_can_bypass": "owner_audit_only",
            },
            ruleset_security_field_sources(live),
        )

    def test_live_ruleset_change_is_rejected(self) -> None:
        audited = expected_ruleset()
        live = copy.deepcopy(audited)
        live["conditions"]["ref_name"]["include"] = ["refs/tags/v0.1.0"]
        self.assertTrue(ruleset_errors(live, audited))

    def test_live_bypass_actor_is_rejected(self) -> None:
        audited = expected_ruleset()
        live = copy.deepcopy(audited)
        live["bypass_actors"] = [{"actor_id": 1}]
        self.assertIn(
            "live ruleset reports bypass actors",
            ruleset_errors(live, audited),
        )

    def test_annotated_tag_is_accepted(self) -> None:
        ref = {"object": {"type": "tag", "sha": TAG_OBJECT_SHA}}
        tag = {
            "sha": TAG_OBJECT_SHA,
            "tag": TAG,
            "message": "Release v0.1.0\n",
            "object": {"type": "commit", "sha": RELEASE_COMMIT},
        }
        self.assertEqual([], tag_errors(ref, tag))

    def test_unexpected_tag_target_is_rejected(self) -> None:
        ref = {"object": {"type": "tag", "sha": TAG_OBJECT_SHA}}
        tag = {
            "sha": TAG_OBJECT_SHA,
            "tag": TAG,
            "message": "Release v0.1.0\n",
            "object": {"type": "commit", "sha": "0" * 40},
        }
        self.assertIn(
            "annotated tag target commit is unexpected",
            tag_errors(ref, tag),
        )

    def test_expected_failed_run_is_accepted(self) -> None:
        self.assertEqual([], failed_run_errors(*valid_run_payloads()))

    def test_failed_proof_step_is_rejected(self) -> None:
        run, jobs, artifacts = valid_run_payloads()
        jobs["jobs"][0]["steps"][0]["conclusion"] = "failure"
        self.assertTrue(failed_run_errors(run, jobs, artifacts))

    def test_expired_owner_audit_is_rejected(self) -> None:
        observed = datetime(2026, 9, 10, tzinfo=timezone.utc)
        self.assertIn(
            "owner-authenticated ruleset audit has expired",
            owner_audit_freshness_errors(valid_record(), observed),
        )

    def test_exact_release_asset_hashes_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "dist/release"
            release.mkdir(parents=True)
            payloads = {
                "SHA256SUMS": b"checksums\n",
                "paper.pdf": b"%PDF-test\n",
                "source.tar.gz": b"archive\n",
            }
            for name, payload in payloads.items():
                (release / name).write_bytes(payload)
            expected = {
                name: hashlib.sha256(payload).hexdigest()
                for name, payload in payloads.items()
            }
            self.assertEqual(
                [],
                exact_release_asset_errors(root, expected),
            )
            (release / "source.tar.gz").write_bytes(b"changed\n")
            self.assertIn(
                "tagged release asset hash is unexpected: source.tar.gz",
                exact_release_asset_errors(root, expected),
            )

    def test_recovery_environment_records_real_dispatch_context(self) -> None:
        commit = "1" * 40
        environment = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_REF_NAME": "main",
            "GITHUB_WORKFLOW": "tag-release-recovery",
            "GITHUB_WORKFLOW_REF": (
                f"{REPOSITORY}/.github/workflows/"
                "tag-release-recovery.yml@refs/heads/main"
            ),
            "GITHUB_SHA": commit,
            "GITHUB_RUN_ID": "12345",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        self.assertEqual(
            [],
            recovery_environment_errors(
                environment,
                controller_commit=commit,
            ),
        )
        environment["GITHUB_EVENT_NAME"] = "push"
        environment["GITHUB_REF"] = f"refs/tags/{TAG}"
        environment["GITHUB_REF_TYPE"] = "tag"
        environment["GITHUB_REF_NAME"] = TAG
        self.assertTrue(
            recovery_environment_errors(
                environment,
                controller_commit=commit,
            )
        )

    def test_release_checkout_binds_annotated_tag_and_clean_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Release Fixture"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "fixture.invalid"],
                cwd=root,
                check=True,
            )
            payload = root / "payload"
            payload.write_text("payload\n", encoding="ascii")
            subprocess.run(["git", "add", "payload"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "--quiet", "-m", "payload"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "tag", "-a", TAG, "-m", "Release v0.1.0"],
                cwd=root,
                check=True,
            )
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            tag_object = subprocess.run(
                ["git", "rev-parse", f"refs/tags/{TAG}"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            with (
                patch(
                    "verify_tag_release_recovery.RELEASE_COMMIT",
                    commit,
                ),
                patch(
                    "verify_tag_release_recovery.TAG_OBJECT_SHA",
                    tag_object,
                ),
            ):
                self.assertEqual([], release_checkout_errors(root))
                payload.write_text("changed\n", encoding="ascii")
                self.assertIn(
                    "release checkout has tracked or untracked changes",
                    release_checkout_errors(root),
                )

    def test_tagged_verifier_hash_is_checked_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            marker = root / "executed"
            (tools / "verify_release_gate.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed')\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "tagged release-gate verifier hash is unexpected",
            ):
                load_tagged_release_gate_module(root)
            self.assertFalse(marker.exists())

    def test_preflight_evidence_is_bound_to_final_recovery(self) -> None:
        evidence = {
            "schema_version": 1,
            "project": "ramsey-number-5-5",
            "phase": "preflight",
            "result": "verified",
            "failed_tag_run_id": FAILED_RUN_ID,
            "failed_tag_job_id": FAILED_JOB_ID,
            "candidate_artifact_id": ARTIFACT_ID,
            "candidate_artifact_digest": ARTIFACT_DIGEST,
            "candidate_artifact_expires_at": ARTIFACT_EXPIRES_AT,
            "release_tag": TAG,
            "release_tag_object_sha": TAG_OBJECT_SHA,
            "release_commit": RELEASE_COMMIT,
            "ruleset_id": RULESET_ID,
            "publication_authorization": PUBLICATION_AUTHORIZATION,
            "paper_log_reconstruction": {
                "source": "paper/ramsey-number-5-5-paper-v0.1.0.log",
                "target": "build/paper/main.log",
                "sha256": PAPER_LOG_SHA256,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preflight.json"
            path.write_text(
                json.dumps(evidence),
                encoding="ascii",
            )
            self.assertEqual([], preflight_evidence_errors(path))
            evidence["release_commit"] = "0" * 40
            path.write_text(
                json.dumps(evidence),
                encoding="ascii",
            )
            self.assertTrue(preflight_evidence_errors(path))

    def test_tagged_paper_log_reconstruction_is_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = (
                root / "paper/ramsey-number-5-5-paper-v0.1.0.log"
            )
            target = root / "build/paper/main.log"
            record = root / "build/paper/paper-build.json"
            source.parent.mkdir()
            target.parent.mkdir(parents=True)
            payload = b"deterministic paper log\n"
            digest = hashlib.sha256(payload).hexdigest()
            source.write_bytes(payload)
            record.write_text(
                json.dumps(
                    {
                        "latex_log": {
                            "path": "build/paper/main.log",
                            "reported_bytes": 49068,
                            "reported_output": "main.xdv",
                            "reported_pages": 9,
                            "sha256": digest,
                        }
                    }
                ),
                encoding="ascii",
            )
            with patch(
                "verify_tag_release_recovery.PAPER_LOG_SHA256",
                digest,
            ):
                self.assertEqual([], restore_tagged_paper_log(root))
            self.assertEqual(payload, target.read_bytes())


if __name__ == "__main__":
    unittest.main()
