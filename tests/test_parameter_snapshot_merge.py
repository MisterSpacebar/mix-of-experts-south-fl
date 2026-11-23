"""Offline safeguards for cross-region parameter snapshot consolidation."""
import json
import tempfile
import unittest
from pathlib import Path

from southfl.net import write_csv
from southfl.sources import STATION_COLUMNS
from southfl.periods import PERIOD_COLUMNS, _row
from scripts.merge_parameter_periods import combine


class ParameterSnapshotTests(unittest.TestCase):
    def test_overlapping_series_deduplicated_and_resummarized(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous, expanded, out = (root/x for x in ("previous", "expanded", "out"))
            previous.mkdir()
            expanded.mkdir()
            stations = root/"stations.csv"
            write_csv(stations, [{
                "dataset_id": "usgs_water", "site_id": "USGS-1",
                "latitude": 26.5, "longitude": -80.8,
                "regions": "everglades_interior;everglades_agricultural_area"
            }], STATION_COLUMNS)
            a = _row("usgs_water", "USGS-1", "ts",
                     code="00300", concept="dissolved_oxygen",
                     begin="2020-01-01", end="2026-10-01",
                     evidence="time_series_first_last_metadata",
                     region="north")
            b = dict(a, region_query="west", source_url="https://some-other-request")
            write_csv(previous/"parameter_periods.csv", [a], PERIOD_COLUMNS)
            write_csv(expanded/"parameter_periods.csv", [b], PERIOD_COLUMNS)
            for source in (previous, expanded):
                (source/"parameter_manifest.json").write_text(json.dumps({
                    "n_failed_requests": 0, "n_conflicting_metadata_records": 0
                }))
            result = combine(previous, expanded, stations, out)
            self.assertEqual(result["n_parameter_periods"], 1)
            self.assertEqual(result["status"], "complete")
            from southfl.audit import read_csv
            self.assertEqual(len(read_csv(out/"concept_summary.csv")), 2)

    def test_incomplete_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b, dest = (root/x for x in ("a", "b", "out"))
            a.mkdir()
            b.mkdir()
            for path, failures in ((a, 1), (b, 0)):
                (path/"parameter_manifest.json").write_text(json.dumps({
                    "n_failed_requests": failures, "n_conflicting_metadata_records": 0
                }))
            with self.assertRaisesRegex(ValueError, "incomplete"):
                combine(a, b, root/"stations.csv", dest)


if __name__ == "__main__":
    unittest.main()
