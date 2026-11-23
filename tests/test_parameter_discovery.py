"""Offline parameter-period discovery contract tests (no API calls)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from southfl.net import AcquisitionError
from southfl.parameters import usgs_concept, wqp_concept
from southfl.periods import (
    coops_periods, ndbc_periods, usgs_periods, wqp_periods, _row)
from scripts.discover_parameters import run, unique_periods, concept_summary


def usgs_feature(site, code="00300", series="ts-1", begin="2019-01-01T00:00:00Z"):
    return {"id": series, "properties": {
        "monitoring_location_id": site, "time_series_id": series,
        "parameter_code": code, "parameter_name": "Dissolved oxygen",
        "begin": begin, "end": "2026-01-01T00:00:00Z",
        "unit_of_measure": "mg/L", "computation_identifier": "Instantaneous",
        "statistic_id": "00003", "sublocation_identifier": "surface",
        "primary": "Primary", "data_gap_interval": "PT1H"},
        "geometry": {"type": "Point", "coordinates": [-80.2, 25.7]}}


def write_stations(path):
    headers = ["dataset_id", "provider", "site_id", "site_name", "latitude",
               "longitude", "regions", "source_url", "retrieved_at_utc",
               "location_type", "coverage_status"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, headers)
        w.writeheader()
        w.writerows([dict(dataset_id="usgs_water", site_id="USGS-123",
                          latitude="25.7", longitude="-80.2",
                          regions="central_south_biscayne")])


class MappingTests(unittest.TestCase):
    def test_usgs_parameter_codes(self):
        self.assertEqual(usgs_concept("00300"), "dissolved_oxygen")
        self.assertEqual(usgs_concept("00065"), "water_level")
        self.assertEqual(usgs_concept("00600"), "nitrogen_total")

    def test_conservative_nutrient_names(self):
        self.assertEqual(wqp_concept("Nitrogen"), "nitrogen_unspecified_fraction")
        self.assertEqual(wqp_concept("Nitrate + Nitrite"), "nitrate_nitrite")
        self.assertEqual(wqp_concept("Phosphorus"), "phosphorus_unspecified_fraction")
        self.assertEqual(wqp_concept("Temperature, water"), "water_temperature")


class AdapterTests(unittest.TestCase):
    @patch("southfl.periods.get_json")
    def test_usgs_filter_and_source_metadata(self, mock):
        mock.return_value = {
            "features": [usgs_feature("USGS-123"), usgs_feature("USGS-999", series="ts-2")],
            "links": []}
        rows = usgs_periods((-80.4, 25.4, -80.1, 26.0), {"USGS-123"}, "north_biscayne")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["site_id"], "USGS-123")
        self.assertEqual(rows[0]["concept"], "dissolved_oxygen")
        self.assertEqual(rows[0]["begin_utc"], "2019-01-01T00:00:00Z")
        self.assertEqual(rows[0]["end_utc"], "2026-01-01T00:00:00Z")
        self.assertEqual(rows[0]["evidence"], "time_series_first_last_metadata")
        self.assertEqual(rows[0]["n_results"], "")
        self.assertEqual(rows[0]["statistic_id"], "00003")
        self.assertEqual(rows[0]["sublocation_identifier"], "surface")
        self.assertEqual(rows[0]["primary_status"], "Primary")
        self.assertEqual(rows[0]["data_gap_interval"], "PT1H")

    @patch("southfl.periods.get_json")
    def test_usgs_pagination_cycle_fails(self, mock):
        mock.return_value = {"features": [], "links": [
            {"rel": "next", "href": "?bbox=-80.4,25.4,-80.1,26.0&limit=1&f=json"}]}
        # A never-ending sequence must NOT be treated as completed coverage.
        with self.assertRaisesRegex(AcquisitionError, "page cap|cycle"):
            usgs_periods((-80.4, 25.4, -80.1, 26.0), {"USGS-123"},
                         max_pages=2, limit=1)

    @patch("southfl.periods.get_csv")
    def test_wqp_annual_counts(self, mock):
        mock.return_value = [{
            "MonitoringLocationIdentifier": "ORG-123",
            "CharacteristicName": "Phosphorus", "YearSummarized": "2024",
            "ActivityCount": "4", "ResultCount": "7",
            "Provider": "STORET", "OrganizationIdentifier": "ORG",
        }]
        rows = wqp_periods((-81, 24, -80, 26), {"ORG-123"}, characteristic_type="Nutrient")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["n_activities"], "4")
        self.assertEqual(rows[0]["concept"], "phosphorus_unspecified_fraction")
        self.assertEqual(rows[0]["year"], "2024")

    @patch("southfl.periods.get_csv")
    def test_wqp_schema_drift_fails(self, mock):
        mock.return_value = [{"some_other_header": "value"}]
        with self.assertRaisesRegex(AcquisitionError, "schema mismatch"):
            wqp_periods((-81, 24, -80, 26), {"ORG-123"})

    @patch("southfl.periods.get_json")
    def test_coops_established_is_not_observation_start(self, mock):
        mock.return_value = {"id": "8724580", "details": {
            "established": "1950-01-01", "removed": ""}}
        rows = coops_periods({"8724580"})
        self.assertEqual(rows[0]["begin_utc"], "")
        self.assertEqual(rows[0]["evidence"], "station_class_only")
        self.assertIn("1950-01-01", rows[0]["quality_note"])

    @patch("southfl.periods.get_json")
    def test_coops_wrapped_single_station(self, mock):
        mock.return_value = {"count": 1, "stations": [
            {"id": "8723214", "name": "South Florida",
             "details": {"established": "1964-05-01", "removed": ""}}], "self": None}
        rows = coops_periods({"8723214"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["site_id"], "8723214")
        self.assertIn("1964-05-01", rows[0]["quality_note"])
        self.assertEqual(rows[0]["begin_utc"], "")
        self.assertEqual(rows[0]["evidence"], "station_class_only")

    @patch("southfl.periods.get_json")
    def test_coops_wrong_wrapped_id_is_rejected(self, mock):
        mock.return_value = {"count": 1, "stations": [{"id": "8729999"}]}
        with self.assertRaisesRegex(AcquisitionError, "mismatch"):
            coops_periods({"8723214"})

    @patch("southfl.periods.get_json")
    def test_coops_ambiguous_multiple_stations_fail(self, mock):
        mock.return_value = {"count": 2, "stations": [
            {"id": "8723214"}, {"id": "8724580"}]}
        with self.assertRaisesRegex(AcquisitionError, "expected one station"):
            coops_periods({"8723214"})

    @patch("southfl.periods.get_json")
    def test_coops_partial_station_failure_preserves_good_ones(self, mock):
        mock.side_effect = [
            {"count": 1, "stations": [{"id": "8723214"}]},
            {"count": 1, "stations": [{"id": "other"}]},
            {"count": 1, "stations": [{"id": "8724580"}]},
        ]
        problems = []
        rows = coops_periods({"8723214", "8723970", "8724580"}, errors=problems)
        self.assertEqual([x["site_id"] for x in rows], ["8723214", "8724580"])
        self.assertEqual([x["site_id"] for x in problems], ["8723970"])

    @patch("southfl.periods.get_bytes")
    def test_ndbc_archive_index_only(self, mock):
        mock.return_value = (b'<a href="41010h2023.txt.gz">2023</a>'
                             b'<a href="41010h2024.txt.gz">2024</a>'
                             b'<a href="99999h2024.txt.gz">other</a>')
        rows = ndbc_periods({"41010"})
        self.assertEqual([r["year"] for r in rows], ["2023", "2024"])
        self.assertEqual(rows[0]["concept"], "meteorology_package")
        self.assertEqual(rows[0]["evidence"], "historical_file_exists")


class IntegrationTests(unittest.TestCase):
    def test_merge_overlapping_region_sources(self):
        a = _row("usgs_water", "USGS-123", "ts-1", concept="dissolved_oxygen",
                 evidence="time_series_first_last_metadata", region="region-a")
        b = dict(a, region_query="region-b", source_url="https://example.org/second")
        rows, conflicts = unique_periods([a, b])
        self.assertEqual(len(rows), 1)
        self.assertEqual(conflicts, [])

    def test_conflicting_series_metadata_quarantined(self):
        a = _row("usgs_water", "USGS-123", "ts-1", begin="2020-01-01",
                 evidence="time_series_first_last_metadata")
        b = dict(a, end_utc="2026-01-01")
        rows, conflicts = unique_periods([a, b])
        self.assertEqual(len(rows), 0)
        self.assertEqual(len(conflicts), 1)

    def test_concept_summary_unassigned(self):
        a = _row("usgs_water", "USGS-123", "ts-1", concept="dissolved_oxygen",
                 begin="2020-01-01", end="2026-01-01",
                 evidence="time_series_first_last_metadata")
        stations = [{"dataset_id": "usgs_water", "site_id": "USGS-123", "regions": ""}]
        rows = concept_summary([a], stations)
        self.assertEqual(rows[0]["region"], "unassigned")
        self.assertEqual(rows[0]["readiness"], "metadata_only_not_trainable")

    @patch("scripts.discover_parameters.coops_periods")
    def test_coops_partial_manifest_is_not_marked_success(self, mock):
        from southfl.periods import _row
        def partial(sites, errors):
            errors.append({"site_id": "8723970", "error": "bad NOAA response"})
            return [_row("noaa_coops", "8723214", "8723214|water_level_candidate",
                         evidence="station_class_only", concept="water_level")]
        mock.side_effect = partial
        with tempfile.TemporaryDirectory() as d:
            stations = Path(d) / "stations.csv"
            write_stations(stations)
            # Override the local fixture to supply the NOAA station IDs.
            lines = stations.read_text()
            stations.write_text(lines + "noaa_coops,,8723214,,25.7,-80.2,,,,\n", encoding="utf-8")
            out = Path(d) / "run"
            result = run(stations, out, ["coops"], [])
            self.assertEqual(result["n_failed_requests"], 1)
            self.assertEqual(result["n_failed_station_requests"], 1)
            self.assertEqual(result["attempts"][0]["status"], "partial")
            self.assertEqual(result["n_parameter_periods"], 1)

    @patch("scripts.discover_parameters.usgs_periods")
    def test_run_writes_auditable_partial_manifest(self, mock):
        mock.side_effect = AcquisitionError("test agency API unavailable")
        with tempfile.TemporaryDirectory() as d:
            stations = Path(d)/"stations.csv"
            write_stations(stations)
            out = Path(d)/"parameters"
            manifest = run(stations, out, ["usgs"], ["north_biscayne"])
            self.assertEqual(manifest["n_failed_requests"], 1)
            self.assertTrue((out/"parameter_manifest.json").exists())
            self.assertTrue((out/"parameter_periods.csv").exists())
            self.assertEqual(json.loads((out/"parameter_manifest.json").read_text())[
                "observation_coverage_verified"], False)


if __name__ == "__main__":
    unittest.main()
