#!/usr/bin/env python3
"""Extract, compress, and verify a core DRAT proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import subprocess
import time
from pathlib import Path


EXPECTED_CHECKER_SOURCE_COMMIT = (
    "2e3b2dc0ecf938addbd779d42877b6ed69d9a985"
)
EXPECTED_CHECKER_SHA256 = (
    "f58f63b0f76945d4c4c9ff6e87afaf870f579e67c0f7cca589492df8fc7ebd47"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_commit(source_directory: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(source_directory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def require_clean_source_tree(source_directory: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(source_directory),
            "status",
            "--porcelain",
            "--untracked-files=no",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise AssertionError(f"tracked source changes in {source_directory}")


def stream_to_checker(
    checker: Path,
    cnf: Path,
    proof: Path,
    log_path: Path,
    extra_arguments: list[str],
) -> tuple[int, float, int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    started = time.perf_counter()
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [str(checker), str(cnf), "-i", *extra_arguments],
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        if process.stdin is None:
            raise AssertionError("failed to open checker input")
        try:
            with lzma.open(proof, "rb") as source:
                for block in iter(
                    lambda: source.read(1024 * 1024),
                    b"",
                ):
                    digest.update(block)
                    byte_count += len(block)
                    process.stdin.write(block)
            process.stdin.close()
            return_code = process.wait()
        except BaseException:
            if not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
    elapsed = time.perf_counter() - started
    with log_path.open("ab") as log:
        log.write(f"drat_trim_exit_code={return_code}\n".encode("ascii"))
    return return_code, elapsed, byte_count, digest.hexdigest()


def compress_file(source: Path, destination: Path) -> None:
    with source.open("rb") as input_handle:
        with lzma.open(destination, "wb", preset=9) as output_handle:
            for block in iter(
                lambda: input_handle.read(1024 * 1024),
                b"",
            ):
                output_handle.write(block)


def require_verified(log_path: Path, return_code: int) -> None:
    output = log_path.read_text(
        encoding="ascii",
        errors="replace",
    )
    if return_code != 0:
        raise AssertionError(
            f"drat-trim returned {return_code}: {log_path}"
        )
    if "s VERIFIED" not in output:
        raise AssertionError(f"proof did not verify: {log_path}")


def extraction_arguments(
    core_path: Path,
    optimize_to_fixpoint: bool,
) -> list[str]:
    arguments = ["-C", "-l", str(core_path)]
    if optimize_to_fixpoint:
        arguments.insert(0, "-O")
    return arguments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--checker-source", type=Path, required=True)
    parser.add_argument("--cnf", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log-prefix", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument(
        "--optimize-to-fixpoint",
        action="store_true",
        help=(
            "repeat core extraction to a fixpoint; single-pass extraction "
            "is the default because the retained core is verified separately"
        ),
    )
    args = parser.parse_args()

    observed_commit = source_commit(args.checker_source)
    if observed_commit != EXPECTED_CHECKER_SOURCE_COMMIT:
        raise AssertionError("unexpected drat-trim source commit")
    if args.checker.resolve() != (
        args.checker_source / "drat-trim"
    ).resolve():
        raise AssertionError("checker is not the pinned source build")
    require_clean_source_tree(args.checker_source)
    checker_sha256 = file_sha256(args.checker)
    if checker_sha256 != EXPECTED_CHECKER_SHA256:
        raise AssertionError("unexpected drat-trim binary hash")
    for path, label in (
        (args.checker, "checker"),
        (args.cnf, "CNF"),
        (args.proof, "proof"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    for path, label in (
        (args.output, "output"),
        (args.metadata, "metadata"),
    ):
        if path.exists():
            raise FileExistsError(f"{label} already exists: {path}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.log_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    core_path = args.output.with_suffix("")
    if core_path.exists():
        raise FileExistsError(f"temporary core exists: {core_path}")
    extraction_log = args.log_prefix.with_name(
        args.log_prefix.name + "-extract.log"
    )
    verification_log = args.log_prefix.with_name(
        args.log_prefix.name + "-verify.log"
    )
    if extraction_log.exists() or verification_log.exists():
        raise FileExistsError("compaction log already exists")

    extract_code, extract_seconds, source_bytes, source_digest = (
        stream_to_checker(
            args.checker,
            args.cnf,
            args.proof,
            extraction_log,
            extraction_arguments(
                core_path,
                args.optimize_to_fixpoint,
            ),
        )
    )
    require_verified(extraction_log, extract_code)
    if not core_path.is_file():
        raise AssertionError("drat-trim did not emit a core proof")

    compress_file(core_path, args.output)
    core_path.unlink()

    verify_code, verify_seconds, output_bytes, output_digest = (
        stream_to_checker(
            args.checker,
            args.cnf,
            args.output,
            verification_log,
            [],
        )
    )
    require_verified(verification_log, verify_code)

    record = {
        "cnf": {
            "path": args.cnf.name,
            "bytes": args.cnf.stat().st_size,
            "sha256": file_sha256(args.cnf),
        },
        "source_proof": {
            "path": args.proof.name,
            "role": "solver-output",
            "compressed_bytes": args.proof.stat().st_size,
            "compressed_sha256": file_sha256(args.proof),
            "decompressed_bytes": source_bytes,
            "decompressed_sha256": source_digest,
        },
        "compacted_proof": {
            "path": args.output.name,
            "role": "retained-core",
            "compressed_bytes": args.output.stat().st_size,
            "compressed_sha256": file_sha256(args.output),
            "decompressed_bytes": output_bytes,
            "decompressed_sha256": output_digest,
        },
        "checker": {
            "path": args.checker.name,
            "sha256": checker_sha256,
            "source_commit": observed_commit,
        },
        "extraction": {
            "strategy": (
                "fixpoint"
                if args.optimize_to_fixpoint
                else "single-pass"
            ),
            "wall_seconds": round(extract_seconds, 6),
            "log": extraction_log.name,
            "log_sha256": file_sha256(extraction_log),
        },
        "verification": {
            "wall_seconds": round(verify_seconds, 6),
            "log": verification_log.name,
            "log_sha256": file_sha256(verification_log),
        },
        "verified": True,
    }
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    with args.metadata.open(
        "w",
        encoding="ascii",
        newline="\n",
    ) as handle:
        handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
