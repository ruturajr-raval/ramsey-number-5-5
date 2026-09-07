#!/usr/bin/env python3
"""Resolve and stream single-file or multipart compressed c8 proofs."""

from __future__ import annotations

import hashlib
import io
import lzma
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_PROOF_FIELDS = {
    "path",
    "role",
    "compressed_bytes",
    "compressed_sha256",
    "decompressed_bytes",
    "decompressed_sha256",
}
RUN_PROOF_FIELDS = {
    "path",
    "compressed_bytes",
    "compressed_sha256",
}


@dataclass(frozen=True)
class CompressedProofArtifact:
    paths: tuple[Path, ...]
    compressed_bytes: int
    compressed_sha256: str
    parts: tuple[dict[str, object], ...] | None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_regular_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(path)


def validate_source_proof_record(
    record: dict[str, object],
    run_record: object,
    extraction_log: str,
    label: str,
) -> None:
    if set(record) != SOURCE_PROOF_FIELDS:
        raise AssertionError(f"{label} source proof fields are incomplete")
    if not isinstance(run_record, dict) or set(run_record) != RUN_PROOF_FIELDS:
        raise AssertionError(f"{label} solver proof fields are incomplete")
    if record.get("role") != "solver-output":
        raise AssertionError(f"{label} source proof role mismatch")

    path = record.get("path")
    if (
        not isinstance(path, str)
        or not path
        or Path(path).name != path
    ):
        raise AssertionError(f"{label} source proof path is invalid")
    for field in RUN_PROOF_FIELDS:
        if record.get(field) != run_record.get(field):
            raise AssertionError(
                f"{label} source proof mismatch: {field}"
            )

    for field in ("compressed_bytes", "decompressed_bytes"):
        value = record.get(field)
        if type(value) is not int or value <= 0:
            raise AssertionError(
                f"{label} source proof {field} is invalid"
            )
    for field in ("compressed_sha256", "decompressed_sha256"):
        value = record.get(field)
        if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
            raise AssertionError(
                f"{label} source proof {field} is invalid"
            )

    checker_counts = {
        int(value)
        for value in re.findall(
            r"read ([0-9]+) bytes from proof file",
            extraction_log,
        )
    }
    if checker_counts != {record["decompressed_bytes"]}:
        raise AssertionError(
            f"{label} source proof decompressed byte count mismatch"
        )


def resolve_compressed_proof(
    directory: Path,
    logical_name: str,
    record: dict[str, object],
) -> CompressedProofArtifact:
    if record.get("path") != logical_name:
        raise AssertionError("compressed proof logical path mismatch")
    observed_part_names = tuple(
        sorted(
            path.name
            for path in directory.glob(f"{logical_name}.part-*")
        )
    )
    raw_parts = record.get("parts")
    if raw_parts is None:
        if observed_part_names:
            raise AssertionError(
                "single-file proof has unreferenced multipart artifacts"
            )
        path = directory / logical_name
        require_regular_file(path)
        paths = (path,)
        part_records = None
    else:
        if not isinstance(raw_parts, list) or len(raw_parts) < 2:
            raise AssertionError(
                "multipart proof must contain at least two parts"
            )
        if (directory / logical_name).exists():
            raise AssertionError(
                "multipart proof has an ambiguous single-file artifact"
            )
        paths_list: list[Path] = []
        records_list: list[dict[str, object]] = []
        for index, raw_part in enumerate(raw_parts):
            if not isinstance(raw_part, dict):
                raise AssertionError("multipart proof part is not an object")
            expected_name = f"{logical_name}.part-{index:03d}"
            if raw_part.get("path") != expected_name:
                raise AssertionError("multipart proof part order mismatch")
            path = directory / expected_name
            require_regular_file(path)
            expected_part = {
                "bytes": path.stat().st_size,
                "path": expected_name,
                "sha256": file_sha256(path),
            }
            if raw_part != expected_part:
                raise AssertionError(
                    f"multipart proof part metadata mismatch: {expected_name}"
                )
            paths_list.append(path)
            records_list.append(expected_part)
        expected_part_names = tuple(
            record["path"]
            for record in records_list
        )
        if observed_part_names != expected_part_names:
            raise AssertionError(
                "multipart proof has unreferenced or missing parts"
            )
        paths = tuple(paths_list)
        part_records = tuple(records_list)

    digest = hashlib.sha256()
    byte_count = 0
    for path in paths:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                byte_count += len(block)
                digest.update(block)
    return CompressedProofArtifact(
        paths=paths,
        compressed_bytes=byte_count,
        compressed_sha256=digest.hexdigest(),
        parts=part_records,
    )


class ConcatenatedReader(io.RawIOBase):
    """Present ordered proof parts as one non-seekable byte stream."""

    def __init__(self, paths: tuple[Path, ...]) -> None:
        super().__init__()
        self._paths = iter(paths)
        self._current: BinaryIO | None = None

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray | memoryview) -> int:
        view = memoryview(buffer)
        total = 0
        while total < len(view):
            if self._current is None:
                try:
                    self._current = next(self._paths).open("rb")
                except StopIteration:
                    break
            count = self._current.readinto(view[total:])
            if count:
                total += count
                continue
            self._current.close()
            self._current = None
        return total

    def close(self) -> None:
        if self._current is not None:
            self._current.close()
            self._current = None
        super().close()


@contextmanager
def open_decompressed_proof(
    artifact: CompressedProofArtifact,
) -> Iterator[lzma.LZMAFile]:
    raw = ConcatenatedReader(artifact.paths)
    buffered = io.BufferedReader(raw, buffer_size=1024 * 1024)
    archive = lzma.LZMAFile(buffered, "rb")
    try:
        yield archive
    finally:
        archive.close()


def decompressed_details(
    artifact: CompressedProofArtifact,
) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    with open_decompressed_proof(artifact) as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            byte_count += len(block)
            digest.update(block)
    return byte_count, digest.hexdigest()
