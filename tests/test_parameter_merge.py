"""Offline tests for safe partial-manifest consolidation."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_parameter_discoveries import merge
from southfl.periods import PERIOD_COLUMNS, _row
from southfl.net import write_csv
from southfl.sources import STATION_COLUMNS


def write_case(root, missing_site=False, extra_failure=False):
    root = Path(root)
    base, supplement = root/"base", root/"supplement"
    base.mkdir()
    supplement.mkdir()
    stations = root/"stations.csv"
    station_rows = [
        {"dataset_id": "noaa_coops", "site_id": "8723214",
         "latitude": 25.2, "longitude": -80.3, "regions": "upper_keys"},
        {"dataset_id": "noaa_coops", "site_id": "8724580",
         "latitude": 24.6, "longitude": -81.8, "regions": "lower_keys"},
        {"dataset_id": "usgs_water", "site_id": "USGS-123",
         "latitude": 25.7, "longitude": -80.2, "regions": "north_biscayne"},
    ]
    write_csv(stations, station_rows, STATION_COLUMNS)
    write_csv(base/"parameter_periods.csv", [
        _row("usgs_water", "USGS-123", "test-series",
             concept="dissolved_oxygen",
             evidence="time_series_first_last_metadata")], PERIOD_COLUMNS)
    coops_rows = [_row("noaa_coops", sid, sid+"|water_level_candidate",
                       concept="water_level", evidence="station_class_only")
                  for sid in (["8723214"] if missing_site else ["8723214", "8724580"])]
    write_csv(supplement/"parameter_periods.csv", coops_rows, PERIOD_COLUMNS)
    first = {"source": "coops", "region": "domain", "subtype": "waterlevel_station",
             "status": "failed", "n_rows": 0}
    other = {"source": "usgs", "region": "north_biscayne", "subtype": "time_series_metadata",
             "status": "failed" if extra_failure else "success", "n_rows": 1}
    (base/"parameter_manifest.json").write_text(json.dumps({
        "sources": ["coops", "usgs"], "n_failed_requests": 1,
        "n_conflicting_metadata_records": 0, "attempts": [first, other],
        "n_raw_metadata_rows": 1
    }), encoding="utf-8")
    (supplement/"parameter_manifest.json").write_text(json.dumps({
        "sources": ["coops"], "n_failed_requests": 0,
        "n_conflicting_metadata_records": 0,
        "n_raw_metadata_rows": len(coops_rows),
        "attempts": [dict(first, status="success", n_rows=len(coops_rows))],
    }), encoding="utf-8")
    return base, supplement, stations, root/"consolidated"


class ConsolidationTests(unittest.TestCase):
    def test_merges_only_replaced_noaa_queries(self):
        with tempfile.TemporaryDirectory() as d:
            base, supplement, stations, dest = write_case(d)
            report = merge(base, supplement, stations, dest)
            self.assertEqual(report["n_failed_requests"], 0)
            self.assertEqual(report["n_parameter_periods"], 3)
            self.assertFalse(report["observation_coverage_verified"])
            with (dest/"parameter_periods.csv").open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual({x["dataset_id"] for x in rows},
                             {"usgs_water", "noaa_coops"})
            with (dest/"parameter_manifest.json").open(encoding="utf-8") as f:
                self.assertEqual(json.load(f)["n_raw_metadata_rows"], 3)

    def test_missing_noaa_station_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            args = write_case(d, missing_site=True)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                merge(*args)

    def test_unrelated_failed_query_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            args = write_case(d, extra_failure=True)
            with self.assertRaisesRegex(ValueError, "base failure"):
                merge(*args)

    def test_never_overwrites_existing_data(self):
        with tempfile.TemporaryDirectory() as d:
            base, supplement, stations, dest = write_case(d)
            dest.mkdir()
            (dest/"sentinel").write_text("keep me", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nonempty"):
                merge(base, supplement, stations, dest)
            self.assertEqual((dest/"sentinel").read_text(), "keep me")


if __name__ == "__main__":
    unittest.main()
