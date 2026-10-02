"""Regression for the L1--L4 versus L6 transfer distinction."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lifting_counterexample import evaluate_l1_l4_counterexample  # noqa: E402


class LiftingCounterexampleTests(unittest.TestCase):
    def test_l1_l4_do_not_imply_statewise_correctness(self) -> None:
        result = evaluate_l1_l4_counterexample()
        self.assertTrue(result["L1_through_L4"])
        self.assertTrue(result["actual_grant_safety"])
        self.assertEqual(result["epsilon_knowledge"], ["s0", "s1"])
        self.assertEqual(result["ineligible_in_epsilon"], ["s0"])
        self.assertTrue(result["abstract_cstar_enables"])
        self.assertFalse(result["L6"])
        self.assertFalse(result["full_correctness"])

    def test_counterexample_is_exactly_the_declared_small_graph(self) -> None:
        result = evaluate_l1_l4_counterexample()
        self.assertEqual(result["abstract"]["grant"], ["q", "g"])
        self.assertEqual(result["concrete"]["hidden_step"], ["s0", "s1"])
        self.assertEqual(result["concrete"]["grant"], ["s1", "gB"])
        self.assertEqual(result["alpha"], {"s0": "q", "s1": "q", "gB": "g"})
        self.assertEqual(result["rank"], {"s0": 1, "s1": 0})


if __name__ == "__main__":
    unittest.main()
