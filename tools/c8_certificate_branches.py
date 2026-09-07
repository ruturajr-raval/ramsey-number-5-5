#!/usr/bin/env python3
"""Shared branch definitions for the retained 3^8 1^19 certificates."""

from __future__ import annotations


CanonicalBranch = tuple[int, int, int]
T4SplitBranch = tuple[int, str]

ROOT_BRANCHES: tuple[CanonicalBranch, ...] = (
    (2, 0, 0),
    (2, 1, 0),
    (2, 0, 1),
    (3, 0, 0),
    (3, 1, 0),
    (3, 0, 1),
    (4, 0, 0),
    (4, 1, 0),
)

RETAINED_CANONICAL_BRANCHES: tuple[CanonicalBranch, ...] = tuple(
    branch for branch in ROOT_BRANCHES if branch[0] in (2, 3)
)

RETAINED_T4_SPLIT_BRANCHES: tuple[T4SplitBranch, ...] = (
    (0, "two-c4"),
    (0, "c8"),
    (1, "two-c4"),
    (1, "c8"),
)


def canonical_stem(branch: CanonicalBranch) -> str:
    triangles, adjacent_triangles, missed_independent = branch
    return (
        f"p3-c8-t{triangles}-p{adjacent_triangles}"
        f"-z{missed_independent}"
    )


def t4_split_stem(branch: T4SplitBranch) -> str:
    adjacent_triangles, matrix_type = branch
    return f"p3-c8-t4-p{adjacent_triangles}-z0-m{matrix_type}"
