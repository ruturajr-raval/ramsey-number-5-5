from __future__ import annotations

import json
import lzma
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from replay_proofs import (
    CLAIM,
    CLAIM_BOUNDARY,
    build_fresh_checker,
    file_sha256,
    replay_branch,
    require_clean_source_tree,
    source_commit,
    validate_certificate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class C6ReplayProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=build,
            prefix="c6-replay-test-",
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    @staticmethod
    def write_json(path: Path, value: dict[str, object]) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )

    def make_source_repository(self) -> Path:
        source = self.root / "checker-source"
        source.mkdir()
        (source / "drat-trim.c").write_text(
            "#include <stdio.h>\n"
            "int main(void) {\n"
            "  while (getchar() != EOF) {}\n"
            '  puts("s VERIFIED");\n'
            "  return 0;\n"
            "}\n",
            encoding="ascii",
        )
        subprocess.run(["git", "init", "-q"], cwd=source, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Test Author"],
            cwd=source,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test"],
            cwd=source,
            check=True,
        )
        subprocess.run(["git", "add", "drat-trim.c"], cwd=source, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "Add checker"],
            cwd=source,
            check=True,
        )
        return source

    def test_clean_source_commit_and_dirty_source_rejection(self) -> None:
        source = self.make_source_repository()
        self.assertEqual(40, len(source_commit(source)))
        require_clean_source_tree(source)

        (source / "drat-trim.c").write_text(
            "int main(void) { return 1; }\n",
            encoding="ascii",
        )
        with self.assertRaisesRegex(AssertionError, "tracked source changes"):
            require_clean_source_tree(source)

    @unittest.skipUnless(shutil.which("cc"), "C compiler is unavailable")
    def test_fresh_checker_build_records_source_and_log_hashes(self) -> None:
        source = self.make_source_repository()
        logs = self.root / "logs"
        logs.mkdir()
        checker, record = build_fresh_checker(source, logs, "cc")

        self.assertTrue(checker.is_file())
        self.assertEqual("fresh-source-build", record["mode"])
        self.assertEqual(
            file_sha256(source / "drat-trim.c"),
            record["source_sha256"],
        )
        self.assertEqual(
            file_sha256(logs / str(record["log"])),
            record["log_sha256"],
        )

    def make_replay_fixture(
        self,
    ) -> tuple[Path, list[dict[str, object]]]:
        formulas = self.root / "formulas"
        evidence = self.root / "evidence"
        logs = self.root / "logs"
        for directory in (formulas, evidence, logs):
            directory.mkdir(exist_ok=True)
        checker = self.root / "checker"
        checker.write_text(
            "#!/bin/sh\ncat >/dev/null\nprintf 's VERIFIED\\n'\n",
            encoding="ascii",
        )
        checker.chmod(0o755)

        branches = []
        for branch in range(4):
            stem = f"p3-c6-k{branch}"
            cnf = formulas / f"{stem}.cnf"
            cnf.write_text("p cnf 1 1\n1 0\n", encoding="ascii")
            self.write_json(
                formulas / f"{stem}.json",
                {
                    "root_adjacent_cycles": branch,
                    "sha256": file_sha256(cnf),
                    "variables": 1,
                    "clauses": 1,
                },
            )
            (evidence / f"{stem}.drat.xz").write_bytes(
                lzma.compress(f"proof {branch}\n".encode("ascii"))
            )
            branches.append(
                replay_branch(
                    checker,
                    formulas,
                    evidence,
                    logs,
                    branch,
                )
            )

        coverage = evidence / "branch-coverage.json"
        coverage.write_text('{"coverage_complete": true}\n', encoding="ascii")
        audit = evidence / "cnf-audit.json"
        audit.write_text('{"audit_passed": true}\n', encoding="ascii")
        manifest = evidence / "certificate-manifest.json"
        self.write_json(
            manifest,
            {
                "claim": CLAIM,
                "claim_boundary": CLAIM_BOUNDARY,
                "coverage": {
                    "artifact": coverage.name,
                    "sha256": file_sha256(coverage),
                },
                "cnf_audit": {
                    "artifact": audit.name,
                    "sha256": file_sha256(audit),
                },
                "branches": [
                    {
                        "branch": record["branch"],
                        "cnf": record["cnf"],
                        "proof": record["proof"],
                    }
                    for record in branches
                ],
                "verification_passed": True,
            },
        )
        return manifest, branches

    def test_complete_four_branch_manifest_binding_is_accepted(self) -> None:
        manifest, branches = self.make_replay_fixture()
        self.assertEqual(
            file_sha256(manifest),
            validate_certificate_manifest(manifest, branches),
        )

    def test_manifest_proof_mismatch_is_rejected(self) -> None:
        manifest, branches = self.make_replay_fixture()
        value = json.loads(manifest.read_text(encoding="ascii"))
        value["branches"][0]["proof"]["compressed_sha256"] = "0" * 64
        self.write_json(manifest, value)

        with self.assertRaisesRegex(AssertionError, "proof mismatch"):
            validate_certificate_manifest(manifest, branches)

    def test_incomplete_branch_inventory_is_rejected(self) -> None:
        manifest, branches = self.make_replay_fixture()
        with self.assertRaisesRegex(AssertionError, "exactly four branches"):
            validate_certificate_manifest(manifest, branches[:-1])


if __name__ == "__main__":
    unittest.main()
