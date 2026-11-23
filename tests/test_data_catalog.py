import json
import tempfile
import unittest
from pathlib import Path

from scripts.catalog import CATALOG, validate
from scripts.fetch_coops import request_observations, validate_date


class CatalogTests(unittest.TestCase):
    def test_registry(self):
        records = validate()
        self.assertGreaterEqual(len(records), 10)
        self.assertIn("noaa_coops", [r["id"] for r in records])

    def test_duplicate_ids_rejected(self):
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        data["datasets"].append(dict(data["datasets"][0]))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "dupe.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate ID"):
                validate(path)

    def test_invalid_station_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError, "numeric"):
            request_observations("bad-station", "20260101", "20260102")

    def test_invalid_date_rejected(self):
        with self.assertRaises(Exception):
            validate_date("2026-01-01")

    def test_inverted_range_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError, "end"):
            request_observations("8724580", "20260107", "20260101")


if __name__ == "__main__":
    unittest.main()
