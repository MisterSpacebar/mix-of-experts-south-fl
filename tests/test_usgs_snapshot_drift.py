"""Regression tests for live USGS time-series metadata snapshot drift."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_parameter_periods import combine, reconcile_snapshots
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.periods import PERIOD_COLUMNS, _row
from southfl.sources import STATION_COLUMNS

OLD_AT = "2026-11-23T01:00:00+00:00"
NEW_AT = "2026-11-25T01:00:00+00:00"


def series():
    return _row(
        "usgs_water", "USGS-0229070825", "2bba25271b8d423aba985fac76892dc9",
        code="00065", name="Gage height", concept="water_level", unit="ft",
        series_type="Instantaneous", statistic_id="00011",
        primary="Primary", gap_interval="PT1H12M",
        begin="2020-07-16T19:30:00+00:00",
        end="2026-11-22T09:15:00+00:00",
        evidence="time_series_first_last_metadata",
        note="Time series can contain substantial gaps; metadata is not completeness",
        url="https://api.waterdata.usgs.gov/query-old",
        region="central_south_biscayne", inventory="yes",
    )


def advanced(**changes):
    row = dict(series())
    row.update(end_utc="2026-11-24T08:15:00+00:00",
               region_query="everglades_interior/tile_02",
               source_url="https://api.waterdata.usgs.gov/query-new")
    row.update(changes)
    return row


class DriftPolicyTests(unittest.TestCase):
    def test_advancing_timestamp_is_audited_not_quarantined(self):
        rows, problems, logs, same = reconcile_snapshots(
            [series()], [advanced()], OLD_AT, NEW_AT)
        self.assertEqual(len(rows), 1)
        self.assertEqual(problems, [])
        self.assertEqual(same, 0)
        self.assertEqual(rows[0]["end_utc"], advanced()["end_utc"])
        self.assertEqual(rows[0]["source_url"], advanced()["source_url"])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["previous_end_utc"], series()["end_utc"])
        self.assertEqual(logs[0]["expanded_end_utc"], advanced()["end_utc"])
        self.assertEqual(logs[0]["elapsed_hours"], "47.000")

    def test_identical_metadata_across_regions_deduplicates(self):
        duplicate = dict(series(), source_url="https://new-query",
                         region_query="other_region")
        rows, problems, logs, same = reconcile_snapshots(
            [series()], [duplicate], OLD_AT, NEW_AT)
        self.assertEqual(len(rows), 1)
        self.assertEqual(problems, [])
        self.assertEqual(logs, [])
        self.assertEqual(same, 1)

    def test_retrograde_end_date_still_quarantined(self):
        old = advanced()
        newer = series()
        rows, problems, logs, _ = reconcile_snapshots(
            [old], [newer], OLD_AT, NEW_AT)
        self.assertEqual(rows, [])
        self.assertEqual(len(problems), 1)
        self.assertEqual(logs, [])

    def test_changed_start_date_is_real_conflict(self):
        rows, problems, logs, _ = reconcile_snapshots(
            [series()], [advanced(begin_utc="2020-07-17T00:00:00+00:00")],
            OLD_AT, NEW_AT)
        self.assertEqual(rows, [])
        self.assertEqual(len(problems), 1)
        self.assertEqual(logs, [])

    def test_changed_units_or_qa_fields_remain_conflicts(self):
        for field, value in (("unit", "m"), ("primary_status", "Secondary"),
                             ("parameter_code", "00060"),
                             ("data_gap_interval", "PT2H")):
            with self.subTest(field=field):
                rows, problems, logs, _ = reconcile_snapshots(
                    [series()], [advanced(**{field: value})], OLD_AT, NEW_AT)
                self.assertEqual(rows, [])
                self.assertEqual(len(problems), 1)
                self.assertEqual(logs, [])

    def test_non_usgs_end_advance_not_reconciled(self):
        old = dict(series(), dataset_id="epa_wqp")
        new = dict(advanced(), dataset_id="epa_wqp")
        rows, problems, logs, _ = reconcile_snapshots([old], [new])
        self.assertEqual((len(rows), len(problems), len(logs)), (0, 1, 0))

    def test_invalid_or_naive_timestamps_quarantined(self):
        for end in ("not-a-date", "2026-11-24T08:15:00", "",
                    "2020-01-01T00:00:00+00:00"):
            with self.subTest(end=end):
                rows, problems, logs, _ = reconcile_snapshots(
                    [series()], [advanced(end_utc=end)], OLD_AT, NEW_AT)
                self.assertEqual((len(rows), len(problems), len(logs)), (0, 1, 0))

    def test_time_retrieval_out_of_order_quarantined(self):
        rows, problems, logs, _ = reconcile_snapshots(
            [series()], [advanced()], NEW_AT, OLD_AT)
        self.assertEqual((len(rows), len(problems), len(logs)), (0, 1, 0))

    def test_end_cannot_postdate_source_snapshot(self):
        rows, problems, logs, _ = reconcile_snapshots(
            [series()], [advanced(end_utc="2026-11-28T01:00:00+00:00")],
            OLD_AT, NEW_AT)
        self.assertEqual((len(rows), len(problems), len(logs)), (0, 1, 0))

    def test_duplicate_key_within_input_snapshot_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate canonical series"):
            reconcile_snapshots([series(), series()], [])


class FileIntegrationTests(unittest.TestCase):
    def _inputs(self, root):
        prev, new, dest = (root/x for x in ("previous", "expanded", "combined_v4"))
        prev.mkdir()
        new.mkdir()
        station_path = root/"stations.csv"
        write_csv(station_path, [{
            "dataset_id": "usgs_water", "site_id": series()["site_id"],
            "latitude": "25.5", "longitude": "-80.4",
            "regions": "central_south_biscayne;everglades_interior"
        }], STATION_COLUMNS)
        write_csv(prev/"parameter_periods.csv", [series()], PERIOD_COLUMNS)
        write_csv(new/"parameter_periods.csv", [advanced()], PERIOD_COLUMNS)
        for path, stamp in ((prev, OLD_AT), (new, NEW_AT)):
            (path/"parameter_manifest.json").write_text(json.dumps({
                "n_failed_requests": 0, "n_conflicting_metadata_records": 0,
                "n_parameter_periods": 1, "retrieved_at_utc": stamp,
            }), encoding="utf-8")
        return prev, new, station_path, dest

    def test_completed_merge_has_full_provenance_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            prev, new, stations, out = self._inputs(Path(directory))
            report = combine(prev, new, stations, out)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["n_parameter_periods"], 1)
            self.assertEqual(report["n_reconciled_usgs_end_advances"], 1)
            self.assertEqual(report["n_conflicting_metadata_records"], 0)
            self.assertFalse(report["observation_coverage_verified"])
            audit = read_csv(out/"time_series_end_advances.csv")
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0]["expanded_source_url"], advanced()["source_url"])
            self.assertEqual(len(read_csv(out/"concept_summary.csv")), 2)
            self.assertEqual(read_csv(out/"parameter_periods.csv")[0]["end_utc"],
                             advanced()["end_utc"])
            self.assertEqual(len(read_csv(out/"parameter_metadata_conflicts.csv")), 0)

    def test_regression_preserves_previous_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            prev, new, stations, out = self._inputs(Path(directory))
            original = (prev/"parameter_periods.csv").read_bytes()
            combine(prev, new, stations, out)
            self.assertEqual((prev/"parameter_periods.csv").read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "nonempty"):
                combine(prev, new, stations, out)

    def test_manifest_count_mismatch_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            prev, new, stations, out = self._inputs(Path(directory))
            (prev/"parameter_manifest.json").write_text(json.dumps({
                "n_failed_requests": 0, "n_conflicting_metadata_records": 0,
                "n_parameter_periods": 2,
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "count differs"):
                combine(prev, new, stations, out)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
