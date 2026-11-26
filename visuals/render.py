"""Matplotlib rendering for FCM preview outputs.

Pure post-processing: reads scripts/preview_fcm.py's own CSV/JSON artifacts
and writes PNG charts plus tidy summary CSVs into a NEW directory. Never
overwrites the original preview, never fits a model, never interpolates
missing values, and never claims causal effects or operational readiness.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from .common import ensure_clean_dir, write_csv
from .fcm_charts import (
    CONCEPT_SUMMARY_COLUMNS, SUMMARY_COLUMNS, concept_summary_rows,
    discover_panel_dirs, load_edge_matrix, load_manifest, load_metrics,
    panel_region_site, summarize_panel,
)

CAVEAT = ("Held-out one-day-ahead comparison only. Weights are standardized "
          "predictive associations, NOT demonstrated causal effects.")


def plot_baseline_comparison(panel_dir, out_path, dpi=180):
    metrics = load_metrics(panel_dir)
    concepts = [m["concept"] for m in metrics]
    series = ["fcm_mae", "self_ar_mae", "persistence_mae", "train_climatology_mae"]
    labels = ["Dynamic FCM", "Self-AR(1)", "Persistence", "Train climatology"]
    x = np.arange(len(concepts))
    width = 0.8 / len(series)
    fig, ax = plt.subplots(figsize=(max(6.5, 1.6 * len(concepts) + 2), 5.2))
    for i, (key, label) in enumerate(zip(series, labels)):
        offset = (i - (len(series) - 1) / 2) * width
        ax.bar(x + offset, [m[key] for m in metrics], width, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in concepts])
    ax.set_ylabel("Held-out MAE (native source units; not comparable across concepts)")
    ax.set_title(f"Baseline comparison — {Path(panel_dir).name}")
    ax.legend(frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.text(0.01, 0.01, CAVEAT, fontsize=8, color="#555555")
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def plot_edge_weight_heatmap(panel_dir, out_path, dpi=180):
    concepts, matrix = load_edge_matrix(panel_dir)
    arr = np.array(matrix, dtype=float)
    vmax = max(abs(arr.min()), abs(arr.max()), 1e-6)
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    im = ax.imshow(
        arr,
        cmap="coolwarm",
        norm=TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax),
    )
    ax.set_xticks(np.arange(len(concepts)))
    ax.set_yticks(np.arange(len(concepts)))
    ax.set_xticklabels([c.replace("_", "\n") for c in concepts])
    ax.set_yticklabels([c.replace("_", " ") for c in concepts])
    plt.setp(ax.get_xticklabels(), rotation=0, ha="center")
    ax.set_xlabel("Target concept")
    ax.set_ylabel("Source concept")
    ax.set_title(f"Edge-weight heatmap — {Path(panel_dir).name}", loc="left", fontsize=12)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, f"{arr[i, j]:+.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.85, label="Signed standardized weight")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.text(0.01, 0.01, CAVEAT, fontsize=8, color="#555555")
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def plot_cross_panel_summary(panel_rows, out_path, dpi=180):
    panels = [r["panel_id"] for r in panel_rows]
    y = np.arange(len(panels))
    h = 0.35
    fig, ax = plt.subplots(figsize=(10, max(4.8, 1.2 + len(panels) * 0.8)))
    ax.barh(y + h / 2, [r["mean_delta_persistence"] for r in panel_rows], h,
            label="FCM minus Persistence")
    ax.barh(y - h / 2, [r["mean_delta_self_ar"] for r in panel_rows], h,
            label="FCM minus Self-AR")
    ax.axvline(0, linewidth=1.0, color="black")
    ax.set_yticks(y)
    ax.set_yticklabels(panels)
    ax.set_xlabel("Mean MAE delta across concepts (negative = FCM better)")
    ax.set_title("Cross-panel performance summary")
    ax.legend(frameon=False)
    for i, row in enumerate(panel_rows):
        note = (f"beats P {row['beats_persistence']}/{row['n_concepts']} | "
                f"beats AR {row['beats_self_ar']}/{row['n_concepts']}")
        edge = max(row["mean_delta_persistence"], row["mean_delta_self_ar"], 0)
        ax.text(edge + 0.02, i, note, va="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.text(0.01, 0.01, CAVEAT, fontsize=8, color="#555555")
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def render_all(preview_dir, out_dir=None, dpi=180):
    preview_dir = Path(preview_dir)
    manifest = load_manifest(preview_dir)
    out_dir = ensure_clean_dir(out_dir or (preview_dir / "visuals"))
    panel_dirs = discover_panel_dirs(preview_dir)

    panel_summaries, concept_rows, panel_entries = [], [], []
    for panel_id, panel_dir in panel_dirs:
        region, site_id = panel_region_site(manifest, panel_id)
        metrics = load_metrics(panel_dir)
        panel_out = out_dir / "panels" / panel_id
        panel_out.mkdir(parents=True, exist_ok=True)
        plot_baseline_comparison(panel_dir, panel_out / "baseline_comparison.png", dpi=dpi)
        plot_edge_weight_heatmap(panel_dir, panel_out / "edge_weight_heatmap.png", dpi=dpi)
        panel_summaries.append(summarize_panel(panel_id, region, site_id, metrics))
        concept_rows.extend(concept_summary_rows(panel_id, region, site_id, metrics))
        panel_entries.append({
            "panel_id": panel_id,
            "baseline_comparison": str(panel_out / "baseline_comparison.png"),
            "edge_weight_heatmap": str(panel_out / "edge_weight_heatmap.png"),
        })

    cross_panel = out_dir / "cross_panel"
    write_csv(cross_panel / "panel_summary.csv", panel_summaries, SUMMARY_COLUMNS)
    write_csv(cross_panel / "concept_summary.csv", concept_rows, CONCEPT_SUMMARY_COLUMNS)
    cross_panel_png = None
    if panel_summaries:
        cross_panel_png = cross_panel / "cross_panel_performance_summary.png"
        plot_cross_panel_summary(panel_summaries, cross_panel_png, dpi=dpi)

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_preview": str(preview_dir),
        "n_panels": len(panel_summaries),
        "panel_ids": [r["panel_id"] for r in panel_summaries],
        "panels": panel_entries,
        "cross_panel_summary_csv": str(cross_panel / "panel_summary.csv"),
        "cross_panel_concept_csv": str(cross_panel / "concept_summary.csv"),
        "cross_panel_performance_png": str(cross_panel_png) if cross_panel_png else "",
        "causal_discovery": False,
        "operational_ready": False,
        "note": CAVEAT,
    }
    (out_dir / "visuals_manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
