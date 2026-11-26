"""Tests for M8 evidence browser and scientific interpretation safeguards."""
import json
import math
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.panels import PANEL_SUMMARY_COLS
from southfl.m8_evidence import (
    transfer_diagnostics,edge_strength_diagnostics,uncertainty_integrity)
from scripts.train_m8_layers import run as train
from scripts.evaluate_m8_replication import run as evaluate
from scripts.browse_m8_evidence import run as browse


def fake_station(root,site,phase):
    panel="panel_"+site.replace("-","_")
    x,y=38.0,3.0
    rows=[]
    for i in range(150):
        rows.append(dict(
            date=(date(2026,1,1)+timedelta(days=i)).isoformat(),
            site_id=site,panel_id=panel,discharge=x,gage_height=y))
        updated_x=.75*x+3.0*y+6.0+math.sin((i+phase)/9)
        y=.65*y+.012*x+.65+.04*math.cos((i+phase)/5)
        x=updated_x
    write_csv(root/(panel+".csv"),rows,
              ["date","site_id","panel_id","discharge","gage_height"])
    return dict(
        panel_id=panel,site_id=site,region="big_cypress",
        concepts="discharge;gage_height",
        concept_units="discharge=ft3/s;gage_height=ft",
        concept_datums="discharge=;gage_height=",
        source_series_ids="discharge=ts0;gage_height=ts1",
        n_requested_days=150,n_complete_days=150,
        n_consecutive_daily_pairs=149,n_excluded_source_values=0,
        status="candidate_for_held_out_evaluation")


class EvidenceUnitTests(unittest.TestCase):
    def test_transfer_shift_and_missing_datum_are_distinct(self):
        donor={"panel_id":"A","site_id":"A",
               "concept_units":"gage_height=ft",
               "concept_datums":"gage_height="}
        target={"panel_id":"B","site_id":"B",
                "concept_units":"gage_height=ft",
                "concept_datums":"gage_height="}
        model=dict(concepts=["gage_height"],normalization_mean=[5.0],
                   normalization_scale=[1.0])
        sample=[dict(concept="gage_height",actual=2.0,persistence=1.0,
                     transferred=8.0),
                dict(concept="gage_height",actual=4.0,persistence=3.0,
                     transferred=8.0)]
        scores=[dict(level="category",scope="hydrology",
                     concept="gage_height",donor_transfer_mae=5.0,
                     target_persistence_mae=1.0,n_matched_test_days=2)]
        evidence=transfer_diagnostics(donor,target,model,sample,scores)
        self.assertEqual(len(evidence),1)
        self.assertEqual(evidence[0]["datum_check"],
                         "reference_datum_unverified")
        self.assertEqual(evidence[0]["mae_ratio_vs_persistence"],5)
        self.assertEqual(evidence[0]["source_unit"],"ft")
        with self.assertRaisesRegex(ValueError,"do not match"):
            changed=[dict(scores[0],donor_transfer_mae=999)]
            transfer_diagnostics(donor,target,model,sample,changed)

    def test_sign_consensus_must_not_disguise_tiny_weights(self):
        recurrence=[dict(level="category",scope="water_quality",
            source_concept="salinity",target_concept="water_temperature",
            n_distinct_sites=3,n_positive=0,n_negative=3,
            sign_consistency=1.0)]
        site_weights={("category","water_quality","salinity",
                       "water_temperature"):
                      [("A",-.02),("B",-.04),("C",-.07)]}
        result=edge_strength_diagnostics(recurrence,site_weights,.08)
        self.assertEqual(result[0]["evidence_grade"],
                         "weak_weight_in_at_least_one_site")
        self.assertEqual(result[0]["n_sites_above_threshold"],0)
        self.assertFalse(result[0]["regional_model_trained"])
        with self.assertRaisesRegex(ValueError,"sign counts"):
            edge_strength_diagnostics([
                dict(recurrence[0],n_positive=3,n_negative=0)],
                site_weights,.08)

    def test_bootstrap_outside_point_is_explicit_warning(self):
        rows=[dict(panel_id="p",level="category",scope="hydrology",
            comparison="specialist_minus_full_station",concept="discharge",
            n_test_days="19",mae_delta_a_minus_b="-4.16",
            delta_ci_2_5="0.88",delta_ci_97_5="8.32")]
        result=uncertainty_integrity(rows)
        self.assertEqual(result[0]["audit_status"],
                         "point_estimate_outside_bootstrap_interval")


class EvidenceEndToEndTests(unittest.TestCase):
    def test_two_real_structure_sites_and_immutable_model_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            panels=base/"panels";panels.mkdir()
            sites=[fake_station(panels,"USGS-A",0),
                   fake_station(panels,"USGS-B",4)]
            write_csv(panels/"panel_readiness.csv",sites,PANEL_SUMMARY_COLS)
            (panels/"panels_manifest.json").write_text(json.dumps({
                "observations_sha256":"0"*64,"synthetic_only":True
            }),encoding="utf-8")
            models=base/"models"
            trained=train([panels],models,dpi=60)
            self.assertEqual(trained["n_fitted_dataset_models"],2)
            frozen=(models/"manifest.json").read_bytes()
            evidence=base/"evidence"
            evaluate(models,[panels],evidence,block_days=5,bootstrap=100,
                     max_folds=2,min_sites=2,dpi=60)
            proof=(evidence/"manifest.json").read_bytes()
            out=base/"browse"
            result=browse(models,evidence,[panels],out,edge_threshold=.08,dpi=60)
            self.assertEqual(result["n_transfer_diagnostics"],8)
            self.assertEqual(result["n_unverified_stage_datum_rows"],4)
            self.assertEqual((models/"manifest.json").read_bytes(),frozen)
            self.assertEqual((evidence/"manifest.json").read_bytes(),proof)
            self.assertTrue((out/"INDEX.md").exists())
            self.assertTrue((out/"scope_coverage.png").exists())
            self.assertTrue((out/"levels"/"category"/"hydrology"/
                             "visuals"/"transfer_vs_persistence.png").exists())
            self.assertTrue((out/"levels"/"subcategory"/"hydrology"/
                             "surface_flow"/"FINDINGS.md").exists())
            self.assertTrue((out/"levels"/"overall"/"FINDINGS.md").exists())
            audit=read_csv(out/"transfer_failure_audit.csv")
            self.assertEqual(sum(x["datum_check"]==
                         "reference_datum_unverified" for x in audit),4)
            scopes=read_csv(out/"scope_summary.csv")
            hydro=next(x for x in scopes if x["level"]=="category"
                       and x["scope"]=="hydrology")
            self.assertEqual(hydro["evidence_status"],
                             "station_transfer_evidence_available")
            singleton=next(x for x in scopes if x["level"]=="subcategory"
                       and x["scope"]=="hydrology/surface_flow")
            self.assertEqual(singleton["evidence_status"],
                             "redundant_concept_scope_not_independent")
            self.assertIn("FCM network",
                          (out/"levels"/"category"/"hydrology"/
                           "FINDINGS.md").read_text())
            with self.assertRaisesRegex(ValueError,"new/empty"):
                browse(models,evidence,[panels],out,dpi=60)

    def test_committed_three_station_snapshot_if_present(self):
        """Real USGS snapshot regression; skip if large data excluded from clone."""
        base=Path(__file__).resolve().parents[1]
        models=base/"data/m8/layers_replication_v1"
        evidence=base/"data/m8/replication_evidence_v1"
        panels=[base/"data/m7/daily_panels_verified_01",
                base/"data/m8/replication_daily_01"]
        needed=[models/"manifest.json",models/"model_registry.csv",
                evidence/"manifest.json",evidence/"cross_station_transfer.csv"]
        needed += [p/"panel_readiness.csv" for p in panels]
        if not all(x.is_file() for x in needed):
            self.skipTest("real M8 station files not present in this checkout")
        with tempfile.TemporaryDirectory() as td:
            result=browse(models,evidence,panels,Path(td)/"browser",
                          edge_threshold=.08,dpi=60)
            self.assertEqual(result["n_transfer_diagnostics"],48)
            self.assertEqual(result["n_edge_evidence_rows"],24)
            self.assertEqual(result["n_unverified_stage_datum_rows"],12)
            self.assertTrue((Path(td)/"browser"/"INDEX.md").exists())

    def test_evidence_hash_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"models").mkdir()
            (root/"evidence").mkdir()
            (root/"models"/"manifest.json").write_text('{"a":1}')
            (root/"evidence"/"manifest.json").write_text(
                json.dumps({"source_m8_manifest_sha256":"invalid"}))
            with self.assertRaisesRegex(ValueError,"does not belong"):
                browse(root/"models",root/"evidence",[],
                       root/"browser",dpi=60)


if __name__=="__main__":
    unittest.main()
