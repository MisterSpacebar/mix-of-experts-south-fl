"""Source-grounded tests for hydraulic concept and vertical datum preservation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.discover_parameters import concept_summary
from scripts.fetch_observation_pilot import validate_tasks
from scripts.harmonize_parameter_inventory import harmonize
from scripts.merge_parameter_periods import combine
from southfl.audit import read_csv
from southfl.net import AcquisitionError, write_csv
from southfl.observations import usgs_observations
from southfl.parameters import (harmonize_period_record, usgs_concept,
                                 usgs_vertical_datum, wqp_concept)
from southfl.periods import PERIOD_COLUMNS, _row, usgs_periods
from southfl.sources import STATION_COLUMNS

SITES = [
    {"dataset_id": "usgs_water", "site_id": "USGS-GW",
     "latitude": 26.0, "longitude": -80.8,
     "regions": "everglades_interior;big_cypress"},
    {"dataset_id": "noaa_coops", "site_id": "8724580",
     "latitude": 24.6, "longitude": -81.8, "regions": "lower_keys"},
]


class HydraulicConceptTests(unittest.TestCase):
    def test_verified_usgs_parameter_codes(self):
        expected = {
            "62610": ("groundwater_elevation", "NGVD29"),
            "62611": ("groundwater_elevation", "NAVD88"),
            "63158": ("stream_stage_elevation", "NGVD29"),
            "63160": ("stream_stage_elevation", "NAVD88"),
            "72255": ("water_velocity", ""),
            "00065": ("gage_height", ""),
            "72019": ("groundwater_depth_below_land_surface", ""),
        }
        for code, (concept, datum) in expected.items():
            with self.subTest(parameter_code=code):
                self.assertEqual(usgs_concept(code), concept)
                self.assertEqual(usgs_vertical_datum(code), datum)

    def test_site_gage_height_does_not_invent_a_geodetic_datum(self):
        self.assertEqual(usgs_vertical_datum("00065"), "")
        self.assertEqual(usgs_vertical_datum("00065", "LOCAL-GAGE"), "LOCAL-GAGE")
        self.assertEqual(usgs_vertical_datum("62611", "NAVD88"), "NAVD88")
        with self.assertRaisesRegex(ValueError, "expects NGVD29"):
            usgs_vertical_datum("62610", "NAVD88")

    def test_unknown_code_preserves_source_vertical_reference(self):
        self.assertEqual(usgs_vertical_datum("99999", "CUSTOM-DATUM"), "CUSTOM-DATUM")
        self.assertEqual(usgs_concept("99999", "Unspecified measurement"), "unmapped")

    def test_legacy_rows_harmonized_without_modifying_source(self):
        old = dict(dataset_id="usgs_water", site_id="USGS-GW",
                   parameter_code="62610", parameter_name="Elevation, GW, NGVD29",
                   concept="unmapped", unit="ft")
        new = harmonize_period_record(old)
        self.assertEqual(new["concept"], "groundwater_elevation")
        self.assertEqual(new["vertical_datum"], "NGVD29")
        self.assertNotIn("vertical_datum", old)
        other = harmonize_period_record(dict(
            dataset_id="noaa_coops", site_id="8724580", parameter_code="",
            concept="water_level"))
        self.assertEqual(other["concept"], "water_level")
        self.assertEqual(other["vertical_datum"], "")

    @patch("southfl.periods.get_json")
    def test_usgs_metadata_preserves_reference(self, request):
        request.return_value = {"features": [{
            "id": "ts-62611",
            "properties": {
                "monitoring_location_id": "USGS-GW",
                "time_series_id": "ts-62611", "parameter_code": "62611",
                "parameter_name": "Elevation, GW, NAVD88",
                "unit_of_measure": "ft",
                "begin": "2020-01-01T00:00:00Z",
                "end": "2026-11-24T00:00:00Z"}}], "links": []}
        rows = usgs_periods((-81.0, 25.0, -80.0, 27.0), {"USGS-GW"})
        self.assertEqual(rows[0]["concept"], "groundwater_elevation")
        self.assertEqual(rows[0]["vertical_datum"], "NAVD88")
        self.assertEqual(rows[0]["unit"], "ft")

    @patch("southfl.observations.get_json")
    def test_usgs_observations_preserve_reference(self, request):
        request.return_value = {"features": [{
            "id": "value-1",
            "properties": {
                "monitoring_location_id": "USGS-GW",
                "parameter_code": "62611",
                "time": "2026-10-01T18:00:00Z", "value": "1.4",
                "unit_of_measure": "ft"}}], "links": []}
        rows, _ = usgs_observations(
            "USGS-GW", "62611", "2026-10-01", "2026-10-02",
            "groundwater_elevation", mode="continuous")
        self.assertEqual(rows[0]["vertical_datum"], "NAVD88")
        self.assertEqual(rows[0]["concept"], "groundwater_elevation")
        self.assertEqual(rows[0]["unit"], "ft")

    def test_old_usgs_gage_height_plan_rejected_before_network(self):
        task = dict(dataset_id="usgs_water", site_id="USGS-1",
                    concept="water_level", parameter_code="00065",
                    parameter_name="Gage height", start_date="2026-10-01",
                    end_date="2026-10-07", usgs_mode="continuous")
        with self.assertRaisesRegex(ValueError, "regenerate"):
            validate_tasks([task], 25)

    def test_summary_stratifies_ngvd29_vs_navd88(self):
        a = _row("usgs_water", "USGS-GW", "g1", code="62610",
                 concept="groundwater_elevation", datum="NGVD29",
                 evidence="time_series_first_last_metadata")
        b = _row("usgs_water", "USGS-GW", "g2", code="62611",
                 concept="groundwater_elevation", datum="NAVD88",
                 evidence="time_series_first_last_metadata")
        records = concept_summary([a, b], [SITES[0]])
        self.assertEqual(len(records), 2 * 2)
        self.assertEqual({r["vertical_datum"] for r in records},
                         {"NGVD29", "NAVD88"})


class SnapshotMigrationTests(unittest.TestCase):
    def _fixture(self, root):
        old = root/"verified_v4"
        old.mkdir()
        site_path = root/"stations.csv"
        write_csv(site_path, SITES, STATION_COLUMNS)
        # Older snapshots have no vertical_datum column by construction.
        old_cols = [c for c in PERIOD_COLUMNS if c != "vertical_datum"]
        raw = [_row("usgs_water", "USGS-GW", "gw-a", code="62610",
                    name="Elevation, GW, NGVD29", concept="unmapped", unit="ft",
                    evidence="time_series_first_last_metadata"),
               _row("usgs_water", "USGS-GW", "gage-b", code="00065",
                    name="Gage height", concept="water_level", unit="ft",
                    evidence="time_series_first_last_metadata"),
               _row("noaa_coops", "8724580", "8724580|water_level_candidate",
                    concept="water_level", evidence="station_class_only")]
        write_csv(old/"parameter_periods.csv", raw, old_cols)
        (old/"parameter_manifest.json").write_text(json.dumps({
            "status": "complete", "n_failed_requests": 0,
            "n_conflicting_metadata_records": 0, "n_parameter_periods": 3,
            "observation_coverage_verified": False,
        }), encoding="utf-8")
        (old/"time_series_end_advances.csv").write_text(
            "site_id,previous_end_utc,expanded_end_utc\nUSGS-GW,old,new\n",
            encoding="utf-8")
        return old, site_path, root/"harmonized"

    def test_snapshot_reclassification_with_provenance_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            old, sites, dest = self._fixture(Path(temp))
            old_bytes = (old/"parameter_periods.csv").read_bytes()
            original_audit = (old/"time_series_end_advances.csv").read_bytes()
            report = harmonize(old, sites, dest)
            self.assertEqual(report["n_parameter_periods"], 3)
            self.assertEqual(report["n_changed_series_rows"], 2)
            self.assertEqual(report["n_distinct_mapping_changes"], 2)
            self.assertEqual(report["status"], "complete")
            self.assertFalse(report["observation_coverage_verified"])
            rows = read_csv(dest/"parameter_periods.csv")
            gw = next(x for x in rows if x["series_id"] == "gw-a")
            self.assertEqual((gw["concept"], gw["vertical_datum"]),
                             ("groundwater_elevation", "NGVD29"))
            gage = next(x for x in rows if x["series_id"] == "gage-b")
            self.assertEqual((gage["concept"], gage["vertical_datum"]),
                             ("gage_height", ""))
            self.assertEqual((old/"parameter_periods.csv").read_bytes(), old_bytes)
            self.assertEqual((dest/"time_series_end_advances.csv").read_bytes(),
                             original_audit)
            self.assertEqual(len(read_csv(dest/"parameter_taxonomy_changes.csv")), 2)
            with self.assertRaisesRegex(ValueError, "empty"):
                harmonize(old, sites, dest)

    def test_incomplete_source_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            old, sites, dest = self._fixture(Path(temp))
            (old/"parameter_manifest.json").write_text(json.dumps({
                "status": "incomplete", "n_failed_requests": 0,
                "n_conflicting_metadata_records": 354, "n_parameter_periods": 3
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "complete"):
                harmonize(old, sites, dest)
            self.assertFalse(dest.exists())

    def test_cross_snapshot_merge_accepts_legacy_usgs_datum(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root/"old"
            new = root/"new"
            old.mkdir()
            new.mkdir()
            site = root/"stations.csv"
            write_csv(site, [SITES[0]], STATION_COLUMNS)
            old_columns = [c for c in PERIOD_COLUMNS if c != "vertical_datum"]
            previous = _row("usgs_water", "USGS-GW", "ts", code="62611",
                            concept="unmapped", name="Elevation, GW, NAVD88",
                            unit="ft", begin="2020-01-01T00:00:00+00:00",
                            end="2026-11-22T00:00:00+00:00",
                            evidence="time_series_first_last_metadata")
            expanded = dict(previous, end_utc="2026-11-24T00:00:00+00:00")
            write_csv(old/"parameter_periods.csv", [previous], old_columns)
            write_csv(new/"parameter_periods.csv", [expanded], old_columns)
            for path, stamp in ((old, "2026-11-23T00:00:00+00:00"),
                                (new, "2026-11-25T00:00:00+00:00")):
                (path/"parameter_manifest.json").write_text(json.dumps({
                    "status": "complete", "n_failed_requests": 0,
                    "n_conflicting_metadata_records": 0, "n_parameter_periods": 1,
                    "retrieved_at_utc": stamp,
                }), encoding="utf-8")
            output = root/"joined"
            report = combine(old, new, site, output)
            self.assertEqual(report["n_reconciled_usgs_end_advances"], 1)
            self.assertEqual(report["n_conflicting_metadata_records"], 0)
            rows = read_csv(output/"parameter_periods.csv")
            self.assertEqual(rows[0]["vertical_datum"], "NAVD88")
            self.assertEqual(rows[0]["concept"], "groundwater_elevation")


if __name__ == "__main__":
    unittest.main()
