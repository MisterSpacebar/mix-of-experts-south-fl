"""Offline chronological FCM and preview artifact regression tests."""
import json,math,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from southfl.fcm_model import fit_preview,NotReadyError,build_pairs
from southfl.fcm_figures import network_svg,hindcast_svg
from southfl.net import write_csv
from southfl.panels import PANEL_SUMMARY_COLS
from scripts.preview_fcm import run

CONCEPTS=["salinity","water_temperature","discharge"]


def synthetic(n=165):
    a,b,c=10.0,22.0,30.0
    day=date(2026,1,1)
    out=[]
    for i in range(n):
        out.append(dict(
            date=(day+timedelta(days=i)).isoformat(),
            site_id="USGS-TEST",panel_id="panel_test",
            salinity=a,water_temperature=b,discharge=c,
        ))
        aa=.84*a+.013*c+.12*math.sin(i/9)+.7
        bb=.78*b+.10*a+.5*math.cos(i/13)+1.1
        cc=.67*c-.22*a+.2*math.sin(i/4)+4.5
        a,b,c=aa,bb,cc
    return out


class ModelTests(unittest.TestCase):
    def test_train_validation_test_is_chronological(self):
        result=fit_preview(synthetic(),CONCEPTS)
        self.assertEqual(result["n_pairs"],164)
        self.assertEqual(result["train_pairs"]+result["validation_pairs"]+
                         result["test_pairs"],164)
        self.assertLess(result["train_end"],result["validation_start"])
        self.assertLess(result["validation_end"],result["test_start"])
        self.assertTrue(result["forecast_type"].startswith("one-day-ahead"))
        self.assertEqual(len(result["evaluation"]),3)
        self.assertEqual(len(result["self_ar_alphas"]),3)
        self.assertTrue(all(x in (0.1,1.0,10.0,50.0) for x in result["self_ar_alphas"]))
        self.assertEqual(len(result["rollout"]),21)
        self.assertTrue(all(-1<=x<=1 for row in result["matrix_source_to_target"]
                            for x in row))
        self.assertTrue(all(r["interpretation"].endswith("NOT demonstrated causality")
                            for r in result["edges"]))

    def test_train_weights_do_not_depend_on_test_target_changes(self):
        rows=synthetic()
        before=fit_preview(rows,CONCEPTS)
        # Test tail can change, but cannot influence train scaler or selected
        # ridge parameter. Only the evaluation and rollout may change.
        modified=[dict(r) for r in rows]
        for r in modified[-23:]:
            r["salinity"]+=200
            r["discharge"]-=50
        after=fit_preview(modified,CONCEPTS)
        self.assertEqual(before["ridge_alpha"],after["ridge_alpha"])
        self.assertEqual(before["normalization_mean"],after["normalization_mean"])
        self.assertEqual(before["matrix_source_to_target"],
                         after["matrix_source_to_target"])

    def test_missing_day_is_not_interpolated(self):
        rows=synthetic(95)
        rows.pop(12)
        pairs=build_pairs(rows,CONCEPTS)
        self.assertEqual(len(pairs),92)  # lost two transitions bordering missing date

    def test_missing_values_rejected(self):
        rows=synthetic()
        rows[10]["salinity"]=""
        with self.assertRaisesRegex(NotReadyError,"missing"):
            fit_preview(rows,CONCEPTS)

    def test_cross_site_model_refused(self):
        rows=synthetic()
        rows[-1]["site_id"]="USGS-OTHER"
        with self.assertRaisesRegex(NotReadyError,"cross-site"):
            fit_preview(rows,CONCEPTS)

    def test_short_series_not_fitted(self):
        with self.assertRaisesRegex(NotReadyError,"require"):
            fit_preview(synthetic(70),CONCEPTS)

    def test_visuals_self_contained_and_caveated(self):
        model=fit_preview(synthetic(),CONCEPTS)
        diagram=network_svg(model)
        chart=hindcast_svg(model,"salinity")
        self.assertIn("NOT inferred causal effects",diagram)
        self.assertIn("<svg",chart)
        self.assertIn("previous observed day",chart)

    def test_edges_keyed_by_concept_name_not_loop_index(self):
        # Regression: edges previously stored the enumerate() loop index
        # (an int) instead of the concept name, which crashed network_svg's
        # name-keyed point lookup with KeyError once any cross-concept
        # weight passed its drawing threshold.
        model=fit_preview(synthetic(),CONCEPTS)
        for edge in model["edges"]:
            self.assertIn(edge["source_concept"],CONCEPTS)
            self.assertIn(edge["target_concept"],CONCEPTS)

    def test_network_svg_renders_strong_cross_concept_edge(self):
        concepts=["a","b"]
        day=date(2026,1,1)
        rows=[]
        a,b=10.0,5.0
        for i in range(165):
            rows.append(dict(date=(day+timedelta(days=i)).isoformat(),
                             site_id="USGS-TEST",panel_id="panel_test",a=a,b=b))
            a,b=.5*a+.01*(i%7),.9*a+.01*(i%5)
        model=fit_preview(rows,concepts)
        strongest=max(r["weight"] for r in model["edges"]
                     if r["edge_kind"]=="cross_concept")
        self.assertGreaterEqual(abs(strongest),.08)
        diagram=network_svg(model)
        self.assertIn("<svg",diagram)
        self.assertIn("self ",diagram)

    def test_cli_writes_outputs_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            panels=Path(td)/"panels"
            panels.mkdir()
            write_csv(panels/"panel_test.csv",synthetic(),
                      ["date","site_id","panel_id"]+CONCEPTS)
            write_csv(panels/"panel_readiness.csv",[dict(
                panel_id="panel_test",region="caloosahatchee",
                site_id="USGS-TEST",concepts=";".join(CONCEPTS),
                status="candidate_for_held_out_evaluation")],
                PANEL_SUMMARY_COLS)
            (panels/"panels_manifest.json").write_text(
                json.dumps({"observation_source":"synthetic_test_only"}))
            dest=Path(td)/"preview"
            result=run(panels,dest)
            self.assertEqual(result["n_fitted_previews"],1)
            self.assertTrue((dest/"panel_test/fcm_network.svg").exists())
            self.assertTrue((dest/"panel_test/heldout_hindcast.svg").exists())
            self.assertTrue((dest/"panel_test/heldout_metrics.csv").exists())
            with self.assertRaisesRegex(ValueError,"new output"):
                run(panels,dest)

    def test_renderer_keyerror_is_reported_as_failure_not_readiness_skip(self):
        # Regression: a previous network_svg KeyError(3) was swallowed as
        # a 'skipped — 3' panel, even though model training had succeeded.
        with tempfile.TemporaryDirectory() as td:
            panels=Path(td)/"panels"
            panels.mkdir()
            write_csv(panels/"panel_test.csv",synthetic(),
                      ["date","site_id","panel_id"]+CONCEPTS)
            write_csv(panels/"panel_readiness.csv",[dict(
                panel_id="panel_test",region="caloosahatchee",
                site_id="USGS-TEST",concepts=";".join(CONCEPTS),
                status="candidate_for_held_out_evaluation")],
                PANEL_SUMMARY_COLS)
            (panels/"panels_manifest.json").write_text("{}")
            dest=Path(td)/"preview"
            with patch("scripts.preview_fcm.network_svg",
                       side_effect=KeyError(3)):
                with self.assertRaisesRegex(
                        RuntimeError,"FCM preview processing failed for panel_test: KeyError: 3"):
                    run(panels,dest)
            # Rendering is preflighted before any per-panel outputs are saved.
            self.assertFalse((dest/"panel_test").exists())

    def test_model_schema_valueerror_is_not_a_readiness_skip(self):
        with tempfile.TemporaryDirectory() as td:
            panels=Path(td)/"panels"
            panels.mkdir()
            write_csv(panels/"panel_test.csv",synthetic(),
                      ["date","site_id","panel_id"]+CONCEPTS)
            write_csv(panels/"panel_readiness.csv",[dict(
                panel_id="panel_test",region="big_cypress",
                site_id="USGS-TEST",concepts=";".join(CONCEPTS),
                status="candidate_for_held_out_evaluation")],
                PANEL_SUMMARY_COLS)
            (panels/"panels_manifest.json").write_text("{}")
            with patch("scripts.preview_fcm.fit_preview",
                       side_effect=ValueError("malformed panel")):
                with self.assertRaisesRegex(
                        RuntimeError,"panel_test: ValueError: malformed panel"):
                    run(panels,Path(td)/"preview")

    def test_genuine_readiness_exception_remains_a_skip(self):
        with tempfile.TemporaryDirectory() as td:
            panels=Path(td)/"panels"
            panels.mkdir()
            write_csv(panels/"panel_test.csv",synthetic(55),
                      ["date","site_id","panel_id"]+CONCEPTS)
            write_csv(panels/"panel_readiness.csv",[dict(
                panel_id="panel_test",region="big_cypress",
                site_id="USGS-TEST",concepts=";".join(CONCEPTS),
                status="candidate_for_held_out_evaluation")],
                PANEL_SUMMARY_COLS)
            (panels/"panels_manifest.json").write_text("{}")
            report=run(panels,Path(td)/"preview")
            self.assertEqual(report["n_fitted_previews"],0)
            self.assertEqual(report["n_skipped"],1)
            self.assertIn("require",report["results"][0]["reason"])

    def test_insufficient_panel_produces_skip_not_fake_model(self):
        with tempfile.TemporaryDirectory() as td:
            panels=Path(td)/"panels"
            panels.mkdir()
            write_csv(panels/"panel_readiness.csv",[
                dict(panel_id="p1",region="lower_keys",site_id="USGS-1",
                     concepts="salinity;water_temperature",
                     status="insufficient_consecutive_observation_days")],
                PANEL_SUMMARY_COLS)
            (panels/"panels_manifest.json").write_text("{}")
            result=run(panels,Path(td)/"output")
            self.assertEqual(result["n_fitted_previews"],0)
            self.assertEqual(result["results"][0]["status"],"skipped")
            self.assertFalse((Path(td)/"output/p1").exists())


if __name__=="__main__":
    unittest.main()
