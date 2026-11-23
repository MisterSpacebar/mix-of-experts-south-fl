"""Offline site-level environmental parameter shortlist tests."""
import unittest
from scripts.shortlist_parameters import build_shortlist
from southfl.periods import _row


class ShortlistTests(unittest.TestCase):
    def test_evidence_not_equated_with_trainability(self):
        stations = [
            {"dataset_id": "usgs_water", "site_id": "USGS-1",
             "regions": "north_biscayne;central_south_biscayne"},
            {"dataset_id": "epa_wqp", "site_id": "ORG-1", "regions": "florida_bay"},
            {"dataset_id": "noaa_coops", "site_id": "8724580", "regions": "lower_keys"},
        ]
        periods = [
            _row("usgs_water", "USGS-1", "ts1", concept="dissolved_oxygen",
                 begin="2020-01-01T00:00:00Z", end="2026-01-01T00:00:00Z",
                 evidence="time_series_first_last_metadata"),
            _row("epa_wqp", "ORG-1", "chem-2025", concept="nitrogen_unspecified_fraction",
                 year="2025", results="19", activities="8",
                 evidence="annual_result_and_activity_counts"),
            _row("noaa_coops", "8724580", "water_level_candidate", concept="water_level",
                 evidence="station_class_only"),
        ]
        out = build_shortlist(periods, stations)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(r["trainable"] == "NOT_DETERMINED" for r in out))
        usgs = [r for r in out if r["dataset_id"] == "usgs_water"]
        self.assertEqual(len(usgs), 2)
        self.assertEqual(usgs[0]["last_date_hint"], "2026-01-01")
        wqp = next(r for r in out if r["dataset_id"] == "epa_wqp")
        self.assertEqual(wqp["reported_result_count"], 19)
        coops = next(r for r in out if r["dataset_id"] == "noaa_coops")
        self.assertEqual(coops["first_date_hint"], "")
        self.assertIn("verify_product_observations", coops["next_step"])

    def test_no_unknown_site_or_unmapped(self):
        s = [{"dataset_id": "epa_wqp", "site_id": "x", "regions": ""}]
        self.assertEqual(build_shortlist([_row("epa_wqp", "x", "a",
                                               concept="unmapped")], s), [])
        with self.assertRaisesRegex(ValueError, "absent"):
            build_shortlist([_row("epa_wqp", "other", "a",
                                  concept="dissolved_oxygen")], s)


if __name__ == "__main__":
    unittest.main()
