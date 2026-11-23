import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from southfl.regions import inside, parse_bbox, regions_for
from southfl.sources import coops, usgs, wqp, station
from southfl.net import AcquisitionError
from southfl.audit import audit_observations, coordinate_collisions, catalog_inventory


class RegionTests(unittest.TestCase):
    def test_regions_overlap_intentionally(self):
        self.assertIn("upper_keys", regions_for(25.01, -80.50))
        self.assertTrue(inside(25.01, -80.50, (-81, 24, -80, 26)))

    def test_bad_bbox(self):
        for value in ("bad", "-80,25,-81,26", "-200,1,0,2"):
            with self.assertRaises(ValueError):
                parse_bbox(value)


class SourceTests(unittest.TestCase):
    @patch("southfl.sources.get_json")
    def test_coops_filters_bbox(self, mock):
        mock.return_value = {"stations": [
            {"id": "8724580", "name": "Key West", "lat": 24.55, "lng": -81.80},
            {"id": "999", "name": "Distant", "lat": 38, "lng": -75},
        ]}
        rows = coops()
        self.assertEqual([r["site_id"] for r in rows], ["8724580"])
        self.assertEqual(rows[0]["coverage_status"], "metadata_only")

    @patch("southfl.sources.get_csv")
    def test_wqp_rows(self, mock):
        mock.return_value = [{
            "MonitoringLocationIdentifier": "ORG-123",
            "MonitoringLocationName": "Sample",
            "LatitudeMeasure": "25.7", "LongitudeMeasure": "-80.2",
        }]
        self.assertEqual(wqp()[0]["site_id"], "ORG-123")

    @patch("southfl.sources.get_json")
    def test_usgs_pagination(self, mock):
        mock.side_effect = [
            {"features": [{"id": "site-a", "properties": {
                "monitoring_location_number": "123", "monitoring_location_name": "A"},
                "geometry": {"coordinates": [-80.25, 25.8]}}
              ], "links": [{"rel": "next", "href": "https://api.waterdata.usgs.gov/ogcapi/v1/collections/monitoring-locations/items?offset=1"}]},
            {"features": [], "links": []},
        ]
        rows = usgs()
        self.assertEqual(len(rows), 1)
        self.assertEqual(mock.call_count, 2)

    @patch("southfl.sources.get_json")
    def test_usgs_fails_incomplete_pagination(self, mock):
        mock.return_value = {"features": [], "links": [{
            "rel": "next", "href": "https://api.waterdata.usgs.gov/ogcapi/v1/collections/monitoring-locations/items?offset=1"}]}
        with self.assertRaisesRegex(AcquisitionError, "pagination"):
            usgs(max_pages=2)


class AuditTests(unittest.TestCase):
    def test_observed_counts_not_assumed_coverage(self):
        observations = [
            dict(dataset_id="x", site_id="s", variable="DO", timestamp_utc="2026-01-01T00:00:00Z", value="1.5"),
            dict(dataset_id="x", site_id="s", variable="DO", timestamp_utc="2026-01-01T12:00:00Z", value="2.2"),
            dict(dataset_id="x", site_id="s", variable="DO", timestamp_utc="2026-01-02T12:00:00Z", value=""),
        ]
        rows = audit_observations(observations)
        self.assertEqual(rows[0]["n_records"], 2)
        self.assertEqual(rows[0]["n_distinct_dates"], 1)
        self.assertEqual(rows[0]["coverage_fraction"], "")
        self.assertEqual(rows[0]["status"], "schedule_unknown")

    def test_timezones_required(self):
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            audit_observations([dict(dataset_id="x", site_id="s", variable="DO",
                                     timestamp_utc="2026-01-01T12:00:00", value="2")])

    def test_colocation_is_not_dedup(self):
        a = station("one", "A", "1", "X", 25.5, -80.2, "https://example.com")
        b = station("two", "B", "2", "Y", 25.5, -80.2, "https://example.com")
        self.assertEqual(len(coordinate_collisions([a, b])), 1)
        with tempfile.TemporaryDirectory() as d:
            catalog_inventory([a, b], Path(d))
            self.assertEqual(len((Path(d)/"stations.csv").read_text().splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
