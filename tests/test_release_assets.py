from __future__ import annotations

import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build_release_assets as release_assets


class ReleaseAssetTests(unittest.TestCase):
    def test_asset_names_include_version(self) -> None:
        names = release_assets.asset_names("1.2.3")
        self.assertEqual(
            "ramsey-number-5-5-paper-v1.2.3.pdf",
            names["paper"],
        )
        self.assertEqual(
            "ramsey-number-5-5-source-v1.2.3.tar.gz",
            names["source"],
        )
        self.assertEqual(
            "paper/ramsey-number-5-5-paper-v1.2.3.pdf",
            release_assets.committed_paper_relative("1.2.3"),
        )

    def test_checksum_writer_is_sorted_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            directory = Path(directory_text)
            names = {"second": "z.bin", "first": "a.bin"}
            (directory / "z.bin").write_bytes(b"z")
            (directory / "a.bin").write_bytes(b"a")
            release_assets.write_checksums(directory, names)
            lines = (directory / "SHA256SUMS").read_text(
                encoding="ascii"
            ).splitlines()
            self.assertEqual(
                [
                    f"{hashlib.sha256(b'a').hexdigest()}  a.bin",
                    f"{hashlib.sha256(b'z').hexdigest()}  z.bin",
                ],
                lines,
            )

    def test_checksum_parser_rejects_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            path = Path(directory_text) / "SHA256SUMS"
            digest = "0" * 64
            path.write_text(
                f"{digest}  asset\n{digest}  asset\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                release_assets.read_checksums(path)

    def test_project_version_matches_candidate_metadata(self) -> None:
        self.assertEqual("0.1.0", release_assets.project_version("HEAD"))

    def test_source_archive_is_deterministic_and_ref_bound(self) -> None:
        entries = [
            release_assets.TreeEntry("README.md", 0o644, "readme"),
            release_assets.TreeEntry("tools/run", 0o755, "tool"),
        ]
        payloads = {"readme": b"readme\n", "tool": b"#!/bin/sh\n"}
        with tempfile.TemporaryDirectory() as directory_text:
            directory = Path(directory_text)
            first = directory / "first.tar.gz"
            second = directory / "second.tar.gz"
            with (
                mock.patch.object(
                    release_assets,
                    "resolve_ref",
                    return_value="f" * 40,
                ),
                mock.patch.object(
                    release_assets,
                    "tree_entries",
                    return_value=entries,
                ),
                mock.patch.object(
                    release_assets,
                    "blob_bytes",
                    side_effect=lambda object_id: payloads[object_id],
                ),
            ):
                release_assets.build_source_archive(
                    first,
                    "0.1.0",
                    "HEAD",
                )
                release_assets.build_source_archive(
                    second,
                    "0.1.0",
                    "HEAD",
                )
                self.assertEqual(
                    release_assets.sha256(first),
                    release_assets.sha256(second),
                )
                release_assets.verify_source_archive(
                    first,
                    "0.1.0",
                    "HEAD",
                )

    def test_source_archive_rejects_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            path = Path(directory_text) / "duplicate.tar.gz"
            name = "ramsey-number-5-5-v0.1.0/duplicate"
            with tarfile.open(path, mode="w:gz") as archive:
                for _ in range(2):
                    info = tarfile.TarInfo(name)
                    info.size = 1
                    archive.addfile(info, io.BytesIO(b"x"))
            with (
                mock.patch.object(
                    release_assets,
                    "resolve_ref",
                    return_value="f" * 40,
                ),
                mock.patch.object(
                    release_assets,
                    "tree_entries",
                    return_value=[],
                ),
            ):
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    release_assets.verify_source_archive(
                        path,
                        "0.1.0",
                        "HEAD",
                    )

    def test_release_paper_must_match_inspected_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            directory = Path(directory_text)
            release_paper = directory / "release.pdf"
            inspected_paper = directory / "inspected.pdf"
            release_paper.write_bytes(b"%PDF-release")
            inspected_paper.write_bytes(b"%PDF-inspected")
            with self.assertRaisesRegex(ValueError, "does not match"):
                release_assets.verify_paper_binding(
                    release_paper,
                    inspected_paper,
                )


if __name__ == "__main__":
    unittest.main()
