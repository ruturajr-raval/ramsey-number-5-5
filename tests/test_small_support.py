#!/usr/bin/env python3
"""Regression tests for the elementary automorphism exclusions."""

from __future__ import annotations

import unittest

from check_small_support import (
    exclude_order_three,
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


if __name__ == "__main__":
    unittest.main()
