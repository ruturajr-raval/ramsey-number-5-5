#!/usr/bin/env python3
"""Verify the active no-bypass ruleset protecting version tags."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_REPOSITORY = "ruturajr-raval/ramsey-number-5-5"
DEFAULT_RULESET_ID = 22507956


def validation_errors(
    record: object,
    repository: str = DEFAULT_REPOSITORY,
    ruleset_id: int = DEFAULT_RULESET_ID,
) -> list[str]:
    if not isinstance(record, dict):
        return ["GitHub ruleset response must be an object"]

    errors: list[str] = []
    if record.get("id") != ruleset_id:
        errors.append("ruleset ID is unexpected")
    if record.get("name") != "Protect version tags":
        errors.append("ruleset name is unexpected")
    if record.get("target") != "tag":
        errors.append("ruleset target is not tag")
    if record.get("source") != repository:
        errors.append("ruleset repository is unexpected")
    if record.get("enforcement") != "active":
        errors.append("ruleset enforcement is not active")
    if record.get("bypass_actors") != []:
        errors.append("ruleset has bypass actors or bypass state is unavailable")
    if record.get("current_user_can_bypass") != "never":
        errors.append("current authenticated actor can bypass the ruleset")

    conditions = record.get("conditions")
    if not isinstance(conditions, dict):
        errors.append("ruleset conditions are missing")
    elif conditions.get("ref_name") != {
        "exclude": [],
        "include": ["refs/tags/v*"],
    }:
        errors.append("ruleset tag pattern is unexpected")

    rules = record.get("rules")
    if not isinstance(rules, list):
        errors.append("ruleset rules are missing")
    else:
        rule_types = sorted(
            rule.get("type")
            for rule in rules
            if isinstance(rule, dict) and isinstance(rule.get("type"), str)
        )
        if rule_types != ["deletion", "update"]:
            errors.append("ruleset must block tag updates and deletions")
    return errors


def fetch_ruleset(
    repository: str,
    ruleset_id: int,
    token: str,
) -> dict[str, Any]:
    url = (
        "https://api.github.com/repos/"
        f"{repository}/rulesets/{ruleset_id}"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ramsey-number-5-5-release-verifier",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        raise RuntimeError(f"GitHub ruleset request failed: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError("GitHub ruleset response was not an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--ruleset-id", type=int, default=DEFAULT_RULESET_ID)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("error: GITHUB_TOKEN or GH_TOKEN is required")
        return 1
    try:
        record = fetch_ruleset(args.repository, args.ruleset_id, token)
    except RuntimeError as error:
        print(f"error: {error}")
        return 1
    errors = validation_errors(record, args.repository, args.ruleset_id)
    if errors:
        for error in errors:
            print("error: " + error)
        return 1
    print(f"verified protected version-tag ruleset {args.ruleset_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
