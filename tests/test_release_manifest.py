#!/usr/bin/env python3
"""Regression tests for release-manifest package boundaries."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "release_manifest.py"
SPEC = importlib.util.spec_from_file_location("release_manifest", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load release_manifest module")
release_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_manifest)


class PackageBoundaryTests(unittest.TestCase):
    def test_local_toolchains_and_build_artifacts_are_excluded(self) -> None:
        paths = {
            path.relative_to(ROOT).as_posix()
            for path in release_manifest.package_files()
        }

        self.assertFalse(any(path.startswith(".tools/") for path in paths))
        self.assertFalse(
            any(path.startswith(".search-sanitize-bin.dSYM/") for path in paths)
        )
        self.assertFalse(any("/target/" in "/{}/".format(path) for path in paths))
        self.assertFalse(any(path.startswith("build/") for path in paths))
        self.assertFalse(any(path.endswith(".tmp") for path in paths))

    def test_release_sources_remain_included(self) -> None:
        paths = {
            path.relative_to(ROOT).as_posix()
            for path in release_manifest.package_files()
        }

        self.assertIn("README.md", paths)
        self.assertIn(".github/workflows/ci.yml", paths)
        self.assertIn(
            "evidence/orbit-p3-c6/certificate-manifest.json",
            paths,
        )
        self.assertIn(
            "evidence/orbit-p3-c6/p3-c6-k0.drat.xz",
            paths,
        )
        self.assertIn("paper/main.tex", paths)
        self.assertIn("src/check_small_support.py", paths)
        self.assertIn("src/orbit_cnf.py", paths)
        self.assertIn("tools/replay_proofs.py", paths)
        self.assertIn("tools/verify_branch_artifacts.py", paths)
        self.assertIn("tools/verify_certificates.py", paths)
        self.assertIn("tools/release_manifest.py", paths)

    def test_manifest_contains_only_tracked_files(self) -> None:
        tracked = set(
            subprocess.run(
                ["git", "ls-files"],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.splitlines()
        )
        packaged = {
            path.relative_to(ROOT).as_posix()
            for path in release_manifest.package_files()
        }
        self.assertTrue(packaged <= tracked)

    def test_untracked_local_file_is_not_packaged(self) -> None:
        fixture = ROOT / "local-review.tmp"
        fixture.write_text("local only\n", encoding="ascii")
        try:
            packaged = {
                path.relative_to(ROOT).as_posix()
                for path in release_manifest.package_files()
            }
            self.assertNotIn(fixture.name, packaged)
        finally:
            fixture.unlink()

    def test_manifest_check_works_without_git_metadata(self) -> None:
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=build,
            prefix="archive-check-",
        ) as temporary:
            archive = Path(temporary)
            payload = archive / "README.md"
            payload.write_text("archive fixture\n", encoding="ascii")
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
            manifest = archive / "release-manifest.sha256"
            manifest.write_text(
                f"{digest}  README.md\n",
                encoding="ascii",
            )

            original_root = release_manifest.ROOT
            original_manifest = release_manifest.MANIFEST
            release_manifest.ROOT = archive
            release_manifest.MANIFEST = manifest
            try:
                self.assertEqual(0, release_manifest.check_manifest())
            finally:
                release_manifest.ROOT = original_root
                release_manifest.MANIFEST = original_manifest


if __name__ == "__main__":
    unittest.main()
