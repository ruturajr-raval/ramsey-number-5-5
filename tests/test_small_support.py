#!/usr/bin/env python3
"""Regression tests for the elementary automorphism exclusions."""

from __future__ import annotations

import unittest

from check_small_support import (
    exclude_order_three,
    order_three_eight_internal_type_audit,
    order_three_seven_cycle_audit,
)


class SmallSupportTests(unittest.TestCase):
    def test_order_three_seven_cycle_counting_contradiction(self) -> None:
        audit = order_three_seven_cycle_audit()

        self.assertTrue(audit["excluded"])
        self.assertTrue(
            all(case["excluded"] for case in audit["mixed_cases"])
        )
        self.assertEqual(
            audit["independent_normal_form"][
                "minimum_intercycle_weight_per_cycle"
            ],
            audit["independent_normal_form"][
                "maximum_intercycle_weight_per_cycle"
            ],
        )
        self.assertTrue(
            audit["independent_normal_form"]["pair_weights_forced_one"]
        )
        self.assertTrue(
            audit["independent_normal_form"]["fixed_neighbors_forced"]
        )
        self.assertEqual(
            28,
            audit["fixed_signature_counting"][
                "total_nonneighbor_incidences"
            ],
        )
        self.assertEqual(
            3,
            audit["fixed_signature_counting"][
                "minimum_signature_union_for_fixed_edge"
            ],
        )
        self.assertEqual(
            36,
            audit["fixed_signature_counting"][
                "minimum_nonneighbor_incidences"
            ],
        )

    def test_order_three_six_remains_certificate_based(self) -> None:
        self.assertFalse(exclude_order_three(6))
        self.assertTrue(exclude_order_three(7))

    def test_order_three_eight_internal_type_reduction(self) -> None:
        audit = order_three_eight_internal_type_audit()

        self.assertTrue(audit["one_triangle_case"]["excluded"])
        self.assertEqual(
            28,
            audit["one_triangle_case"]["incidence_upper"],
        )
        self.assertEqual(
            30,
            audit["one_triangle_case"]["incidence_lower"],
        )
        self.assertTrue(audit["all_independent_case"]["excluded"])
        self.assertEqual(
            2,
            audit["all_independent_case"]["minimum_zero_signatures"],
        )
        self.assertEqual(
            [0, 1, 7, 8],
            audit["excluded_triangle_cycle_counts"],
        )
        self.assertEqual(
            [2, 3, 4],
            audit["normalized_remaining_triangle_cycle_counts"],
        )
        self.assertEqual(1, audit["guaranteed_root_exception_upper"])
        self.assertEqual(
            [
                {
                    "triangle_cycles": 2,
                    "independent_cycles": 6,
                    "slack_budget": 4,
                    "minimum_exception_incidences": 28,
                    "maximum_same_type_deviation": 2,
                    "mixed_weight_lower": 20,
                    "mixed_weight_upper": 24,
                    "triangle_mixed_row_lower": 10,
                    "triangle_mixed_row_upper": 14,
                    "independent_mixed_column_lower": 0,
                    "independent_mixed_column_upper": 4,
                },
                {
                    "triangle_cycles": 3,
                    "independent_cycles": 5,
                    "slack_budget": 1,
                    "minimum_exception_incidences": 31,
                    "maximum_same_type_deviation": 0,
                    "mixed_weight_lower": 24,
                    "mixed_weight_upper": 25,
                    "triangle_mixed_row_lower": 8,
                    "triangle_mixed_row_upper": 9,
                    "independent_mixed_column_lower": 4,
                    "independent_mixed_column_upper": 5,
                },
                {
                    "triangle_cycles": 4,
                    "independent_cycles": 4,
                    "slack_budget": 0,
                    "minimum_exception_incidences": 32,
                    "maximum_same_type_deviation": 0,
                    "mixed_weight_lower": 24,
                    "mixed_weight_upper": 24,
                    "triangle_mixed_row_lower": 6,
                    "triangle_mixed_row_upper": 6,
                    "independent_mixed_column_lower": 6,
                    "independent_mixed_column_upper": 6,
                },
            ],
            audit["remaining_case_bounds"],
        )
        self.assertFalse(audit["cycle_type_excluded"])


if __name__ == "__main__":
    unittest.main()
