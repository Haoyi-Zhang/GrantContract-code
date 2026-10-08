"""Exhaustive tiny-plant meta-oracle tests."""
from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import metaoracle  # noqa: E402
from metaoracle import run_metaoracle  # noqa: E402


class MetaOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = run_metaoracle(4)

    def test_declared_universe_is_exhausted(self):
        self.assertEqual(self.summary["plants_checked"], 486)
        self.assertEqual(self.summary["receipt_partitions_by_bound"],
                         {"0": 1, "1": 2, "2": 5, "3": 15, "4": 52})
        self.assertEqual(self.summary["receipt_partitions_checked"], 75)

    def test_generic_synthesizer_matches_bruteforce(self):
        self.assertEqual(self.summary["kernel_mismatches"], 0)
        self.assertEqual(self.summary["observer_mismatches"], 0)
        self.assertEqual(self.summary["greatest_contract_mismatches"], 0)
        self.assertEqual(self.summary["nonblocking_mismatches"], 0)

    def test_obligation_count_uses_executed_nonblocking_checks(self):
        with patch.object(metaoracle, "_contract_nonblocking",
                          wraps=metaoracle._contract_nonblocking) as checked:
            summary = run_metaoracle(0)
        # Each explicit receipt plant has its own additional direct-path check.
        generic_checks = checked.call_count - summary["receipt_partitions_checked"]
        self.assertEqual(summary["nonblocking_candidates_checked"], generic_checks)
        self.assertEqual(generic_checks, 672)
        self.assertEqual(summary["contract_candidates_checked"], 1188)
        self.assertEqual(self.summary["counted_obligations"],
                         4 * 486 + 1188 + 672 + 75 + 6 + 2)

    def test_quantifier_and_eligibility_mutants_are_killed(self):
        self.assertGreater(self.summary["existential_mutant_counterexamples"], 0)
        self.assertGreater(self.summary["eligibility_mutant_counterexamples"], 0)
        self.assertIsNotNone(self.summary["first_existential_mutant_witness"])

    def test_receipt_partitions_use_explicit_labelled_plants(self):
        self.assertEqual(self.summary["receipt_plant_mismatches"], 0)
        rows = self.summary["receipt_partition_results"]
        self.assertEqual(len(rows), 75)
        self.assertTrue(all(row["exact"] for row in rows))
        self.assertTrue(all(
            row["direct_nonblocking_exists"] == row["zero_isolated"]
            for row in rows
        ))

    def test_l1_l4_counterexample_and_complexity_sanity(self):
        witness = self.summary["lifting_counterexample"]
        self.assertTrue(witness["L1_through_L4"])
        self.assertTrue(witness["actual_grant_safety"])
        self.assertFalse(witness["L6"])
        self.assertFalse(witness["full_correctness"])
        self.assertEqual(witness["ineligible_in_epsilon"], ["s0"])
        self.assertTrue(self.summary["complexity_sanity"]["exact"])


if __name__ == "__main__":
    unittest.main()
