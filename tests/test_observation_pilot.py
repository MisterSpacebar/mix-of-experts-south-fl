"""Mocked agency ingestion, pilot planning, and observed-only QA tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from southfl.net import AcquisitionError, write_csv
from southfl.observations import (
    COLS, _row, usgs_observations, wqp_observations, coops_observations)
from southfl.coverage import coverage
from southfl.selection import PLAN_COLUMNS, plan
from scripts.fetch_observation_pilot import run, validate_tasks


class SourceObservationTests(unittest.TestCase):
    @patch("southfl.observations.get_json")
    def test_usgs_continuous_preserves_qa_and_utc(self, request):
        request.return_value = {"features": [{
            "id": "unique-source-result",
            "properties": {
                "monitoring_location_id": "USGS-1",
                "parameter_code": "00300", "time_series_id": "ts",
                "time": "2026-10-01T12:00:00-04:00", "value": "4.2",
                "unit_of_measure": "mg/L", "approval_status": "Provisional",
                "qualifier": "E",
            }}], "links": []}
        rows, urls = usgs_observations("USGS-1", "00300", "2026-10-01",
                                       "2026-10-03", "dissolved_oxygen")
        self.assertEqual(rows[0]["timestamp_utc"], "2026-10-01T16:00:00Z")
        self.assertEqual(rows[0]["approval_status"], "Provisional")
        self.assertEqual(rows[0]["value"], "4.2")
        self.assertIn("time=2026-10-01%2F2026-10-03", urls[0])

    @patch("southfl.observations.get_json")
    def test_usgs_daily_does_not_fake_utc(self, request):
        request.return_value = {"features": [{
            "properties": {
                "monitoring_location_id": "USGS-1", "parameter_code": "00060",
                "time": "2026-10-01", "value": "10",
                "approval_status": "Approved"}}], "links": []}
        rows, _ = usgs_observations("USGS-1", "00060", "2026-10-01",
                                    "2026-10-02", "discharge", mode="daily")
        self.assertEqual(rows[0]["timestamp_utc"], "")
        self.assertEqual(rows[0]["sample_date"], "2026-10-01")
        self.assertEqual(rows[0]["time_basis"], "source_daily_calendar_date")

    @patch("southfl.observations.get_json")
    def test_usgs_unexpected_site_rejected(self, request):
        request.return_value = {"features": [{
            "properties": {"monitoring_location_id": "USGS-OTHER",
                           "parameter_code": "00300",
                           "time": "2026-10-01", "value": "1"}}], "links": []}
        with self.assertRaisesRegex(AcquisitionError, "mismatch"):
            usgs_observations("USGS-1", "00300", "2026-10-01",
                              "2026-10-02", "dissolved_oxygen", mode="daily")

    @patch("southfl.observations.get_csv")
    def test_wqp_non_detect_not_zero(self, request):
        request.return_value = [{
            "MonitoringLocationIdentifier": "ORG-1",
            "ActivityStartDate": "2026-09-01",
            "CharacteristicName": "Phosphorus",
            "ResultMeasureValue": "",
            "ResultDetectionConditionText": "Not Detected",
            "ResultMeasure/MeasureUnitCode": "mg/L",
            "ActivityIdentifier": "A-1", "ResultIdentifier": "R-1",
        }]
        rows, _ = wqp_observations("ORG-1", "Phosphorus", "2026-01-01",
                                   "2026-10-01", "phosphorus_unspecified_fraction")
        self.assertEqual(rows[0]["value"], "")
        self.assertEqual(rows[0]["detection_condition"], "Not Detected")
        self.assertEqual(rows[0]["time_basis"], "source_local_date_not_utc")
        self.assertEqual(rows[0]["activity_id"], "A-1")

    @patch("scripts.fetch_coops.request_observations")
    def test_coops_datum_and_utc(self, request):
        request.return_value = ([{
            "timestamp_utc": "2026-10-01T00:00:00Z",
            "water_level_m": 0.41, "quality_flag": "0"}], "https://api.example.com")
        rows, _ = coops_observations("8724580", "2026-10-01", "2026-10-02")
        self.assertEqual(rows[0]["vertical_datum"], "MLLW")
        self.assertEqual(rows[0]["unit"], "m")
        self.assertEqual(rows[0]["value"], "0.41")


class PlanAndCoverageTests(unittest.TestCase):
    def test_region_balanced_selection_and_no_duplicate_sites(self):
        locations = [
            {"dataset_id": "usgs_water", "site_id": "USGS-1",
             "regions": "everglades_interior"},
            {"dataset_id": "epa_wqp", "site_id": "WQP-1",
             "regions": "lake_okeechobee"},
            {"dataset_id": "noaa_coops", "site_id": "8724580",
             "regions": "lower_keys"},
        ]
        series = [
            {"dataset_id": "usgs_water", "site_id": "USGS-1", "concept": "dissolved_oxygen",
             "parameter_code": "00300", "parameter_name": "DO", "series_id": "ts-1",
             "year": "", "end_utc": "2026-10-05T00:00:00Z",
             "begin_utc": "2025-10-01", "evidence": "time_series_first_last_metadata"},
            {"dataset_id": "epa_wqp", "site_id": "WQP-1",
             "concept": "phosphorus_unspecified_fraction",
             "parameter_code": "", "parameter_name": "Phosphorus", "series_id": "yr2025",
             "year": "2025", "end_utc": "", "begin_utc": "",
             "evidence": "annual_result_and_activity_counts"},
            {"dataset_id": "noaa_coops", "site_id": "8724580", "concept": "water_level",
             "parameter_code": "", "parameter_name": "Water Level",
             "series_id": "coops", "year": "", "end_utc": "", "begin_utc": "",
             "evidence": "station_class_only"},
        ]
        selected = plan(series, locations, "2026-10-31", max_total=6)
        self.assertEqual(len(selected), 3)
        self.assertEqual({x["dataset_id"] for x in selected},
                         {"usgs_water", "epa_wqp", "noaa_coops"})
        self.assertTrue(all(x["selection_status"] == "candidate_not_verified" for x in selected))

    def test_observation_qa_not_completeness(self):
        task = dict(dataset_id="epa_wqp", site_id="ORG-1", concept="salinity",
                    start_date="2026-01-01", end_date="2026-10-01")
        r = _row(dataset_id="epa_wqp", site_id="ORG-1", concept="salinity",
                 sample_date="2026-03-01", measurement_type="discrete_sample",
                 time_basis="source_local_date_not_utc", value="3.2", unit="ppt",
                 result_id="R-1")
        rows = coverage([r, dict(r)], [task])
        self.assertEqual(rows[0]["n_distinct_sample_dates"], 1)
        self.assertEqual(rows[0]["possible_duplicate_result_ids"], 1)
        self.assertEqual(rows[0]["observed_completeness"], "")

    def test_dry_run_makes_no_request(self):
        with tempfile.TemporaryDirectory() as d:
            plan_file = Path(d)/"plan.csv"
            task = dict(dataset_id="usgs_water", site_id="USGS-1",
                        region="everglades_interior", concept="water_level",
                        parameter_code="00065", parameter_name="gage height",
                        start_date="2026-10-01", end_date="2026-10-07",
                        usgs_mode="continuous", evidence="metadata",
                        last_date_hint="2026-10-07",
                        selection_status="candidate_not_verified")
            write_csv(plan_file, [task], PLAN_COLUMNS)
            with patch("scripts.fetch_observation_pilot.fetch_task") as fetcher:
                result = run(plan_file, Path(d)/"download", execute=False)
            self.assertEqual(result["status"], "dry_run")
            fetcher.assert_not_called()
            self.assertFalse((Path(d)/"download").exists())

    def test_partial_acquisition_retains_valid_observations(self):
        with tempfile.TemporaryDirectory() as d:
            plan_file = Path(d)/"plan.csv"
            tasks = [
                dict(dataset_id="usgs_water", site_id=f"USGS-{i}", region="lake_okeechobee",
                     concept="discharge", parameter_code="00060",
                     parameter_name="Streamflow", start_date="2026-10-01",
                     end_date="2026-10-07", usgs_mode="daily",
                     evidence="time_series_first_last_metadata",
                     last_date_hint="2026-10-07", selection_status="candidate_not_verified")
                for i in (1, 2)]
            write_csv(plan_file, tasks, PLAN_COLUMNS)
            good = _row(dataset_id="usgs_water", site_id="USGS-1",
                        concept="discharge", measurement_type="daily_statistic",
                        sample_date="2026-10-01", time_basis="source_daily_calendar_date",
                        value="2", unit="ft3/s")
            with patch("scripts.fetch_observation_pilot.fetch_task", side_effect=[
                        ([good], ["https://api.example.com"]), AcquisitionError("offline")]):
                manifest = run(plan_file, Path(d)/"run", execute=True)
            self.assertEqual(manifest["n_failed_tasks"], 1)
            self.assertEqual(manifest["n_observations"], 1)
            self.assertEqual(manifest["requests"][1]["status"], "failed")
            self.assertTrue((Path(d)/"run/observations.csv").exists())


if __name__ == "__main__":
    unittest.main()
