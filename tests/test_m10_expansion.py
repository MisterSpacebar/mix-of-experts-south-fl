"""Regression on the committed M9 real metadata snapshot; no network."""
import tempfile
import unittest
from pathlib import Path

from scripts.plan_m10_expansion import ROOT, BASELINE, REFERENCE, read, run


class M10ExpansionTests(unittest.TestCase):
    def test_real_ranked_synchronized_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"m10"
            result = run(ROOT/"history_plan.csv",
                         ROOT/"metadata_recruitment_shortlist.csv",
                         REFERENCE, BASELINE, out)
            rows = read(out/"batch_index.csv")
            self.assertEqual([r["site_id"] for r in rows], [
                "USGS-255432081303900", "USGS-255327081275900",
                "USGS-255726081303700", "USGS-255654081350200",
                "USGS-255138081321701", "USGS-02290930"])
            self.assertEqual(result["n_candidate_series"], 21)
            self.assertEqual(result["n_history_windows"], 273)
            self.assertEqual(result["n_new_station_candidates"], 5)
            self.assertEqual(result["regional_fcms_trained"], 0)
            self.assertFalse(result["observations_downloaded"])
            self.assertEqual(read(out/"excluded_sites.csv")[0]["site_id"],
                             "USGS-261808081042800")
            for row in rows:
                tasks = read(out/row["batch_id"]/"history_plan.csv")
                self.assertEqual({t["site_id"] for t in tasks}, {row["site_id"]})
                self.assertEqual({(t["start_date"], t["end_date"]) for t in tasks},
                                 {("2026-05-29", "2026-11-21")})
            self.assertEqual(rows[0]["unverified_stage_concepts"], "gage_height")
            with self.assertRaises(ValueError):
                run(ROOT/"history_plan.csv", ROOT/"metadata_recruitment_shortlist.csv",
                    REFERENCE, BASELINE, out)

    def test_window_and_request_cap_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"m10"
            args = (ROOT/"history_plan.csv",
                    ROOT/"metadata_recruitment_shortlist.csv", REFERENCE, BASELINE, out)
            with self.assertRaises(ValueError):
                run(*args, end="2026-11-24")
            self.assertFalse(out.exists())
            with self.assertRaises(ValueError):
                run(*args, max_requests=10)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
