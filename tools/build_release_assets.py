#!/usr/bin/env python3
"""Build and verify deterministic paper-inclusive release assets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "dist" / "release"
PROJECT = "ramsey-number-5-5"
VERSION_RE = re.compile(r"^version:\s*[\"']?([^\"' \n]+)", re.MULTILINE)
CHECKSUM_RE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class TreeEntry:
    path: str
    mode: int
    object_id: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(arguments: list[str]) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def resolve_ref(reference: str) -> str:
    commit = git_output(
        ["rev-parse", "--verify", f"{reference}^{{commit}}"]
    ).decode("ascii").strip()
    if COMMIT_RE.fullmatch(commit) is None:
        raise ValueError(f"Git reference did not resolve to a commit: {reference}")
    return commit


def tree_entries(reference: str) -> list[TreeEntry]:
    commit = resolve_ref(reference)
    entries = []
    for record in git_output(["ls-tree", "-r", "-z", commit]).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode_text, object_type, object_id = metadata.decode("ascii").split()
        path = os.fsdecode(raw_path)
        parts = Path(path).parts
        if (
            object_type != "blob"
            or mode_text not in {"100644", "100755"}
            or Path(path).is_absolute()
            or ".." in parts
        ):
            raise ValueError(f"unsupported Git tree entry: {path}")
        entries.append(
            TreeEntry(
                path=path,
                mode=0o755 if mode_text == "100755" else 0o644,
                object_id=object_id,
            )
        )
    return sorted(entries, key=lambda entry: entry.path)


def blob_bytes(object_id: str) -> bytes:
    return git_output(["cat-file", "blob", object_id])


def text_at_ref(reference: str, relative: str) -> str:
    for entry in tree_entries(reference):
        if entry.path == relative:
            return blob_bytes(entry.object_id).decode("utf-8")
    raise ValueError(f"{relative} is absent from Git reference {reference}")


def project_version(reference: str = "HEAD") -> str:
    match = VERSION_RE.search(text_at_ref(reference, "CITATION.cff"))
    if match is None:
        raise ValueError("CITATION.cff has no version")
    return match.group(1).removeprefix("v")


def validate_tag(reference: str, tag: str, version: str) -> str:
    if tag != f"v{version}":
        raise ValueError(f"release tag {tag!r} does not match version {version}")
    commit = resolve_ref(reference)
    tag_commit = resolve_ref(f"refs/tags/{tag}")
    if tag_commit != commit:
        raise ValueError(
            f"release tag {tag} resolves to {tag_commit}, expected {commit}"
        )
    return commit


def normalized_tar_info(
    data: bytes,
    mode: int,
    archive_name: str,
) -> tarfile.TarInfo:
    info = tarfile.TarInfo(archive_name)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    return info


def build_source_archive(
    output: Path,
    version: str,
    reference: str,
) -> None:
    commit = resolve_ref(reference)
    prefix = f"{PROJECT}-v{version}"
    with output.open("wb") as raw_stream:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_stream,
            mtime=0,
        ) as gzip_stream:
            with tarfile.open(
                fileobj=gzip_stream,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for entry in tree_entries(commit):
                    data = blob_bytes(entry.object_id)
                    archive.addfile(
                        normalized_tar_info(
                            data,
                            entry.mode,
                            f"{prefix}/{entry.path}",
                        ),
                        io.BytesIO(data),
                    )


def asset_names(version: str) -> dict[str, str]:
    return {
        "paper": f"{PROJECT}-paper-v{version}.pdf",
        "source": f"{PROJECT}-source-v{version}.tar.gz",
    }


def verify_pdf(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{path} is missing or unsafe")
    if path.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"{path} is not a PDF")


def verify_paper_binding(release_paper: Path, inspected_paper: Path) -> None:
    verify_pdf(release_paper)
    verify_pdf(inspected_paper)
    if sha256(release_paper) != sha256(inspected_paper):
        raise ValueError("release paper does not match the inspected build")


def replace_file(source: Path, destination: Path) -> None:
    shutil.copyfile(source, destination)
    destination.chmod(0o644)


def write_checksums(directory: Path, names: dict[str, str]) -> None:
    lines = [
        f"{sha256(directory / name)}  {name}\n"
        for name in sorted(names.values())
    ]
    with (directory / "SHA256SUMS").open(
        "w",
        encoding="ascii",
        newline="\n",
    ) as stream:
        stream.write("".join(lines))


def read_checksums(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="ascii").splitlines(),
        start=1,
    ):
        match = CHECKSUM_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid checksum line {line_number}")
        digest, name = match.groups()
        if name in entries:
            raise ValueError(f"duplicate checksum entry: {name}")
        entries[name] = digest
    return entries


def build_assets(reference: str, paper: Path, tag: str | None = None) -> None:
    commit = resolve_ref(reference)
    version = project_version(commit)
    if tag is not None:
        validate_tag(commit, tag, version)
    verify_pdf(paper)
    names = asset_names(version)

    RELEASE_DIR.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix="release-assets-", dir=RELEASE_DIR.parent)
    )
    try:
        replace_file(paper, staging / names["paper"])
        build_source_archive(staging / names["source"], version, commit)
        write_checksums(staging, names)
        if RELEASE_DIR.is_symlink():
            raise ValueError("dist/release must not be a symlink")
        if RELEASE_DIR.exists():
            shutil.rmtree(RELEASE_DIR)
        os.replace(staging, RELEASE_DIR)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    print(
        f"built 3 release files from {commit} in "
        f"{RELEASE_DIR.relative_to(ROOT)}"
    )


def verify_source_archive(
    path: Path,
    version: str,
    reference: str,
) -> None:
    commit = resolve_ref(reference)
    prefix = f"{PROJECT}-v{version}/"
    expected = {
        f"{prefix}{entry.path}": entry
        for entry in tree_entries(commit)
    }
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError("source archive contains duplicate members")
        observed = {member.name: member for member in members}
        if any(
            not member.isfile()
            or not member.name.startswith(prefix)
            or Path(member.name).is_absolute()
            or ".." in Path(member.name).parts
            or member.uid != 0
            or member.gid != 0
            or member.mtime != 0
            for member in members
        ):
            raise ValueError("source archive contains an unsafe member")
        if set(observed) != set(expected):
            raise ValueError("source archive does not match the Git tree")
        for name, entry in expected.items():
            member = observed[name]
            if member.mode != entry.mode:
                raise ValueError(f"source archive mode mismatch: {name}")
            stream = archive.extractfile(member)
            if stream is None or stream.read() != blob_bytes(entry.object_id):
                raise ValueError(f"source archive content mismatch: {name}")


def verify_assets(
    reference: str,
    expected_paper: Path,
    tag: str | None = None,
) -> None:
    commit = resolve_ref(reference)
    version = project_version(commit)
    if tag is not None:
        validate_tag(commit, tag, version)
    names = asset_names(version)
    expected_files = set(names.values()) | {"SHA256SUMS"}
    if not RELEASE_DIR.is_dir() or RELEASE_DIR.is_symlink():
        raise ValueError("dist/release is missing or unsafe")
    paths = list(RELEASE_DIR.iterdir())
    if (
        {path.name for path in paths} != expected_files
        or any(not path.is_file() or path.is_symlink() for path in paths)
    ):
        raise ValueError("dist/release contains an unexpected asset set")

    entries = read_checksums(RELEASE_DIR / "SHA256SUMS")
    if set(entries) != set(names.values()):
        raise ValueError("SHA256SUMS does not list the expected release assets")
    for name, expected in entries.items():
        if sha256(RELEASE_DIR / name) != expected:
            raise ValueError(f"release asset hash mismatch: {name}")

    paper = RELEASE_DIR / names["paper"]
    verify_paper_binding(paper, expected_paper)
    verify_source_archive(
        RELEASE_DIR / names["source"],
        version,
        commit,
    )
    print(f"verified 3 release files against {commit}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify existing assets instead of rebuilding them",
    )
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="Git commit or ref used for the source archive",
    )
    parser.add_argument("--tag", help="require this tag to match the ref")
    parser.add_argument(
        "--paper",
        type=Path,
        default=ROOT / "build" / "paper" / "main.pdf",
    )
    args = parser.parse_args()
    paper = args.paper if args.paper.is_absolute() else ROOT / args.paper

    if args.check:
        verify_assets(args.ref, paper, args.tag)
    else:
        build_assets(args.ref, paper, args.tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
