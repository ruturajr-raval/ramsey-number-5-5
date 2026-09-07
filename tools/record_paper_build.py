#!/usr/bin/env python3
"""Record hashes and page metadata for a freshly built technical report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


OUTPUT_RE = re.compile(
    r"Output written on ([^ ]+) \(([0-9]+) pages?, ([0-9]+) bytes\)\."
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_record(
    source: Path,
    pdf: Path,
    log: Path,
) -> dict[str, object]:
    for path in (source, pdf, log):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not pdf.read_bytes()[:5] == b"%PDF-":
        raise AssertionError("technical report is not a PDF")
    matches = OUTPUT_RE.findall(log.read_text(encoding="ascii"))
    if not matches:
        raise AssertionError("LaTeX log has no final output record")
    reported_output, page_count_text, logged_bytes_text = matches[-1]
    page_count = int(page_count_text)
    logged_bytes = int(logged_bytes_text)
    if page_count <= 0:
        raise AssertionError("technical report has no pages")
    if reported_output.endswith(".pdf") and logged_bytes != pdf.stat().st_size:
        raise AssertionError("LaTeX log PDF byte count changed")
    if pdf.stat().st_mtime_ns < source.stat().st_mtime_ns:
        raise AssertionError("technical report predates its source")

    return {
        "schema_version": 1,
        "source": {
            "path": source.as_posix(),
            "sha256": file_sha256(source),
        },
        "pdf": {
            "path": pdf.as_posix(),
            "bytes": pdf.stat().st_size,
            "sha256": file_sha256(pdf),
            "pages": page_count,
        },
        "latex_log": {
            "path": log.as_posix(),
            "sha256": file_sha256(log),
            "reported_output": reported_output,
            "reported_bytes": logged_bytes,
            "reported_pages": page_count,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    record = build_record(args.source, args.pdf, args.log)
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
