#!/usr/bin/env python3
"""Split one compressed c8 proof into deterministic release-sized parts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path


DEFAULT_PART_BYTES = 49_000_000
ROOT = Path(__file__).resolve().parents[1]


def open_regular_no_follow(path: Path):
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("safe proof splitting requires O_NOFOLLOW")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    details = os.fstat(descriptor)
    if not stat.S_ISREG(details.st_mode):
        os.close(descriptor)
        raise ValueError(f"not a regular file: {path}")
    return os.fdopen(descriptor, "rb"), details


def require_project_parent(path: Path) -> None:
    try:
        path.parent.resolve().relative_to(ROOT)
    except ValueError as error:
        raise ValueError(f"path escapes project: {path}") from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--compaction-record", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--output-record", type=Path, required=True)
    parser.add_argument(
        "--part-bytes",
        type=int,
        default=DEFAULT_PART_BYTES,
    )
    args = parser.parse_args()
    proof_path = args.proof.absolute()
    compaction_path = args.compaction_record.absolute()
    output_directory = args.output_directory.absolute()
    output_record = args.output_record.absolute()

    if args.part_bytes <= 0 or args.part_bytes >= 100_000_000:
        raise ValueError("part size must be between 1 and 99,999,999 bytes")
    for path in (proof_path, compaction_path):
        require_project_parent(path)
    require_project_parent(output_directory)
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    if output_record.parent != output_directory:
        raise ValueError("output record must be inside the output directory")
    if output_directory.exists() or output_directory.is_symlink():
        raise FileExistsError(output_directory)

    compaction_stream, _ = open_regular_no_follow(compaction_path)
    with compaction_stream:
        record = json.loads(
            compaction_stream.read().decode("ascii")
        )
    compacted = record.get("compacted_proof")
    if not isinstance(compacted, dict):
        raise AssertionError("compacted proof record is missing")
    if compacted.get("path") != proof_path.name:
        raise AssertionError("compacted proof path mismatch")
    if "parts" in compacted:
        raise AssertionError("compacted proof is already multipart")
    expected_bytes = compacted.get("compressed_bytes")
    expected_sha256 = compacted.get("compressed_sha256")
    if not isinstance(expected_bytes, int):
        raise AssertionError("compacted proof byte count is invalid")
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha256)
    ):
        raise AssertionError("compacted proof hash is invalid")
    if expected_bytes <= args.part_bytes:
        raise AssertionError("proof does not require multipart storage")

    staging_directory = Path(
        tempfile.mkdtemp(
            dir=output_directory.parent,
            prefix=f".{output_directory.name}.tmp-",
        )
    )
    try:
        part_records: list[dict[str, object]] = []
        combined = hashlib.sha256()
        total_bytes = 0
        source, source_details = open_regular_no_follow(proof_path)
        with source:
            if source_details.st_size != expected_bytes:
                raise AssertionError("compacted proof size mismatch")
            index = 0
            while True:
                payload = source.read(args.part_bytes)
                if not payload:
                    break
                name = f"{proof_path.name}.part-{index:03d}"
                path = staging_directory / name
                with path.open("xb") as handle:
                    handle.write(payload)
                part_records.append(
                    {
                        "bytes": len(payload),
                        "path": name,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
                combined.update(payload)
                total_bytes += len(payload)
                index += 1

        if len(part_records) < 2:
            raise AssertionError("split produced fewer than two parts")
        if total_bytes != expected_bytes:
            raise AssertionError("multipart byte count mismatch")
        if combined.hexdigest() != expected_sha256:
            raise AssertionError("multipart combined hash mismatch")

        compacted["parts"] = part_records
        text = json.dumps(record, indent=2, sort_keys=True) + "\n"
        staged_record = staging_directory / output_record.name
        with staged_record.open(
            "x",
            encoding="ascii",
            newline="\n",
        ) as handle:
            handle.write(text)
        staging_directory.replace(output_directory)
    except BaseException:
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise
    print(text, end="")


if __name__ == "__main__":
    main()
