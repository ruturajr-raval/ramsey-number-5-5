from __future__ import annotations

import copy
import unittest

from verify_github_ruleset import (
    DEFAULT_REPOSITORY,
    DEFAULT_RULESET_ID,
    validation_errors,
)


def valid_record() -> dict[str, object]:
    return {
        "id": DEFAULT_RULESET_ID,
        "name": "Protect version tags",
        "target": "tag",
        "source": DEFAULT_REPOSITORY,
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


class RulesetTests(unittest.TestCase):
    def test_expected_ruleset_is_accepted(self) -> None:
        self.assertEqual([], validation_errors(valid_record()))

    def test_bypass_actor_is_rejected(self) -> None:
        record = valid_record()
        record["bypass_actors"] = [{"actor_id": 1}]
        self.assertIn(
            "ruleset has bypass actors or bypass state is unavailable",
            validation_errors(record),
        )

    def test_missing_update_rule_is_rejected(self) -> None:
        record = valid_record()
        record["rules"] = [{"type": "deletion"}]
        self.assertIn(
            "ruleset must block tag updates and deletions",
            validation_errors(record),
        )

    def test_wrong_pattern_is_rejected(self) -> None:
        record = copy.deepcopy(valid_record())
        record["conditions"]["ref_name"]["include"] = ["refs/tags/v0.1.0"]
        self.assertIn(
            "ruleset tag pattern is unexpected",
            validation_errors(record),
        )


if __name__ == "__main__":
    unittest.main()
