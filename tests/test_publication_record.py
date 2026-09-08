from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_RECORD = ROOT / "research" / "publication-record.json"
CLAIM_RECORD = ROOT / "research" / "claim.json"
PUBLICATION_AUDIT = ROOT / "research" / "tag-release-publication-audit.json"
FINAL_EVIDENCE = ROOT / "research" / "tag-recovery-final-evidence.json"
GITHUB_RELEASE_SNAPSHOT = (
    ROOT / "research" / "github-release-api-snapshot.json"
)
GITHUB_RULESET_SNAPSHOT = (
    ROOT / "research" / "github-ruleset-api-snapshot.json"
)
ZENODO_RECORD_SNAPSHOT = (
    ROOT / "research" / "zenodo-record-api-snapshot.json"
)
README = ROOT / "README.md"
PUBLICATION = ROOT / "PUBLICATION.md"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")
EXPECTED_ASSETS = {
    "SHA256SUMS",
    "ramsey-number-5-5-paper-v0.1.0.pdf",
    "ramsey-number-5-5-source-v0.1.0.tar.gz",
}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PublicationRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = load_json(PUBLICATION_RECORD)

    def test_publication_identity_is_complete(self) -> None:
        self.assertEqual(1, self.record["schema_version"])
        self.assertEqual("published", self.record["status"])
        release = self.record["github_release"]
        zenodo = self.record["zenodo"]
        self.assertIsInstance(release, dict)
        self.assertIsInstance(zenodo, dict)
        self.assertTrue(release["immutable"])
        self.assertEqual("v0.1.0", release["tag"])
        self.assertEqual(385004910, release["release_id"])
        self.assertEqual("published", zenodo["status"])
        self.assertEqual("10.5281/zenodo.22653273", zenodo["version_doi"])
        self.assertEqual("10.5281/zenodo.22653272", zenodo["concept_doi"])

    def test_github_and_zenodo_assets_match(self) -> None:
        github_entries = self.record["github_release"]["assets"]
        zenodo_entries = self.record["zenodo"]["files"]
        self.assertEqual(3, len(github_entries))
        self.assertEqual(3, len(zenodo_entries))
        github_assets = {}
        for entry in github_entries:
            self.assertNotIn(entry["name"], github_assets)
            self.assertRegex(entry["sha256"], SHA256_RE)
            self.assertIsInstance(entry["id"], int)
            github_assets[entry["name"]] = (
                entry["size"],
                entry["sha256"],
            )
        zenodo_assets = {}
        for entry in zenodo_entries:
            self.assertNotIn(entry["name"], zenodo_assets)
            self.assertRegex(entry["sha256"], SHA256_RE)
            self.assertRegex(entry["md5"], MD5_RE)
            self.assertIsInstance(entry["id"], str)
            zenodo_assets[entry["name"]] = (
                entry["size"],
                entry["sha256"],
            )
        self.assertEqual(EXPECTED_ASSETS, set(github_assets))
        self.assertEqual(EXPECTED_ASSETS, set(zenodo_assets))
        self.assertEqual(github_assets, zenodo_assets)
        verification = self.record["independent_public_verification"]
        self.assertTrue(verification["github_assets_download_verified"])
        self.assertTrue(verification["zenodo_assets_download_verified"])
        self.assertTrue(
            verification["github_and_zenodo_assets_byte_identical"]
        )

    def test_retained_audit_hashes_are_bound(self) -> None:
        audit = self.record["publication_audit"]
        recovery = self.record["protected_tag_verification"]
        self.assertEqual(audit["sha256"], sha256(PUBLICATION_AUDIT))
        self.assertEqual(
            recovery["final_evidence_sha256"],
            sha256(FINAL_EVIDENCE),
        )
        audit_record = load_json(PUBLICATION_AUDIT)
        final_evidence = load_json(FINAL_EVIDENCE)
        self.assertEqual("pass", audit_record["result"])
        self.assertEqual("verified", final_evidence["result"])
        release = self.record["github_release"]
        self.assertEqual(release["tag"], audit_record["release"]["tag"])
        self.assertEqual(
            release["tag_object_sha"],
            audit_record["release"]["tag_object_sha"],
        )
        self.assertEqual(
            release["commit_sha"],
            audit_record["release"]["commit_sha"],
        )
        self.assertEqual(
            recovery["run_id"],
            audit_record["recovery_workflow"]["run_id"],
        )
        self.assertEqual(
            recovery["artifact_digest"],
            audit_record["recovery_workflow"]["artifact_digest"],
        )
        self.assertEqual(audit["ruleset_id"], audit_record["ruleset"]["id"])
        self.assertEqual([], audit_record["ruleset"]["bypass_actors"])
        self.assertEqual(
            release["commit_sha"],
            final_evidence["release_commit"],
        )
        self.assertEqual(release["tag"], final_evidence["release_tag"])
        self.assertEqual(
            release["tag_object_sha"],
            final_evidence["release_tag_object_sha"],
        )
        self.assertEqual(
            recovery["run_id"],
            int(final_evidence["recovery_workflow"]["run_id"]),
        )
        self.assertEqual(
            recovery["controller_commit"],
            final_evidence["recovery_workflow"]["sha"],
        )
        evidence_assets = final_evidence["release_assets"]
        recorded_assets = {
            entry["name"]: entry["sha256"]
            for entry in release["assets"]
        }
        self.assertEqual(recorded_assets, evidence_assets)

    def test_retained_api_snapshots_are_bound_and_consistent(self) -> None:
        verification = self.record["independent_public_verification"]
        snapshots = (
            (
                "github_release_api_snapshot",
                GITHUB_RELEASE_SNAPSHOT,
            ),
            (
                "github_ruleset_api_snapshot",
                GITHUB_RULESET_SNAPSHOT,
            ),
            (
                "zenodo_public_api_snapshot",
                ZENODO_RECORD_SNAPSHOT,
            ),
        )
        for key, path in snapshots:
            binding = verification[key]
            self.assertEqual(path.relative_to(ROOT).as_posix(), binding["path"])
            self.assertEqual(sha256(path), binding["sha256"])

        release = self.record["github_release"]
        release_snapshot = load_json(GITHUB_RELEASE_SNAPSHOT)["release"]
        self.assertEqual(
            1,
            load_json(GITHUB_RELEASE_SNAPSHOT)["schema_version"],
        )
        self.assertEqual(release["release_id"], release_snapshot["id"])
        self.assertEqual(release["tag"], release_snapshot["tag_name"])
        self.assertEqual(release["immutable"], release_snapshot["immutable"])
        self.assertEqual(release["draft"], release_snapshot["draft"])
        self.assertEqual(
            release["prerelease"],
            release_snapshot["prerelease"],
        )
        self.assertEqual(
            release["published_at"],
            release_snapshot["published_at"],
        )
        self.assertEqual(3, len(release_snapshot["assets"]))
        self.assertEqual(
            3,
            len({entry["name"] for entry in release_snapshot["assets"]}),
        )
        snapshot_assets = {
            entry["name"]: (
                entry["id"],
                entry["size"],
                entry["digest"].removeprefix("sha256:"),
            )
            for entry in release_snapshot["assets"]
        }
        recorded_assets = {
            entry["name"]: (
                entry["id"],
                entry["size"],
                entry["sha256"],
            )
            for entry in release["assets"]
        }
        self.assertEqual(recorded_assets, snapshot_assets)

        audit = self.record["publication_audit"]
        ruleset_snapshot = load_json(GITHUB_RULESET_SNAPSHOT)
        self.assertEqual(1, ruleset_snapshot["schema_version"])
        ruleset = ruleset_snapshot["ruleset"]
        self.assertEqual(audit["ruleset_id"], ruleset["id"])
        self.assertEqual("Protect version tags", ruleset["name"])
        self.assertEqual("tag", ruleset["target"])
        self.assertEqual("active", ruleset["enforcement"])
        self.assertEqual(
            "ruturajr-raval/ramsey-number-5-5",
            ruleset["source"],
        )
        self.assertEqual(
            {
                "exclude": [],
                "include": ["refs/tags/v*"],
            },
            ruleset["conditions"]["ref_name"],
        )
        self.assertEqual(
            {"update", "deletion"},
            {entry["type"] for entry in ruleset["rules"]},
        )
        self.assertEqual([], ruleset["bypass_actors"])
        self.assertEqual(
            audit["current_user_can_bypass"],
            ruleset["current_user_can_bypass"],
        )

        zenodo = self.record["zenodo"]
        zenodo_snapshot_record = load_json(ZENODO_RECORD_SNAPSHOT)
        self.assertEqual(1, zenodo_snapshot_record["schema_version"])
        zenodo_snapshot = zenodo_snapshot_record["record"]
        self.assertEqual(zenodo["record_id"], zenodo_snapshot["id"])
        self.assertEqual(zenodo["version_doi"], zenodo_snapshot["doi"])
        self.assertEqual(zenodo["concept_doi"], zenodo_snapshot["conceptdoi"])
        self.assertEqual(zenodo["status"], zenodo_snapshot["status"])
        self.assertEqual(
            "Prime-Order Automorphism Exclusions for Ramsey (5,5;43) Graphs",
            zenodo_snapshot["metadata"]["title"],
        )
        self.assertEqual(
            zenodo["publication_date"],
            zenodo_snapshot["metadata"]["publication_date"],
        )
        self.assertEqual(
            zenodo["version"],
            zenodo_snapshot["metadata"]["version"],
        )
        self.assertEqual(
            "Raval, Ruturaj R",
            zenodo_snapshot["metadata"]["creators"][0]["name"],
        )
        self.assertEqual(
            self.record["author"]["affiliation"],
            zenodo_snapshot["metadata"]["creators"][0]["affiliation"],
        )
        self.assertEqual(
            self.record["author"]["orcid"],
            zenodo_snapshot["metadata"]["creators"][0]["orcid"],
        )
        self.assertEqual(
            "mit-license",
            zenodo_snapshot["metadata"]["license"]["id"],
        )
        self.assertEqual(
            zenodo["resource_type"],
            zenodo_snapshot["metadata"]["resource_type"]["type"],
        )
        self.assertEqual(
            zenodo["related_release"],
            zenodo_snapshot["metadata"]["related_identifiers"][0][
                "identifier"
            ],
        )
        self.assertEqual(3, len(zenodo_snapshot["files"]))
        self.assertEqual(
            3,
            len({entry["key"] for entry in zenodo_snapshot["files"]}),
        )
        snapshot_files = {
            entry["key"]: (
                entry["id"],
                entry["size"],
                entry["checksum"].removeprefix("md5:"),
            )
            for entry in zenodo_snapshot["files"]
        }
        recorded_files = {
            entry["name"]: (
                entry["id"],
                entry["size"],
                entry["md5"],
            )
            for entry in zenodo["files"]
        }
        self.assertEqual(recorded_files, snapshot_files)

    def test_claim_points_to_published_record(self) -> None:
        claim = load_json(CLAIM_RECORD)
        self.assertEqual("published scoped theorem", claim["status"])
        release = claim["release"]
        self.assertEqual(
            "research/publication-record.json",
            release["publication_record"],
        )
        self.assertEqual(
            self.record["github_release"]["commit_sha"],
            release["protected_release_commit"],
        )

    def test_public_documents_use_canonical_release_identity(self) -> None:
        readme = README.read_text(encoding="utf-8")
        publication = PUBLICATION.read_text(encoding="utf-8")
        self.assertIn(
            "| Release | `v0.1.0` |",
            readme,
        )
        self.assertIn(
            "`efbd19f319e9131fd550ec149bd1e5b72a82efee`",
            readme,
        )
        self.assertIn("`RELEASE_NOTES.md`", readme)
        for label in (
            "Audited release commit",
            "Tagged release",
            "Archive status",
        ):
            self.assertIn(f"| {label} |", publication)
        self.assertIn(
            "## Remaining Work And Next Acceptance Gate",
            publication,
        )


if __name__ == "__main__":
    unittest.main()
