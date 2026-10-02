"""Closed-form and exhaustive small-partition tests for the receipt theorem."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from metaoracle import _rgs_partitions, evaluate_receipt_partition_plant  # noqa: E402
from parametric_bridge import raw_receipt_partition_is_complete  # noqa: E402


class ReceiptPartitionTests(unittest.TestCase):
    def test_zero_bound_needs_no_distinction(self) -> None:
        self.assertTrue(raw_receipt_partition_is_complete(0, ("ack",)))

    def test_zero_must_be_isolated_from_every_positive_count(self) -> None:
        self.assertTrue(raw_receipt_partition_is_complete(4, ("ready", "wait", "wait", "wait", "wait")))
        self.assertTrue(raw_receipt_partition_is_complete(4, (0, 1, 2, 1, 2)))
        self.assertFalse(raw_receipt_partition_is_complete(4, (0, 1, 0, 1, 1)))
        self.assertFalse(raw_receipt_partition_is_complete(4, ("ack",) * 5))

    def test_all_canonical_partitions_through_bound_four(self) -> None:
        bell = {0: 1, 1: 2, 2: 5, 3: 15, 4: 52}
        for bound, expected_count in bell.items():
            partitions = tuple(_rgs_partitions(bound + 1))
            self.assertEqual(len(partitions), expected_count)
            for symbols in partitions:
                expected = all(symbols[pending] != symbols[0]
                               for pending in range(1, bound + 1))
                self.assertEqual(
                    raw_receipt_partition_is_complete(bound, symbols),
                    expected,
                    msg=(bound, symbols),
                )

    def test_all_partitions_are_checked_on_actual_rho_labelled_plants(self) -> None:
        checked = 0
        for bound in range(5):
            for partition in _rgs_partitions(bound + 1):
                row = evaluate_receipt_partition_plant(bound, partition)
                expected = all(partition[pending] != partition[0]
                               for pending in range(1, bound + 1))
                self.assertTrue(row["exact"], msg=(bound, partition, row))
                self.assertEqual(row["direct_nonblocking_exists"], expected)
                self.assertEqual(row["generic_nonblocking_exists"], expected)
                checked += 1
        self.assertEqual(checked, 75)

    def test_invalid_symbol_vector_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            raw_receipt_partition_is_complete(2, (0, 1))
        with self.assertRaises(ValueError):
            raw_receipt_partition_is_complete(-1, ())


if __name__ == "__main__":
    unittest.main()
