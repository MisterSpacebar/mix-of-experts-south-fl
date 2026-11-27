"""Real corrected M10 source regression (no network or training)."""
import tempfile
import unittest
from pathlib import Path

from scripts.audit_m10_regional_cohort import (
    DEFAULT_SNAPSHOTS, dates_summary, run, load_snapshot)
from southfl.audit import read_csv
from datetime import date


class RegionalCohortTests(unittest.TestCase):
    def test_corrected_real_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"cohort"
            report=run(DEFAULT_SNAPSHOTS,out)
            self.assertEqual(report["n_observed_sites"],4)
            self.assertEqual(len(report["eligible_sites"]),3)
            self.assertNotIn("USGS-0229070854",report["eligible_sites"])
            self.assertEqual((report["common_days"],report["common_transitions"],
                              report["longest_common_stretch"]),(163,159,95))
            self.assertTrue(report["temporal_metadata_screen_pass"])
            self.assertFalse(report["hydrological_connectivity_verified"])
            self.assertFalse(report["raw_bytes_verified"])
            self.assertEqual(report["regional_fcms_trained"],0)
            folds=read_csv(out/"spatial_fold_plan.csv")
            self.assertEqual(len(folds),3)
            for fold in folds:
                self.assertNotIn(fold["heldout_site"],fold["donor_sites"].split(";"))
                self.assertEqual(fold["temporal_screen_pass"],"True")
            with self.assertRaisesRegex(ValueError,"new/empty"):
                run(DEFAULT_SNAPSHOTS,out)

    def test_duplicate_snapshot_is_not_independent_station(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"cohort"
            with self.assertRaisesRegex(ValueError,"duplicate independent station"):
                run([DEFAULT_SNAPSHOTS[0],DEFAULT_SNAPSHOTS[0]],out)
            self.assertFalse(out.exists())

    def test_missing_day_never_creates_transition(self):
        ds=[date(2026,5,29),date(2026,5,30),date(2026,6,1)]
        self.assertEqual(dates_summary(ds),(3,1,2))

    def test_raw_hash_verification_on_committed_faka(self):
        rows,lineage=load_snapshot(*DEFAULT_SNAPSHOTS[0],verify_raw=True)
        self.assertEqual(rows[0]["complete_days"],177)
        self.assertTrue(lineage["raw_bytes_verified"])
