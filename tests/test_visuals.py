"""Offline regression tests for the visuals package.

No network access, no model fitting: fixtures mimic scripts/preview_fcm.py's
own output format exactly (same CSV columns, same manifest shape) so these
tests only exercise the rendering/summarization logic.
"""
import json
import tempfile
import unittest
from pathlib import Path

from visuals.common import write_csv
from visuals.fcm_charts import (
    METRIC_COLUMNS, discover_panel_dirs, load_edge_matrix, load_metrics,
    panel_region_site, summarize_panel,
)
from visuals.render import render_all

METRICS_ROWS = [
    dict(concept="salinity", n_test_pairs=19, fcm_mae=1.3, fcm_rmse=1.6,
         self_ar_mae=1.2, persistence_mae=1.5, train_climatology_mae=3.4,
         fcm_vs_persistence_mae_delta=-0.2, fcm_vs_self_ar_mae_delta=0.1,
         test_target_mean=15.0, unit_note="ppt"),
    dict(concept="water_temperature", n_test_pairs=19, fcm_mae=0.9, fcm_rmse=1.1,
         self_ar_mae=1.0, persistence_mae=1.3, train_climatology_mae=2.5,
         fcm_vs_persistence_mae_delta=-0.4, fcm_vs_self_ar_mae_delta=-0.1,
         test_target_mean=25.0, unit_note="degC"),
]
EDGE_ROWS = [
    dict(source_concept="salinity", target_concept="salinity", weight=0.80,
         sign="positive", edge_kind="self_memory",
         interpretation="held-out predictive association; NOT demonstrated causality"),
    dict(source_concept="salinity", target_concept="water_temperature", weight=-0.20,
         sign="negative", edge_kind="cross_concept",
         interpretation="held-out predictive association; NOT demonstrated causality"),
    dict(source_concept="water_temperature", target_concept="salinity", weight=0.10,
         sign="positive", edge_kind="cross_concept",
         interpretation="held-out predictive association; NOT demonstrated causality"),
    dict(source_concept="water_temperature", target_concept="water_temperature",
         weight=0.70, sign="positive", edge_kind="self_memory",
         interpretation="held-out predictive association; NOT demonstrated causality"),
]
EDGE_COLUMNS = ["source_concept", "target_concept", "weight", "sign",
               "edge_kind", "interpretation"]


def write_trained_panel(preview_dir, panel_id):
    panel_dir = preview_dir / panel_id
    write_csv(panel_dir / "heldout_metrics.csv", METRICS_ROWS, METRIC_COLUMNS)
    write_csv(panel_dir / "edge_weights.csv", EDGE_ROWS, EDGE_COLUMNS)
    return panel_dir


def write_preview_manifest(preview_dir, results, input_panels=None):
    manifest = {"results": results}
    if input_panels is not None:
        manifest["input_panels"] = str(input_panels)
    (preview_dir / "preview_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8")


class FcmChartsTests(unittest.TestCase):
    def test_discover_panel_dirs_only_trained_previews(self):
        with tempfile.TemporaryDirectory() as td:
            preview = Path(td) / "preview"
            preview.mkdir()
            write_trained_panel(preview, "panel_a")
            write_preview_manifest(preview, [
                {"panel_id": "panel_a", "status": "trained_preview"},
                {"panel_id": "panel_b", "status": "skipped"},
            ])
            found = discover_panel_dirs(preview)
            self.assertEqual([pid for pid, _ in found], ["panel_a"])

    def test_load_metrics_rejects_nonnumeric_field(self):
        with tempfile.TemporaryDirectory() as td:
            panel_dir = Path(td) / "panel_a"
            bad_rows = [dict(METRICS_ROWS[0], fcm_mae="not-a-number")]
            write_csv(panel_dir / "heldout_metrics.csv", bad_rows, METRIC_COLUMNS)
            with self.assertRaisesRegex(ValueError, "non-numeric"):
                load_metrics(panel_dir)

    def test_load_edge_matrix_orders_concepts_and_fills_weights(self):
        with tempfile.TemporaryDirectory() as td:
            panel_dir = Path(td) / "panel_a"
            write_csv(panel_dir / "edge_weights.csv", EDGE_ROWS, EDGE_COLUMNS)
            concepts, matrix = load_edge_matrix(panel_dir)
            self.assertEqual(concepts, ["salinity", "water_temperature"])
            self.assertEqual(matrix[0][0], 0.80)
            self.assertEqual(matrix[0][1], -0.20)
            self.assertEqual(matrix[1][0], 0.10)
            self.assertEqual(matrix[1][1], 0.70)

    def test_panel_region_site_blank_when_readiness_missing(self):
        region, site_id = panel_region_site({"input_panels": None}, "panel_a")
        self.assertEqual((region, site_id), ("", ""))

    def test_summarize_panel_counts_beats_and_extremes(self):
        metrics = load_metrics_from_rows(METRICS_ROWS)
        summary = summarize_panel("panel_a", "big_cypress", "USGS-1", metrics)
        self.assertEqual(summary["n_concepts"], 2)
        self.assertEqual(summary["beats_persistence"], 2)
        self.assertEqual(summary["beats_self_ar"], 1)
        self.assertEqual(summary["best_concept_vs_self_ar"], "water_temperature")
        self.assertEqual(summary["worst_concept_vs_self_ar"], "salinity")


def load_metrics_from_rows(rows):
    # Mirrors fcm_charts.load_metrics' numeric coercion without touching disk.
    out = []
    for row in rows:
        out.append(dict(row))
    return out


class RenderTests(unittest.TestCase):
    def test_render_all_writes_expected_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            preview = Path(td) / "fcm_preview_v1"
            preview.mkdir()
            write_trained_panel(preview, "panel_01_USGS_1")
            write_preview_manifest(preview, [
                {"panel_id": "panel_01_USGS_1", "status": "trained_preview"},
            ])
            report = render_all(preview, preview / "visuals")
            out = preview / "visuals"
            self.assertEqual(report["n_panels"], 1)
            self.assertTrue((out / "panels/panel_01_USGS_1/baseline_comparison.png").exists())
            self.assertTrue((out / "panels/panel_01_USGS_1/edge_weight_heatmap.png").exists())
            self.assertTrue((out / "cross_panel/panel_summary.csv").exists())
            self.assertTrue((out / "cross_panel/concept_summary.csv").exists())
            self.assertTrue((out / "cross_panel/cross_panel_performance_summary.png").exists())
            self.assertTrue((out / "visuals_manifest.json").exists())
            self.assertFalse(report["causal_discovery"])
            self.assertFalse(report["operational_ready"])

    def test_render_all_refuses_nonempty_output_dir(self):
        with tempfile.TemporaryDirectory() as td:
            preview = Path(td) / "fcm_preview_v1"
            preview.mkdir()
            write_trained_panel(preview, "panel_01_USGS_1")
            write_preview_manifest(preview, [
                {"panel_id": "panel_01_USGS_1", "status": "trained_preview"},
            ])
            out = preview / "visuals"
            render_all(preview, out)
            with self.assertRaisesRegex(ValueError, "new/empty"):
                render_all(preview, out)

    def test_render_all_handles_zero_trained_panels(self):
        with tempfile.TemporaryDirectory() as td:
            preview = Path(td) / "fcm_preview_v1"
            preview.mkdir()
            write_preview_manifest(preview, [
                {"panel_id": "panel_01_USGS_1", "status": "skipped"},
            ])
            report = render_all(preview, preview / "visuals")
            self.assertEqual(report["n_panels"], 0)
            self.assertEqual(report["cross_panel_performance_png"], "")
            self.assertTrue((preview / "visuals/cross_panel/panel_summary.csv").exists())

    def test_render_all_populates_region_and_site_from_panel_readiness(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            daily_panels = root / "daily_panels_v1"
            daily_panels.mkdir()
            write_csv(daily_panels / "panel_readiness.csv", [dict(
                panel_id="panel_01_USGS_1", region="big_cypress",
                site_id="USGS-1")], ["panel_id", "region", "site_id"])
            preview = root / "fcm_preview_v1"
            preview.mkdir()
            write_trained_panel(preview, "panel_01_USGS_1")
            write_preview_manifest(preview, [
                {"panel_id": "panel_01_USGS_1", "status": "trained_preview"},
            ], input_panels=daily_panels)
            report = render_all(preview, preview / "visuals")
            rows = list(csv_rows(preview / "visuals/cross_panel/panel_summary.csv"))
            self.assertEqual(rows[0]["region"], "big_cypress")
            self.assertEqual(rows[0]["site_id"], "USGS-1")


def csv_rows(path):
    from visuals.common import read_csv
    return read_csv(path)


if __name__ == "__main__":
    unittest.main()
