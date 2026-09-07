#!/usr/bin/env python3
"""Verify root-prefix branch coverage under relabeling and complementation."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


def canonical_prefix(pattern: tuple[bool, ...]) -> tuple[bool, ...]:
    adjacent = sum(pattern)
    return (True,) * adjacent + (False,) * (len(pattern) - adjacent)


def representative_branch(
    pattern: tuple[bool, ...],
) -> tuple[int, bool]:
    adjacent = sum(pattern)
    if adjacent <= len(pattern) // 2:
        return adjacent, False
    return len(pattern) - adjacent, True


def verify(cycles: int) -> dict[str, object]:
    if cycles < 1:
        raise ValueError("cycles must be positive")

    solved = set(range(cycles // 2 + 1))
    rows = []
    branch_counts = {branch: 0 for branch in sorted(solved)}

    for pattern in itertools.product((False, True), repeat=cycles):
        canonical = canonical_prefix(pattern)
        branch, complemented = representative_branch(pattern)
        transformed = (
            tuple(not value for value in pattern)
            if complemented
            else pattern
        )
        representative = canonical_prefix(transformed)
        expected = (True,) * branch + (False,) * (cycles - branch)

        if canonical.count(True) != sum(pattern):
            raise AssertionError("cycle relabeling changed adjacency count")
        if representative != expected:
            raise AssertionError("pattern did not reduce to prefix branch")
        if branch not in solved:
            raise AssertionError("pattern reduced to an unsolved branch")

        branch_counts[branch] += 1
        rows.append(
            {
                "pattern": "".join("1" if value else "0" for value in pattern),
                "adjacent_cycles": sum(pattern),
                "complemented": complemented,
                "representative_branch": branch,
            }
        )

    return {
        "cycles": cycles,
        "patterns_checked": len(rows),
        "solved_branches": sorted(solved),
        "branch_counts": branch_counts,
        "coverage_complete": len(rows) == 2**cycles,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = verify(args.cycles)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open(
            "w",
            encoding="ascii",
            newline="\n",
        ) as handle:
            handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
