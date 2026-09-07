from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from record_paper_build import build_record


ROOT = Path(__file__).resolve().parents[1]


class PaperBuildRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        build = ROOT / "build"
        build.mkdir(exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=build,
            prefix="paper-build-test-",
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "main.tex"
        self.pdf = self.root / "main.pdf"
        self.log = self.root / "main.log"
        self.source.write_text("\\documentclass{article}\n", encoding="ascii")
        self.pdf.write_bytes(b"%PDF-1.4\nfixture\n")

    def test_pdf_log_byte_count_is_enforced(self) -> None:
        self.log.write_text(
            "Output written on main.pdf (1 page, 999 bytes).\n",
            encoding="ascii",
        )
        with self.assertRaisesRegex(AssertionError, "byte count changed"):
            build_record(self.source, self.pdf, self.log)

    def test_tectonic_xdv_record_binds_pages_and_final_pdf(self) -> None:
        self.log.write_text(
            "Output written on main.xdv (9 pages, 45920 bytes).\n",
            encoding="ascii",
        )
        record = build_record(self.source, self.pdf, self.log)

        self.assertEqual(9, record["pdf"]["pages"])
        self.assertEqual("main.xdv", record["latex_log"]["reported_output"])
        self.assertEqual(45920, record["latex_log"]["reported_bytes"])


if __name__ == "__main__":
    unittest.main()
