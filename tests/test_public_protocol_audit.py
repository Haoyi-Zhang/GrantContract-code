"""Integrity tests for the pinned public-protocol source audit."""
from __future__ import annotations

import csv
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "public_protocol_audit.csv"
COMMIT = "0c5c6d8e06ecf1a1d6fed3e6097e496850306dc0"


class PublicProtocolAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with AUDIT.open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_rows_are_unique_and_pinned(self):
        self.assertEqual(len(self.rows), 5)
        self.assertEqual(len({row["fact_id"] for row in self.rows}), len(self.rows))
        self.assertTrue(all(row["repository"] == "TUM-DSE/vCXLGen" for row in self.rows))
        self.assertTrue(all(row["commit"] == COMMIT for row in self.rows))
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", row["blob_sha"])
                            for row in self.rows))
        self.assertTrue(all(int(row["start_line"]) <= int(row["end_line"])
                            for row in self.rows))

    def test_audit_covers_response_counter_and_completion(self):
        text = " ".join(row["concrete_fact"] + " " + row["source_anchor"]
                        for row in self.rows)
        for required in ("ACK", "ALL_ACKS", "NumIntPendingAcks", "zero"):
            self.assertIn(required, text)

    def test_every_fact_is_explicitly_non_lifting(self):
        self.assertTrue(all("not a lift" in row["scope_limit"].lower()
                            for row in self.rows))
        self.assertTrue(all("no source is redistributed" in row["license_note"].lower()
                            for row in self.rows))
        self.assertTrue(all(row["evidence_role"] == "qualitative architecture anchor only"
                            for row in self.rows))


if __name__ == "__main__":
    unittest.main()
