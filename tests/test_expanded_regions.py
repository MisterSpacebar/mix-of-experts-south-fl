"""Offline tests for expanded geography, safe station merge and fast co-location."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from southfl.regions import REGIONS, regions_for
from southfl.audit import catalog_inventory, coordinate_collisions
from southfl.sources import station
from scripts.discover_regions import batch, tiles_for
from scripts.merge_station_discoveries import merge_stations


class RegionalExpansionTests(unittest.TestCase):
    def test_watershed_and_coast_added(self):
        for name in ("everglades_interior", "lake_okeechobee", "big_cypress",
                     "caloosahatchee", "st_lucie_connection",
                     "southwest_everglades_coast"):
            self.assertIn(name, REGIONS)
        self.assertIn("lake_okeechobee", regions_for(27.1, -80.8))

    def test_tiles_cover_screening_box(self):
        bbox = REGIONS["lake_okeechobee"]
        tiles = list(tiles_for(bbox, 2))
        self.assertEqual(len(tiles), 4)
        self.assertEqual(min(x[0] for x in tiles), bbox[0])
        self.assertEqual(min(x[1] for x in tiles), bbox[1])
        self.assertEqual(max(x[2] for x in tiles), bbox[2])
        self.assertEqual(max(x[3] for x in tiles), bbox[3])

    def test_batch_uses_tiled_named_regions(self):
        calls = []
        def fake_source(bbox, conflict_sink=None):
            calls.append(bbox)
            return []
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict("scripts.discover_regions.ADAPTERS", {"usgs": fake_source}):
                report = batch(["usgs"], temp, regions=["lake_okeechobee"], tiles=2)
            self.assertEqual(report["n_failed_queries"], 0)
            self.assertEqual(report["tiles_per_axis"], 2)
            self.assertEqual(len(calls), 4)
            with self.assertRaisesRegex(ValueError, "nonempty"):
                batch(["usgs"], temp, regions=["lake_okeechobee"], tiles=2)

    def test_spatial_hash_comparison(self):
        a = station("usgs_water", "USGS", "USGS-1", "Near", 26.5, -81.1,
                    "https://example.com")
        b = station("epa_wqp", "EPA", "EPA-2", "Near", 26.5001, -81.1001,
                    "https://example.com")
        far = station("epa_wqp", "EPA", "EPA-3", "Far", 26.7, -81.1,
                      "https://example.com")
        matches = coordinate_collisions([a, b, far])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["site_id_a"], "USGS-1")

    def test_merge_reregions_existing_station(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            earlier, newer, dest = (root/p for p in ("old", "new", "combined"))
            old = station("usgs_water", "USGS", "USGS-1", "Inland", 27.0, -80.9,
                          "https://example.com")
            old["regions"] = ""  # station discovered before expansion
            new = station("usgs_water", "USGS", "USGS-2", "Coast", 25.7, -81.5,
                          "https://example.com")
            catalog_inventory([old], earlier)
            catalog_inventory([new], newer)
            report = merge_stations(earlier, newer, dest)
            self.assertEqual(report["combined_unique_sites"], 2)
            from southfl.audit import read_csv
            rows = read_csv(dest/"stations.csv")
            old_row = next(x for x in rows if x["site_id"] == "USGS-1")
            self.assertIn("lake_okeechobee", old_row["regions"])


if __name__ == "__main__":
    unittest.main()
