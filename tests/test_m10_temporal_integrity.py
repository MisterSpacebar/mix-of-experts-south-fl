"""Regression tests for explicit UTC intervals and observed-only boundary recovery."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from southfl.observations import usgs_observations
from southfl.net import AcquisitionError
from southfl.temporal_integrity import verify_historical_hash, window_coverage
from scripts.recover_usgs_boundaries import merge_rows
from test_m7_history import task, obs


def feature(stamp):
    return {"properties": {"monitoring_location_id": "USGS-1",
            "parameter_code": "00480", "time_series_id": "ts-1",
            "time": stamp, "value": "4.0", "unit_of_measure": "ppt"}}


class TemporalIntegrityTests(unittest.TestCase):
    @patch("southfl.observations.get_json")
    def test_inclusive_midnight_trim_and_end_day_retained(self, fetch):
        fetch.return_value = {"features": [
            feature("2026-10-01T00:00:00Z"),
            feature("2026-10-14T23:45:00Z"),
            feature("2026-10-15T00:00:00Z")], "links": []}
        rows, urls = usgs_observations("USGS-1", "00480", "2026-10-01",
                                      "2026-10-14", "salinity", mode="continuous",
                                      series_id_filter="ts-1")
        self.assertEqual(parse_qs(urlsplit(urls[0]).query)["time"],
                         ["2026-10-01T00:00:00Z/2026-10-15T00:00:00Z"])
        self.assertEqual([r["sample_date"] for r in rows],
                         ["2026-10-01", "2026-10-14"])

    @patch("southfl.observations.get_json")
    def test_other_out_of_window_record_rejected(self, fetch):
        fetch.return_value = {"features": [feature("2026-10-15T00:15:00Z")],
                              "links": []}
        with self.assertRaisesRegex(AcquisitionError, "outside"):
            usgs_observations("USGS-1", "00480", "2026-10-14",
                              "2026-10-14", "salinity", mode="continuous")

    @patch("southfl.observations.get_json")
    def test_daily_query_unchanged(self, fetch):
        fetch.return_value = {"features": [], "links": []}
        _, urls = usgs_observations("USGS-1", "00480", "2026-10-01",
                                    "2026-10-14", "salinity")
        self.assertEqual(parse_qs(urlsplit(urls[0]).query)["time"],
                         ["2026-10-01/2026-10-14"])

    def test_endpoint_coverage_includes_empty_days(self):
        report = window_coverage(task(), [obs(day="2026-10-14", hour=0),
                                           obs(day="2026-10-14", hour=23)])
        self.assertEqual(len(report[0]["days"]), 14)
        self.assertEqual(report[0]["days"][0]["n_distinct_instants"], 0)
        self.assertEqual(report[0]["days"][-1]["span_hours"], 23)

    def test_repair_merge_retains_original_and_rejects_conflict(self):
        from scripts.recover_usgs_boundaries import key
        original = obs(day="2026-10-14", hour=0)
        rows = {key(original): original}
        self.assertEqual(merge_rows(rows, [original, obs(day="2026-10-14", hour=12)],
                                    task(), "2026-10-14"), 1)
        self.assertEqual(len(rows), 2)
        with self.assertRaisesRegex(ValueError, "changed"):
            merge_rows(rows, [obs(day="2026-10-14", hour=0, value="99")],
                       task(), "2026-10-14")
        with self.assertRaisesRegex(ValueError, "boundary day"):
            merge_rows(rows, [obs(day="2026-10-13")], task(), "2026-10-14")

    def test_hash_only_exact_or_eol_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"source.csv"
            p.write_bytes(b"a,b\n1,2\n")
            expected = hashlib.sha256(b"a,b\r\n1,2\r\n").hexdigest()
            self.assertEqual(verify_historical_hash(p, expected)["match"],
                             "reconstructed_crlf")
            p.write_bytes(b"a,b\n1,3\n")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_historical_hash(p, expected)
