"""Offline integration tests for batch discovery partial query behavior."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.discover_regions import batch
from southfl.sources import station


class BatchDiscoveryTests(unittest.TestCase):
    def test_conflicted_id_quarantined_while_healthy_site_survives(self):
        west = station("usgs_water", "USGS", "USGS-123", "One", 25.50, -80.3,
                       "https://api.waterdata.usgs.gov")
        east = station("usgs_water", "USGS", "USGS-123", "One", 25.55, -80.3,
                       "https://api.waterdata.usgs.gov")
        good = station("usgs_water", "USGS", "USGS-456", "Two", 25.6, -80.4,
                       "https://api.waterdata.usgs.gov")
        calls = {"count": 0}

        def fake_adapter(_bbox, conflict_sink=None):
            calls["count"] += 1
            if calls["count"] == 1:
                conflict_sink.append(dict(
                    dataset_id="usgs_water", site_id="USGS-123",
                    latitude_a=west["latitude"], longitude_a=west["longitude"],
                    latitude_b=east["latitude"], longitude_b=east["longitude"],
                    source_a=west["source_url"], source_b=east["source_url"],
                    reason="different_coordinates_for_canonical_id"))
                return [good]
            if calls["count"] == 2:
                return [west]
            return [good]

        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("scripts.discover_regions.ADAPTERS", {"usgs": fake_adapter}):
                result = batch(["usgs"], directory)
            self.assertEqual(result["n_quarantined_site_ids"], 1)
            self.assertEqual(result["n_failed_queries"], 1)
            self.assertEqual(result["n_unique_stations"], 1)
            with (Path(directory)/"stations.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([r["site_id"] for r in rows], ["USGS-456"])
            with (Path(directory)/"coordinate_conflicts.csv").open(newline="") as f:
                problems = list(csv.DictReader(f))
            self.assertEqual(len(problems), 1)


if __name__ == "__main__":
    unittest.main()
