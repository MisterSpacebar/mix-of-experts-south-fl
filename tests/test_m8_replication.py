"""Offline M8 replication tests — temporal, uncertainty and site transfer."""
import json
import math
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

from southfl.fcm_model import fit_preview
from southfl.history_selection import PLAN_COLS,select_panels
from southfl.m8_validation import (
    paired_block_interval,expanding_folds,matched_rows,NotReadyError)
from southfl.m8_transfer import (
    exact_units,transfer_to_target,summarize_transfer,source_edge_replication)
from southfl.net import write_csv
from southfl.audit import read_csv
from southfl.panels import PANEL_SUMMARY_COLS
from scripts.train_m8_layers import run as train_layers
from scripts.evaluate_m8_replication import run as evaluate

CONCEPTS=["discharge","gage_height"]


def observed(n=150,site="USGS-EXAMPLE-A",phase=0):
    x,y=38.0,3.0
    start=date(2026,1,1)
    rows=[]
    for i in range(n):
        rows.append({
            "date":(start+timedelta(days=i)).isoformat(),
            "site_id":site,
            "panel_id":"panel_"+site.replace("-","_"),
            "discharge":x,"gage_height":y,
        })
        x=.75*x+3.0*y+6.0+math.sin((i+phase)/9)
        y=.65*y+.012*x+.65+.04*math.cos((i+phase)/5)
    return rows


def panel_data(root,site,phase=0):
    pid="panel_"+site.replace("-","_")
    data=observed(site=site,phase=phase)
    write_csv(root/(pid+".csv"),data,["date","site_id","panel_id"]+CONCEPTS)
    return dict(panel_id=pid,site_id=site,region="big_cypress",
        concepts="discharge;gage_height",
        concept_units="discharge=ft3/s;gage_height=ft",
        concept_datums="discharge=;gage_height=",
        source_series_ids="discharge=ts0;gage_height=ts1",
        n_requested_days=150,n_complete_days=150,
        n_consecutive_daily_pairs=149,n_excluded_source_values=0,
        status="candidate_for_held_out_evaluation")


class UncertaintyTests(unittest.TestCase):
    def test_paired_bootstrap_deterministic_and_correct_sign(self):
        rows=[{"date":(date(2026,1,1)+timedelta(days=i)).isoformat(),
               "actual":10,"fcm":11,"persistence":13}
              for i in range(20)]
        first=paired_block_interval(rows,"fcm","persistence",block_length=5,
                                    replicates=200,seed=81)
        second=paired_block_interval(rows,"fcm","persistence",block_length=5,
                                     replicates=200,seed=81)
        self.assertEqual(first,second)
        self.assertAlmostEqual(first["mae_delta_a_minus_b"],-2)
        self.assertAlmostEqual(first["delta_ci_2_5"],-2)
        self.assertEqual(first["bootstrap_fraction_a_better"],1)

    def test_gap_cannot_cross_a_block(self):
        rows=[{"date":(date(2026,1,1)+timedelta(days=i*3)).isoformat(),
               "actual":10,"fcm":11,"persistence":13}
              for i in range(20)]
        with self.assertRaisesRegex(NotReadyError,"no contiguous"):
            paired_block_interval(rows,"fcm","persistence",block_length=5,
                                  replicates=200)

    def test_different_test_sets_refused(self):
        orig=[dict(date="2026-10-01",concept="discharge",actual=3,fcm=4)]
        shifted=[dict(date="2026-10-02",concept="discharge",actual=3,fcm=4)]
        with self.assertRaisesRegex(ValueError,"dates or concept sets"):
            matched_rows(orig,shifted)


class FoldTests(unittest.TestCase):
    def test_expanding_origin_test_days_disjoint_and_future_free(self):
        rows=observed()
        models=expanding_folds(rows,CONCEPTS,max_folds=3)
        self.assertGreaterEqual(len(models),2)
        dates=set()
        for model in models:
            current={p["date"] for p in model["predictions"]}
            self.assertFalse(dates.intersection(current))
            dates.update(current)
            self.assertLess(model["train_end"],model["validation_start"])
            self.assertLess(model["validation_end"],model["test_start"])
        self.assertEqual(models[-1]["test_end"],rows[-1]["date"])


class TransferTests(unittest.TestCase):
    def test_donor_only_transfer_leaves_source_model_unchanged(self):
        donor_rows=observed(site="USGS-A")
        target_rows=observed(site="USGS-B",phase=2)
        donor=fit_preview(donor_rows,CONCEPTS)
        target=fit_preview(target_rows,CONCEPTS)
        saved=json.dumps(donor,sort_keys=True)
        transfer=transfer_to_target(donor,target_rows,target["predictions"],CONCEPTS)
        self.assertEqual(len(transfer),len(target["predictions"]))
        self.assertEqual(json.dumps(donor,sort_keys=True),saved)
        metrics=summarize_transfer(dict(level="category",scope="hydrology",
            site_id="USGS-A",panel_id="p1"),dict(site_id="USGS-B",panel_id="p2"),
            transfer)
        self.assertEqual(len(metrics),2)
        self.assertTrue(all(m["n_matched_test_days"]==target["test_pairs"]
                            for m in metrics))
        target_rows[-1]["discharge"]+=1000
        with self.assertRaisesRegex(ValueError,"heldout target values differ"):
            transfer_to_target(donor,target_rows,target["predictions"],CONCEPTS)

    def test_missing_or_mismatched_units_refused(self):
        same=dict(concept_units="discharge=ft3/s;gage_height=ft",
                  concept_datums="discharge=;gage_height=")
        other=dict(concept_units="discharge=m3/s;gage_height=ft",
                   concept_datums="discharge=;gage_height=")
        missing=dict(concept_units="discharge=ft3/s",concept_datums="")
        self.assertIsNone(exact_units(missing,CONCEPTS))
        self.assertNotEqual(exact_units(same,CONCEPTS),
                            exact_units(other,CONCEPTS))

    def test_replication_requires_independent_sites(self):
        edges=[dict(source_concept="discharge",target_concept="gage_height",
                    weight=.2),
               dict(source_concept="gage_height",target_concept="discharge",
                    weight=-.1)]
        def src(site,w):
            return dict(level="category",scope="hydrology",
                        site_id=site,panel_id="panel_"+site,
                        concepts=CONCEPTS,
                        unit_signature=(("discharge","ft3/s",""),
                                        ("gage_height","ft","")),
                        edges=[dict(e,weight=e["weight"]*w) for e in edges])
        results=source_edge_replication(
            [src("A",1),src("B",1),src("C",-1)],min_sites=3)
        self.assertEqual(len(results),2)
        self.assertTrue(all(x["status"]=="replication_candidate_not_causal"
                            for x in results))
        x=next(x for x in results if x["source_concept"]=="discharge")
        self.assertEqual(x["n_distinct_sites"],3)
        self.assertAlmostEqual(x["sign_consistency"],2/3)
        with self.assertRaisesRegex(ValueError,"duplicate"):
            source_edge_replication([src("A",1),src("A",1)])


class EndToEndTests(unittest.TestCase):
    def test_two_sites_all_evidence_layers_and_reference_are_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            sources=root/"daily";sources.mkdir()
            items=[panel_data(sources,"USGS-A"),
                   panel_data(sources,"USGS-B",phase=2)]
            write_csv(sources/"panel_readiness.csv",items,PANEL_SUMMARY_COLS)
            (sources/"panels_manifest.json").write_text(json.dumps({
                "observations_sha256":"0"*64,
                "test_marker":"synthetic_only"}))
            trained=root/"trained"
            m8=train_layers([sources],trained,dpi=65)
            self.assertEqual(m8["n_fitted_dataset_models"],2)
            reference=(trained/"manifest.json").read_bytes()
            output=root/"robustness"
            report=evaluate(trained,[sources],output,block_days=5,
                            bootstrap=100,max_folds=2,min_sites=2,dpi=65)
            self.assertEqual((trained/"manifest.json").read_bytes(),reference)
            self.assertEqual(report["n_unique_station_ids"],2)
            self.assertGreater(report["n_temporal_rows"],0)
            self.assertGreater(report["n_paired_uncertainty_rows"],0)
            self.assertGreater(report["n_transfer_concept_rows"],0)
            self.assertEqual(report["regional_category_fcms_fitted"],0)
            for loc in ["INDEX.md","evaluation_registry.csv",
                        "cross_station_edge_signs.csv",
                        "cross_station_transfer.csv",
                        "cross_station_transfer_readiness.csv",
                        "cross_station_transfer_predictions.csv",
                        "levels/dataset/FINDINGS.md",
                        "levels/category/hydrology/FINDINGS.md",
                        "levels/category/hydrology/visuals/edge_sign_recurrence.png",
                        "levels/category/hydrology/visuals/station_transfer_skill.png",
                        "levels/overall/STATUS.md"]:
                self.assertTrue((output/loc).exists(),loc)
            row=next(r for r in read_csv(output/"evaluation_registry.csv")
                     if r["level"]=="dataset")
            self.assertTrue(
                (output/row["model_dir"]/"visuals/temporal_skill.png").exists())
            with self.assertRaisesRegex(ValueError,"new/empty"):
                evaluate(trained,[sources],output,block_days=5,
                         bootstrap=100,max_folds=2,min_sites=2,dpi=65)


if __name__=="__main__":
    unittest.main()
