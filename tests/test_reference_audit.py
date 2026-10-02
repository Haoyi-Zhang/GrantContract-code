import csv
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT = ROOT / "reference_audit.csv"


class ReferenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with AUDIT.open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))
        cls.by_key = {row["key"]: row for row in cls.rows}

    def test_inventory_is_unique_complete_and_passed(self):
        self.assertGreaterEqual(len(self.rows), 30)
        self.assertLessEqual(len(self.rows), 45)
        self.assertEqual(len(self.by_key), len(self.rows))
        self.assertTrue(all(row["status"] == "PASS" for row in self.rows))
        self.assertTrue(all(row["title"] and row["authors"] and row["venue"]
                            and row["year"] and row["verification_source"]
                            for row in self.rows))
        self.assertTrue(all(re.fullmatch(r"20\d{2}|19\d{2}", row["year"])
                            for row in self.rows))
        self.assertTrue(all(row["verification_source"].startswith("https://")
                            for row in self.rows))
        self.assertFalse(any("placeholder" in row["verification_source"].lower()
                             for row in self.rows))

    def test_titles_and_dois_are_unique(self):
        titles = [re.sub(r"\W+", "", row["title"].casefold()) for row in self.rows]
        self.assertEqual(len(titles), len(set(titles)))
        dois = [row["doi_or_identifier"].casefold() for row in self.rows
                if row["doi_or_identifier"].startswith("10.")]
        self.assertEqual(len(dois), len(set(dois)))
        self.assertTrue(all(re.fullmatch(r"10\.\d{4,9}/\S+", doi) for doi in dois))

    def test_same_venue_calibration_has_twelve_tc_papers(self):
        tc_rows = [row for row in self.rows
                   if row["venue"].startswith("IEEE Transactions on Computers")]
        self.assertEqual(len(tc_rows), 12)
        self.assertTrue(all(row["doi_or_identifier"].startswith("10.1109/")
                            for row in tc_rows))

    def test_corrected_and_qualifying_records_are_pinned(self):
        heterogen = self.by_key["heterogen"]
        self.assertEqual(heterogen["venue"], "HPCA 2022")
        self.assertEqual(heterogen["pages_or_article"], "756-771")
        self.assertEqual(heterogen["doi_or_identifier"],
                         "10.1109/HPCA53966.2022.00061")

        disco = self.by_key["disco"]
        self.assertEqual(
            disco["title"],
            "DISCO: Time-Compositional Cache Coherence for Multi-Core Real-Time Embedded Systems",
        )
        self.assertEqual(disco["pages_or_article"], "1163-1177")

        self.assertEqual(self.by_key["tardis"]["pages_or_article"], "227-240")
        self.assertEqual(self.by_key["rc11corrigendum"]["venue"],
                         "Author-issued corrigendum")
        self.assertIn("not counted as a peer-reviewed paper",
                      self.by_key["rc11corrigendum"]["notes"].lower())
        artifact = self.by_key["vcxlgenartifact"]
        self.assertEqual(artifact["year"], "2026")
        self.assertIn("0c5c6d8e06ecf1a1d6fed3e6097e496850306dc0",
                      artifact["doi_or_identifier"])
        self.assertIn("not counted as a peer-reviewed paper",
                      artifact["notes"].lower())
        self.assertIn("ordinary ack", artifact["notes"].lower())
        self.assertIn("all_acks", artifact["notes"].lower())
        self.assertNotIn("mit license", artifact["verification_level"].lower())

    def test_newest_accepted_work_is_not_overread(self):
        synapse = self.by_key["synapse"]
        self.assertEqual(synapse["venue"], "MICRO 2026 (accepted)")
        self.assertEqual(synapse["pages_or_article"], "to appear")
        self.assertIn("public paper unavailable", synapse["verification_level"])
        self.assertIn("no theorem or experiment attributed", synapse["manuscript_use"])
        self.assertIn("makes no technical comparison", synapse["notes"])


if __name__ == "__main__":
    unittest.main()
