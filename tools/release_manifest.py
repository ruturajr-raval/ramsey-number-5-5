#!/usr/bin/env python3
"""Write or verify the deterministic project checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release-manifest.sha256"
MAX_PACKAGE_FILE_BYTES = 100_000_000
EXCLUDED_PARTS = {
    ".git",
    ".search-sanitize-bin.dSYM",
    ".tools",
    "build",
    "dist",
    "target",
    "__pycache__",
}
EXCLUDED_NAMES = {
    ".DS_Store",
    ".search-test-bin",
    MANIFEST.name,
}
LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")


def validate_package_file(path: Path, relative: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(
            "tracked package path is not a regular file: "
            + relative.as_posix()
        )
    size = path.stat().st_size
    if size > MAX_PACKAGE_FILE_BYTES:
        raise ValueError(
            "tracked package file exceeds {} bytes: {} ({})".format(
                MAX_PACKAGE_FILE_BYTES,
                relative.as_posix(),
                size,
            )
        )


def package_files() -> Iterable[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            "git ls-files failed: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )

    relative_paths = sorted(
        Path(raw.decode("utf-8"))
        for raw in completed.stdout.split(b"\0")
        if raw
    )
    for relative in relative_paths:
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.name in EXCLUDED_NAMES:
            continue
        path = ROOT / relative
        validate_package_file(path, relative)
        yield path


def archive_files() -> Iterable[Path]:
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.name in EXCLUDED_NAMES:
            continue
        if path.is_dir():
            continue
        validate_package_file(path, relative)
        yield path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def tracked_entries() -> Dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): digest(path)
        for path in package_files()
    }


def write_manifest() -> int:
    entries = tracked_entries()
    text = "".join(
        "{}  {}\n".format(entries[path], path)
        for path in sorted(entries)
    )
    with MANIFEST.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(text)
    print("wrote {} entries".format(len(entries)))
    return 0


def read_manifest() -> Dict[str, str]:
    if not MANIFEST.is_file():
        raise ValueError("release-manifest.sha256 is missing")
    entries: Dict[str, str] = {}
    for line_number, raw_line in enumerate(
        MANIFEST.read_text(encoding="ascii").splitlines(), start=1
    ):
        match = LINE_RE.fullmatch(raw_line)
        if match is None:
            raise ValueError(
                "invalid manifest line {}".format(line_number)
            )
        expected, relative = match.groups()
        if relative in entries:
            raise ValueError("duplicate manifest path {}".format(relative))
        path = ROOT / relative
        resolved = path.resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            raise ValueError("manifest path escapes project: {}".format(relative))
        validate_package_file(path, Path(relative))
        entries[relative] = expected
    return entries


def check_manifest() -> int:
    expected = read_manifest()
    observed = (
        tracked_entries()
        if (ROOT / ".git").is_dir()
        else {
            path.relative_to(ROOT).as_posix(): digest(path)
            for path in archive_files()
        }
    )
    errors = []
    for relative in sorted(set(expected) & set(observed)):
        if expected[relative] != observed[relative]:
            errors.append("hash mismatch: {}".format(relative))

    missing = sorted(set(observed) - set(expected))
    stale = sorted(set(expected) - set(observed))
    if missing:
        errors.append(
            "manifest is missing package paths: {}".format(
                ", ".join(missing)
            )
        )
    if stale:
        errors.append(
            "manifest has absent package paths: {}".format(
                ", ".join(stale)
            )
        )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("verified {} entries".format(len(expected)))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.write:
            return write_manifest()
        return check_manifest()
    except (OSError, UnicodeError, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
