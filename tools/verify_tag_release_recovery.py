#!/usr/bin/env python3
"""Verify the inputs used by the protected-tag recovery workflow."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Mapping


CONTROLLER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "ruturajr-raval/ramsey-number-5-5"
TAG = "v0.1.0"
TAG_OBJECT_SHA = "8663083baca77bad70f9e850741a79aa02b51d5f"
RELEASE_COMMIT = "efbd19f319e9131fd550ec149bd1e5b72a82efee"
RELEASE_VERSION = "0.1.0"
RULESET_ID = 22507956
FAILED_RUN_ID = 34252608262
FAILED_JOB_ID = 102150449870
ARTIFACT_ID = 10070157214
ARTIFACT_NAME = "release-candidate-evidence"
ARTIFACT_SIZE = 288598
ARTIFACT_DIGEST = (
    "sha256:a9aafbff8cbacbf48d7ffa404c9df6a23631393e37e0cdf79bfe864d09aa2190"
)
ARTIFACT_EXPIRES_AT = "2026-09-11T18:13:45Z"
CANDIDATE_EVIDENCE_SHA256 = (
    "012be8884e4e171c00d17b5b1bc0ddf5e44296752f46fc5d251eb4a7f88e6a73"
)
PAPER_SHA256 = (
    "391228329992b56fdad739404940d2fa31a6beb21bb9faee098481b59c5cb512"
)
PAPER_BUILD_RECORD_SHA256 = (
    "559e59b6d98b6c94183a22929cb7e51686ae1c52d7f2ede668ab80b0207fde2b"
)
PAPER_LOG_SHA256 = (
    "2e327291539053cc70fbb6b451d9475d37a36e10de7632fd005b7b53b2f1dd4c"
)
RELEASE_MANIFEST_SHA256 = (
    "76e60847abab01adb2646e50e000e850849f7b9f24d8f3622daac10853fea692"
)
TAGGED_RELEASE_GATE_SHA256 = (
    "32a539e2c76516a48ce3b3ba870bd9102ef22cb6fbf56685758683de5af8613f"
)
OWNER_AUDITED_AT = "2026-09-08T18:42:34Z"
OWNER_AUDIT_VALID_UNTIL = "2026-09-09T18:42:34Z"
PUBLICATION_AUTHORIZATION = {
    "status": "pending_second_owner_ruleset_audit",
    "required_action": (
        "Run and retain a second owner-authenticated ruleset audit after "
        "the recovery workflow succeeds and before creating the GitHub release."
    ),
}
EXPECTED_RELEASE_ASSETS = {
    "SHA256SUMS": (
        "73eb9e627f04dc0312233837e3ba4b718453274b0fbc04c8ba001883084b3082"
    ),
    "ramsey-number-5-5-paper-v0.1.0.pdf": PAPER_SHA256,
    "ramsey-number-5-5-source-v0.1.0.tar.gz": (
        "32fbc675072083c7689e821835bc3d202d2fbc12602e602016a85d72fc18ae0d"
    ),
}
SUCCESSFUL_STEPS = {
    "Unit and repository checks",
    "Build pinned drat-trim",
    "Regenerate all formulas and replay all proofs",
    "Build technical report",
    "Verify release candidate evidence",
    "Upload candidate evidence",
    "Verify release manifest",
    "Assert deterministic release manifest",
    "Build and verify deterministic release assets",
    "Assert tracked tree unchanged",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, label: str, errors: list[str]) -> object | None:
    try:
        with path.open(encoding="ascii") as stream:
            return json.load(stream)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"{label} could not be read: {error}")
        return None


def fetch_json(path: str, token: str) -> object:
    request = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ramsey-number-5-5-tag-recovery",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        raise RuntimeError(f"GitHub request failed for {path}: {error}") from error


def expected_ruleset() -> dict[str, object]:
    return {
        "id": RULESET_ID,
        "name": "Protect version tags",
        "target": "tag",
        "source_type": "Repository",
        "source": REPOSITORY,
        "enforcement": "active",
        "bypass_actors": [],
        "current_user_can_bypass": "never",
        "conditions": {
            "ref_name": {
                "exclude": [],
                "include": ["refs/tags/v*"],
            }
        },
        "rules": [
            {"type": "update"},
            {"type": "deletion"},
        ],
    }


def record_errors(record: object) -> list[str]:
    if not isinstance(record, dict):
        return ["recovery record must be an object"]
    errors: list[str] = []
    expected_top = {
        "schema_version": 1,
        "project": "ramsey-number-5-5",
        "audited_at": OWNER_AUDITED_AT,
        "owner_audit_valid_until": OWNER_AUDIT_VALID_UNTIL,
    }
    for key, expected in expected_top.items():
        if record.get(key) != expected:
            errors.append(f"recovery record {key} is unexpected")
    if not isinstance(record.get("reason"), str) or len(record["reason"]) < 100:
        errors.append("recovery reason is incomplete")

    release = record.get("release")
    expected_release = {
        "tag": TAG,
        "tag_object_sha": TAG_OBJECT_SHA,
        "commit_sha": RELEASE_COMMIT,
        "tag_message": "Release v0.1.0",
        "tagger_name": "Ruturaj R Raval",
        "tagger_date": "2026-09-08T16:41:27Z",
        "signature_status": "unsigned",
    }
    if not isinstance(release, dict):
        errors.append("recovery release record is missing")
    else:
        for key, expected in expected_release.items():
            if release.get(key) != expected:
                errors.append(f"recovery release {key} is unexpected")

    failed_run = record.get("failed_tag_run")
    expected_run = {
        "run_id": FAILED_RUN_ID,
        "job_id": FAILED_JOB_ID,
        "event": "push",
        "head_branch": TAG,
        "head_sha": RELEASE_COMMIT,
        "conclusion": "failure",
        "failure_step": "Verify final release gate",
        "candidate_artifact_id": ARTIFACT_ID,
        "candidate_artifact_name": ARTIFACT_NAME,
        "candidate_artifact_size": ARTIFACT_SIZE,
        "candidate_artifact_digest": ARTIFACT_DIGEST,
        "candidate_artifact_expires_at": ARTIFACT_EXPIRES_AT,
        "candidate_evidence_sha256": CANDIDATE_EVIDENCE_SHA256,
        "paper_sha256": PAPER_SHA256,
        "paper_build_record_sha256": PAPER_BUILD_RECORD_SHA256,
    }
    if not isinstance(failed_run, dict):
        errors.append("failed tag-run record is missing")
    else:
        for key, expected in expected_run.items():
            if failed_run.get(key) != expected:
                errors.append(f"failed tag-run {key} is unexpected")

    if record.get("ruleset_owner_audit") != expected_ruleset():
        errors.append("owner-authenticated ruleset audit is unexpected")
    return errors


def parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def owner_audit_freshness_errors(
    record: object,
    now: datetime | None = None,
) -> list[str]:
    if not isinstance(record, dict):
        return ["owner-authenticated ruleset audit record is missing"]
    audited_at = parse_utc(record.get("audited_at"))
    valid_until = parse_utc(record.get("owner_audit_valid_until"))
    if audited_at is None or valid_until is None:
        return ["owner-authenticated ruleset audit window is invalid"]
    errors: list[str] = []
    if valid_until <= audited_at:
        errors.append("owner-authenticated ruleset audit window is empty")
    observed = datetime.now(timezone.utc) if now is None else now
    if observed < audited_at:
        errors.append("owner-authenticated ruleset audit is future-dated")
    if observed > valid_until:
        errors.append("owner-authenticated ruleset audit has expired")
    return errors


def ruleset_security_field_sources(live: object) -> dict[str, str]:
    if not isinstance(live, dict):
        return {}
    return {
        key: "live" if key in live else "owner_audit_only"
        for key in ("bypass_actors", "current_user_can_bypass")
    }


def ruleset_errors(live: object, audited: object) -> list[str]:
    if not isinstance(live, dict) or not isinstance(audited, dict):
        return ["ruleset responses must be objects"]
    errors: list[str] = []
    for key in (
        "id",
        "name",
        "target",
        "source_type",
        "source",
        "enforcement",
        "conditions",
        "rules",
    ):
        if live.get(key) != audited.get(key):
            errors.append(f"live ruleset {key} differs from owner audit")
    if "bypass_actors" in live and live["bypass_actors"] != []:
        errors.append("live ruleset reports bypass actors")
    if (
        "current_user_can_bypass" in live
        and live["current_user_can_bypass"] != "never"
    ):
        errors.append("workflow actor can bypass the ruleset")
    return errors


def tag_errors(ref: object, tag: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(ref, dict):
        return ["tag reference response is not an object"]
    target = ref.get("object")
    if not isinstance(target, dict):
        errors.append("tag reference target is missing")
    elif target.get("type") != "tag" or target.get("sha") != TAG_OBJECT_SHA:
        errors.append("tag reference does not name the annotated tag object")

    if not isinstance(tag, dict):
        errors.append("tag object response is not an object")
        return errors
    if tag.get("sha") != TAG_OBJECT_SHA or tag.get("tag") != TAG:
        errors.append("annotated tag identity is unexpected")
    if tag.get("message") != "Release v0.1.0\n":
        errors.append("annotated tag message is unexpected")
    commit = tag.get("object")
    if not isinstance(commit, dict):
        errors.append("annotated tag target is missing")
    elif commit.get("type") != "commit" or commit.get("sha") != RELEASE_COMMIT:
        errors.append("annotated tag target commit is unexpected")
    return errors


def failed_run_errors(
    run: object,
    jobs: object,
    artifacts: object,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(run, dict):
        return ["failed tag run response is not an object"]
    expected_run = {
        "id": FAILED_RUN_ID,
        "name": "ci",
        "event": "push",
        "status": "completed",
        "conclusion": "failure",
        "head_branch": TAG,
        "head_sha": RELEASE_COMMIT,
    }
    for key, expected in expected_run.items():
        if run.get(key) != expected:
            errors.append(f"live failed tag run {key} is unexpected")

    job_values = jobs.get("jobs") if isinstance(jobs, dict) else None
    job = next(
        (
            value
            for value in job_values or []
            if isinstance(value, dict) and value.get("id") == FAILED_JOB_ID
        ),
        None,
    )
    if job is None:
        errors.append("failed tag-run job is missing")
    else:
        if job.get("name") != "verify" or job.get("conclusion") != "failure":
            errors.append("failed tag-run job identity is unexpected")
        steps = {
            step.get("name"): step.get("conclusion")
            for step in job.get("steps", [])
            if isinstance(step, dict)
        }
        for name in SUCCESSFUL_STEPS:
            if steps.get(name) != "success":
                errors.append(f"failed tag-run step did not pass: {name}")
        if steps.get("Verify final release gate") != "failure":
            errors.append("failed tag run did not stop at the final release gate")
        if steps.get("Upload tag-verified release") != "skipped":
            errors.append("failed tag run unexpectedly uploaded release assets")

    artifact_values = (
        artifacts.get("artifacts") if isinstance(artifacts, dict) else None
    )
    artifact = next(
        (
            value
            for value in artifact_values or []
            if isinstance(value, dict) and value.get("id") == ARTIFACT_ID
        ),
        None,
    )
    if artifact is None:
        errors.append("candidate evidence artifact is missing")
    else:
        expected_artifact = {
            "name": ARTIFACT_NAME,
            "size_in_bytes": ARTIFACT_SIZE,
            "digest": ARTIFACT_DIGEST,
            "expired": False,
            "expires_at": ARTIFACT_EXPIRES_AT,
        }
        for key, expected in expected_artifact.items():
            if artifact.get(key) != expected:
                errors.append(f"candidate evidence artifact {key} is unexpected")
    return errors


def release_checkout_errors(release_root: Path) -> list[str]:
    errors: list[str] = []
    commands = (
        (["git", "rev-parse", "HEAD"], RELEASE_COMMIT, "checked-out commit"),
        (
            ["git", "cat-file", "-t", f"refs/tags/{TAG}"],
            "tag",
            "tag object type",
        ),
        (
            ["git", "rev-parse", f"refs/tags/{TAG}"],
            TAG_OBJECT_SHA,
            "tag object SHA",
        ),
        (
            ["git", "rev-parse", f"refs/tags/{TAG}^{{commit}}"],
            RELEASE_COMMIT,
            "tag target commit",
        ),
    )
    for command, expected, label in commands:
        completed = subprocess.run(
            command,
            cwd=release_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or completed.stdout.strip() != expected:
            errors.append(f"{label} is unexpected")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=release_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        errors.append("release checkout Git status is unavailable")
    elif status.stdout.strip():
        errors.append("release checkout has tracked or untracked changes")
    return errors


def local_evidence_errors(
    release_root: Path,
    candidate_evidence_path: Path,
) -> list[str]:
    errors: list[str] = []
    if (
        not candidate_evidence_path.is_file()
        or candidate_evidence_path.is_symlink()
    ):
        errors.append("candidate evidence JSON is missing or unsafe")
    elif sha256(candidate_evidence_path) != CANDIDATE_EVIDENCE_SHA256:
        errors.append("candidate evidence JSON hash is unexpected")
    evidence = load_json(
        candidate_evidence_path,
        "candidate evidence",
        errors,
    )
    if isinstance(evidence, dict):
        expected = {
            "project": "ramsey-number-5-5",
            "mode": "candidate",
            "git_commit": RELEASE_COMMIT,
            "working_tree_dirty": False,
            "result": "verified",
        }
        for key, value in expected.items():
            if evidence.get(key) != value:
                errors.append(f"candidate evidence {key} is unexpected")
        hashes = evidence.get("evidence")
        if not isinstance(hashes, dict):
            errors.append("candidate evidence hashes are missing")
        else:
            checks = {
                "paper_pdf_sha256": (
                    release_root / "build/paper/main.pdf",
                    PAPER_SHA256,
                ),
                "paper_build_record_sha256": (
                    release_root / "build/paper/paper-build.json",
                    PAPER_BUILD_RECORD_SHA256,
                ),
                "c6_replay_sha256": (
                    release_root
                    / "build/proof-replay-c6/fresh-proof-replay.json",
                    hashes.get("c6_replay_sha256"),
                ),
                "c8_replay_sha256": (
                    release_root
                    / "build/proof-replay-c8/fresh-proof-replay.json",
                    hashes.get("c8_replay_sha256"),
                ),
                "release_manifest_sha256": (
                    release_root / "release-manifest.sha256",
                    RELEASE_MANIFEST_SHA256,
                ),
            }
            for key, (path, expected_hash) in checks.items():
                if not path.is_file() or sha256(path) != expected_hash:
                    errors.append(f"candidate artifact {key} is unexpected")
                if key in hashes and hashes.get(key) != expected_hash:
                    errors.append(f"candidate evidence {key} does not bind its file")

    errors.extend(release_checkout_errors(release_root))
    return errors


def exact_release_asset_errors(
    release_root: Path,
    expected: Mapping[str, str] = EXPECTED_RELEASE_ASSETS,
) -> list[str]:
    release_dir = release_root / "dist/release"
    if not release_dir.is_dir() or release_dir.is_symlink():
        return ["tagged release asset directory is missing or unsafe"]
    paths = list(release_dir.iterdir())
    observed_names = {path.name for path in paths}
    errors: list[str] = []
    if observed_names != set(expected):
        errors.append("tagged release asset inventory is unexpected")
    for name, expected_hash in expected.items():
        path = release_dir / name
        if not path.is_file() or path.is_symlink():
            errors.append(f"tagged release asset is missing or unsafe: {name}")
        elif sha256(path) != expected_hash:
            errors.append(f"tagged release asset hash is unexpected: {name}")
    return errors


def restore_tagged_paper_log(
    release_root: Path,
) -> list[str]:
    source = (
        release_root / "paper/ramsey-number-5-5-paper-v0.1.0.log"
    )
    target = release_root / "build/paper/main.log"
    record_path = release_root / "build/paper/paper-build.json"
    errors: list[str] = []
    if not source.is_file() or source.is_symlink():
        errors.append("tagged paper log is missing or unsafe")
    elif sha256(source) != PAPER_LOG_SHA256:
        errors.append("tagged paper log hash is unexpected")
    record = load_json(record_path, "paper build record", errors)
    expected_log = {
        "path": "build/paper/main.log",
        "reported_bytes": 49068,
        "reported_output": "main.xdv",
        "reported_pages": 9,
        "sha256": PAPER_LOG_SHA256,
    }
    if (
        not isinstance(record, dict)
        or record.get("latex_log") != expected_log
    ):
        errors.append("paper build record does not bind the tagged log")
    if (
        not target.parent.is_dir()
        or target.parent.is_symlink()
        or (target.exists() and (not target.is_file() or target.is_symlink()))
    ):
        errors.append("paper log reconstruction path is unsafe")
    if errors:
        return errors
    shutil.copyfile(source, target)
    target.chmod(0o644)
    if sha256(target) != PAPER_LOG_SHA256:
        errors.append("reconstructed paper log hash is unexpected")
    return errors


def git_head(root: Path, label: str, errors: list[str]) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        errors.append(f"{label} Git commit is unavailable")
        return None
    return value


def recovery_environment_errors(
    environment: Mapping[str, str] | None = None,
    controller_root: Path = CONTROLLER_ROOT,
    controller_commit: str | None = None,
) -> list[str]:
    values = os.environ if environment is None else environment
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REF_TYPE": "branch",
        "GITHUB_REF_NAME": "main",
        "GITHUB_WORKFLOW": "tag-release-recovery",
    }
    errors = [
        f"recovery workflow {key} is unexpected"
        for key, value in expected.items()
        if values.get(key) != value
    ]
    observed_commit = controller_commit
    if observed_commit is None:
        observed_commit = git_head(
            controller_root,
            "recovery controller",
            errors,
        )
    if observed_commit is not None and values.get("GITHUB_SHA") != observed_commit:
        errors.append("recovery workflow SHA does not match the controller")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        value = values.get(key, "")
        if not value.isdigit() or int(value) <= 0:
            errors.append(f"recovery workflow {key} is invalid")
    expected_workflow_ref = (
        f"{REPOSITORY}/.github/workflows/"
        "tag-release-recovery.yml@refs/heads/main"
    )
    if values.get("GITHUB_WORKFLOW_REF") != expected_workflow_ref:
        errors.append("recovery workflow reference is unexpected")
    return errors


def recovery_environment_record(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str | None]:
    values = os.environ if environment is None else environment
    return {
        "event": values.get("GITHUB_EVENT_NAME"),
        "ref": values.get("GITHUB_REF"),
        "ref_name": values.get("GITHUB_REF_NAME"),
        "ref_type": values.get("GITHUB_REF_TYPE"),
        "repository": values.get("GITHUB_REPOSITORY"),
        "run_attempt": values.get("GITHUB_RUN_ATTEMPT"),
        "run_id": values.get("GITHUB_RUN_ID"),
        "sha": values.get("GITHUB_SHA"),
        "workflow": values.get("GITHUB_WORKFLOW"),
        "workflow_ref": values.get("GITHUB_WORKFLOW_REF"),
    }


def controller_clean_errors(root: Path = CONTROLLER_ROOT) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ["recovery controller Git status is unavailable"]
    if completed.stdout.strip():
        return ["recovery controller has tracked or untracked changes"]
    return []


def load_tagged_release_gate_module(release_root: Path) -> ModuleType:
    module_path = release_root / "tools/verify_release_gate.py"
    if not module_path.is_file() or module_path.is_symlink():
        raise RuntimeError("tagged release-gate verifier is missing or unsafe")
    if sha256(module_path) != TAGGED_RELEASE_GATE_SHA256:
        raise RuntimeError("tagged release-gate verifier hash is unexpected")
    module_name = "_ramsey_tagged_verify_release_gate"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("tagged release-gate verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    tools_path = str(module_path.parent)
    sys.path.insert(0, tools_path)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise RuntimeError(
            f"tagged release-gate verifier could not be loaded: {error}"
        ) from error
    finally:
        sys.path.remove(tools_path)
    return module


def tagged_final_gate_evidence(
    release_root: Path,
) -> tuple[list[str], dict[str, object] | None]:
    errors: list[str] = []
    try:
        module = load_tagged_release_gate_module(release_root)
    except RuntimeError as error:
        return [str(error)], None
    paths = module.default_evidence_paths(release_root)
    gate = module.load_json(
        release_root / "research/release-gate.json",
        "release gate",
        errors,
    )
    release_ref = f"refs/tags/{TAG}"
    if gate is not None:
        errors.extend(module.validation_errors(gate, paths, "final"))
        errors.extend(
            module.hosted_candidate_commit_errors(
                gate,
                release_root,
                release_ref,
                "final",
            )
        )
    errors.extend(release_checkout_errors(release_root))
    errors.extend(
        module.reference_snapshot_errors(
            paths,
            release_ref,
            RELEASE_VERSION,
        )
    )
    if errors or not isinstance(gate, dict):
        return errors, None
    evidence = module.evidence_record(
        gate,
        paths,
        "final",
        release_ref,
        TAG,
    )
    evidence.pop("hosted_verification", None)
    evidence["verification_mode"] = "protected-tag-recovery"
    return [], evidence


def preflight_evidence_errors(path: Path) -> list[str]:
    errors: list[str] = []
    value = load_json(path, "recovery preflight evidence", errors)
    expected = {
        "schema_version": 1,
        "project": "ramsey-number-5-5",
        "phase": "preflight",
        "result": "verified",
        "failed_tag_run_id": FAILED_RUN_ID,
        "failed_tag_job_id": FAILED_JOB_ID,
        "candidate_artifact_id": ARTIFACT_ID,
        "candidate_artifact_digest": ARTIFACT_DIGEST,
        "candidate_artifact_expires_at": ARTIFACT_EXPIRES_AT,
        "release_tag": TAG,
        "release_tag_object_sha": TAG_OBJECT_SHA,
        "release_commit": RELEASE_COMMIT,
        "ruleset_id": RULESET_ID,
        "publication_authorization": PUBLICATION_AUTHORIZATION,
        "paper_log_reconstruction": {
            "source": "paper/ramsey-number-5-5-paper-v0.1.0.log",
            "target": "build/paper/main.log",
            "sha256": PAPER_LOG_SHA256,
        },
    }
    if isinstance(value, dict):
        for key, expected_value in expected.items():
            if value.get(key) != expected_value:
                errors.append(f"recovery preflight evidence {key} is unexpected")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("preflight", "final"),
        default="preflight",
    )
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--candidate-evidence", type=Path, required=True)
    parser.add_argument("--preflight-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("error: GITHUB_TOKEN or GH_TOKEN is required")
        return 1

    errors: list[str] = []
    record = load_json(args.record, "recovery record", errors)
    if record is not None:
        errors.extend(record_errors(record))
        errors.extend(owner_audit_freshness_errors(record))
    try:
        live_ruleset = fetch_json(
            f"repos/{REPOSITORY}/rulesets/{RULESET_ID}",
            token,
        )
        tag_ref = fetch_json(
            f"repos/{REPOSITORY}/git/ref/tags/{TAG}",
            token,
        )
        tag_object = fetch_json(
            f"repos/{REPOSITORY}/git/tags/{TAG_OBJECT_SHA}",
            token,
        )
        failed_run = fetch_json(
            f"repos/{REPOSITORY}/actions/runs/{FAILED_RUN_ID}",
            token,
        )
        jobs = fetch_json(
            f"repos/{REPOSITORY}/actions/runs/{FAILED_RUN_ID}/jobs?per_page=100",
            token,
        )
        artifacts = fetch_json(
            f"repos/{REPOSITORY}/actions/runs/{FAILED_RUN_ID}/artifacts",
            token,
        )
    except RuntimeError as error:
        errors.append(str(error))
        live_ruleset = tag_ref = tag_object = failed_run = jobs = artifacts = {}

    audited_ruleset = (
        record.get("ruleset_owner_audit")
        if isinstance(record, dict)
        else None
    )
    errors.extend(ruleset_errors(live_ruleset, audited_ruleset))
    errors.extend(tag_errors(tag_ref, tag_object))
    errors.extend(failed_run_errors(failed_run, jobs, artifacts))
    errors.extend(
        local_evidence_errors(
            args.release_root.resolve(),
            args.candidate_evidence.resolve(),
        )
    )
    if errors:
        for error in errors:
            print("error: " + error)
        return 1

    if args.phase == "preflight":
        errors.extend(restore_tagged_paper_log(args.release_root.resolve()))
        if errors:
            for error in errors:
                print("error: " + error)
            return 1

    final_gate_evidence = None
    if args.phase == "final":
        if args.preflight_evidence is None:
            errors.append("final recovery requires --preflight-evidence")
        else:
            errors.extend(
                preflight_evidence_errors(args.preflight_evidence.resolve())
            )
        errors.extend(exact_release_asset_errors(args.release_root.resolve()))
        errors.extend(recovery_environment_errors())
        errors.extend(controller_clean_errors())
        if errors:
            for error in errors:
                print("error: " + error)
            return 1
        final_errors, final_gate_evidence = tagged_final_gate_evidence(
            args.release_root.resolve()
        )
        errors.extend(final_errors)
    if errors:
        for error in errors:
            print("error: " + error)
        return 1

    output = {
        "schema_version": 1,
        "project": "ramsey-number-5-5",
        "phase": args.phase,
        "result": "verified",
        "recovery_record_sha256": sha256(args.record),
        "candidate_evidence_sha256": sha256(args.candidate_evidence),
        "failed_tag_run_id": FAILED_RUN_ID,
        "failed_tag_job_id": FAILED_JOB_ID,
        "candidate_artifact_id": ARTIFACT_ID,
        "candidate_artifact_digest": ARTIFACT_DIGEST,
        "candidate_artifact_expires_at": ARTIFACT_EXPIRES_AT,
        "release_tag": TAG,
        "release_tag_object_sha": TAG_OBJECT_SHA,
        "release_commit": RELEASE_COMMIT,
        "ruleset_id": RULESET_ID,
        "ruleset_owner_audited_at": record.get("audited_at"),
        "ruleset_owner_audit_valid_until": record.get(
            "owner_audit_valid_until"
        ),
        "ruleset_security_field_sources": ruleset_security_field_sources(
            live_ruleset
        ),
        "publication_authorization": PUBLICATION_AUTHORIZATION,
        "paper_log_reconstruction": {
            "source": "paper/ramsey-number-5-5-paper-v0.1.0.log",
            "target": "build/paper/main.log",
            "sha256": PAPER_LOG_SHA256,
        },
    }
    if args.phase == "final":
        output["preflight_evidence_sha256"] = sha256(
            args.preflight_evidence
        )
        output["recovery_workflow"] = recovery_environment_record()
        output["release_assets"] = {
            name: sha256(args.release_root / "dist/release" / name)
            for name in sorted(EXPECTED_RELEASE_ASSETS)
        }
        output["semantic_release_gate"] = final_gate_evidence
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"tag release recovery {args.phase} verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
