"""Milestone 8: real-structure synthetic tests, no agency calls."""
import json
import math
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from xml.etree import ElementTree

from southfl.net import write_csv
from southfl.panels import PANEL_SUMMARY_COLS
from southfl.history_selection import PLAN_COLS
from southfl.fcm_model import fit_preview
from southfl.m8_layers import concept_scopes,compare_matched
from scripts.train_m8_layers import run as train_m8
from scripts.plan_m8_batches import run as plan_batches

CONCEPTS=["discharge","salinity","water_temperature","gage_height"]


def simulated(n=165,site="USGS-TEST"):
    a,b,c,d=30.0,11.0,25.0,2.0
    start=date(2026,1,1)
    rows=[]
    for i in range(n):
        rows.append(dict(date=(start+timedelta(days=i)).isoformat(),
                         panel_id="panel_01_USGS_TEST",site_id=site,
                         discharge=a,salinity=b,water_temperature=c,
                         gage_height=d))
        aa=.82*a-.12*b+.6*math.sin(i/8)+5.3
        bb=.91*b-.02*a+.25*math.cos(i/11)+1.1
        cc=.87*c+.17*math.sin(i/12)+3.0
        dd=.73*d+.018*a+.05*math.sin(i/6)+.12
        a,b,c,d=aa,bb,cc,dd
    return rows


def setup_panel(root,site="USGS-TEST",pid="panel_01_USGS_TEST",days=165):
    root=Path(root)
    rows=simulated(days,site)
    for row in rows:
        row["panel_id"]=pid
    write_csv(root/(pid+".csv"),rows,
              ["date","site_id","panel_id"]+CONCEPTS)
    data=dict(
        panel_id=pid,region="big_cypress",site_id=site,
        concepts=";".join(CONCEPTS),
        concept_units="discharge=ft3/s;salinity=ppt;water_temperature=degC;gage_height=ft",
        concept_datums="discharge=;salinity=;water_temperature=;gage_height=",
        source_series_ids="discharge=ts1;salinity=ts2;water_temperature=ts3;gage_height=ts4",
        n_requested_days=180,n_complete_days=days,
        n_consecutive_daily_pairs=days-1,
        n_excluded_source_values=0,
        status="candidate_for_held_out_evaluation")
    write_csv(root/"panel_readiness.csv",[data],PANEL_SUMMARY_COLS)
    (root/"panels_manifest.json").write_text(json.dumps({
        "observations_sha256":"0"*64,
        "source":"synthetic_test_only"}))
    return pid


def plan_rows(pid,site):
    result=[]
    for concept,code,index in [
        ("discharge","00060",1),("salinity","00480",2),
        ("water_temperature","00010",3),("gage_height","00065",4)]:
        result.append(dict(
            panel_id=pid,region="big_cypress",dataset_id="usgs_water",
            site_id=site,concept=concept,parameter_code=code,
            series_id=f"{site}-{index}",unit="native",vertical_datum="",
            start_date="2026-07-04",end_date="2026-10-31",
            mode="continuous",metadata_start="2020-01-01",
            metadata_end="2026-11-01",
            selection_status="metadata_candidate_validate_real_observations"))
    return result


class ScopeTests(unittest.TestCase):
    def test_scopes_are_not_projections_and_exclude_unknown(self):
        scopes=concept_scopes(CONCEPTS+["unrecognized_variable"])
        keys={(level,cat,sub) for level,cat,sub,_ in scopes}
        self.assertIn(("category","hydrology",""),keys)
        self.assertIn(("category","water_quality",""),keys)
        self.assertIn(("subcategory","hydrology","surface_flow"),keys)
        self.assertIn(("subcategory","water_quality","thermal_conditions"),keys)
        self.assertFalse(any(cat=="unclassified" for _,cat,_,_ in scopes))

    def test_mismatched_holdout_days_rejected(self):
        rows=simulated()
        full=fit_preview(rows,CONCEPTS)
        scoped=fit_preview(rows,["discharge","gage_height"])
        out=compare_matched(full,scoped,"panel","subcategory","hydrology/surface_flow")
        self.assertEqual(len(out),2)
        self.assertTrue(all(r["n_aligned_test_days"]==full["test_pairs"] for r in out))
        scoped["predictions"][0]["date"]="2028-01-01"
        with self.assertRaisesRegex(ValueError,"dates do not match"):
            compare_matched(full,scoped,"panel","subcategory","hydrology/surface_flow")


class EndToEndTests(unittest.TestCase):
    def test_full_station_and_scoped_prototypes_with_layered_visuals(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            daily=root/"daily"
            daily.mkdir()
            pid=setup_panel(daily)
            out=root/"m8"
            report=train_m8([daily],out,dpi=75)
            self.assertEqual(report["n_fitted_dataset_models"],1)
            self.assertEqual(report["n_station_local_specialist_fits"],3)
            self.assertEqual(report["regional_subcategory_experts_trained"],0)
            self.assertEqual(report["regional_category_experts_trained"],0)
            self.assertEqual(report["overall_experts_trained"],0)
            full=out/"levels"/"dataset"/pid
            flow=out/"levels"/"subcategory"/"hydrology"/"surface_flow"/pid
            hydro=out/"levels"/"category"/"hydrology"/pid
            wq=out/"levels"/"category"/"water_quality"/pid
            single=out/"levels"/"subcategory"/"water_quality"/"thermal_conditions"/pid
            self.assertTrue((full/"FINDINGS.md").exists())
            self.assertTrue((full/"DATA.md").exists())
            for target in [flow,hydro,wq]:
                self.assertTrue((target/"edge_weights.csv").exists())
                self.assertTrue((target/"matched_full_comparison.csv").exists())
                self.assertTrue((target/"visuals"/"network.svg").exists())
                self.assertTrue((target/"visuals"/"edge_weight_heatmap.png").exists())
                self.assertTrue((target/"visuals"/"baseline_comparison.png").exists())
                self.assertTrue((target/"visuals"/"heldout_hindcast.svg").exists())
                ElementTree.parse(target/"visuals"/"network.svg")
                content=(target/"fcm_model.json").read_text()
                self.assertIn('"regional_category_expert": false',content)
            self.assertTrue((single/"STATUS.md").exists())
            self.assertFalse((single/"fcm_model.json").exists())
            self.assertTrue((out/"levels"/"overall"/"FINDINGS.md").exists())
            self.assertTrue((out/"levels"/"overall"/"visuals"/"training_status.png").exists())
            self.assertTrue((out/"levels"/"category"/"hydrology"/"visuals"/"station_skill.png").exists())
            self.assertTrue((out/"levels"/"subcategory"/"hydrology"/"surface_flow"/"visuals"/"station_skill.png").exists())
            self.assertTrue((out/"matched_specialist_comparisons.csv").exists())
            self.assertTrue((out/"model_registry.csv").exists())
            self.assertTrue((out/"INDEX.md").exists())
            with self.assertRaisesRegex(ValueError,"new/empty"):
                train_m8([daily],out,dpi=75)

    def test_repeated_panel_ids_block_cross_snapshot_accidental_merge(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a,b=root/"a",root/"b"
            a.mkdir();b.mkdir()
            setup_panel(a)
            setup_panel(b)
            with self.assertRaisesRegex(ValueError,"duplicate panel ID"):
                train_m8([a,b],root/"out",dpi=75)

    def test_insufficient_data_never_fits_or_invents_specialists(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            daily=root/"daily"
            daily.mkdir()
            pid=setup_panel(daily,days=55)
            out=root/"m8"
            result=train_m8([daily],out,dpi=75)
            self.assertEqual(result["n_fitted_dataset_models"],0)
            self.assertEqual(result["n_station_local_specialist_fits"],0)
            self.assertTrue((out/"levels"/"dataset"/pid/"STATUS.md").exists())
            self.assertFalse((out/"levels"/"dataset"/pid/"fcm_model.json").exists())
            self.assertTrue((out/"levels"/"overall"/"STATUS.md").exists())


class BatchPlannerTests(unittest.TestCase):
    def test_whole_panel_batches_preserve_source_and_query_caps(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            src=root/"candidate.csv"
            rows=plan_rows("panel_a","USGS-1")+plan_rows("panel_b","USGS-2")
            write_csv(src,rows,PLAN_COLS)
            result=plan_batches(src,root/"batches",max_requests=40)
            self.assertEqual(result["n_batches"],2)
            self.assertEqual(result["n_planned_panels"],2)
            self.assertEqual(result["n_expected_requests"],72)
            for i in (1,2):
                b=root/"batches"/f"batch_{i:02d}"
                self.assertTrue((b/"history_plan.csv").exists())
                info=json.loads((b/"batch_manifest.json").read_text())
                self.assertFalse(info["identity_verified"])
                self.assertLessEqual(info["max_expected_requests"],40)
            with self.assertRaisesRegex(ValueError,"new/empty"):
                plan_batches(src,root/"batches",max_requests=40)

    def test_exclusion_and_hard_request_cap(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/"source.csv"
            write_csv(src,plan_rows("panel_a","USGS-1")+
                      plan_rows("panel_b","USGS-2"),PLAN_COLS)
            out=plan_batches(src,root/"batch1",max_requests=40,
                             exclude_sites=["USGS-1"])
            self.assertEqual(out["n_planned_panels"],1)
            with self.assertRaisesRegex(ValueError,"above single-batch limit"):
                plan_batches(src,root/"batch2",max_requests=30)


if __name__=="__main__":
    unittest.main()
