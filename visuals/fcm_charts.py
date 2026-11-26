"""Load and summarize scripts/preview_fcm.py outputs for visualization.

No plotting here; this module only reads existing CSV/JSON artifacts and
derives tidy per-panel and per-concept summary rows. Nothing is fabricated:
a panel missing its expected files is skipped with an explicit note rather
than silently treated as zero.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from .common import read_csv, to_float

METRIC_COLUMNS = [
    "concept", "n_test_pairs", "fcm_mae", "fcm_rmse", "self_ar_mae",
    "persistence_mae", "train_climatology_mae", "fcm_vs_persistence_mae_delta",
    "fcm_vs_self_ar_mae_delta", "test_target_mean", "unit_note",
]
CONCEPT_SUMMARY_COLUMNS = ["panel_id", "region", "site_id"] + METRIC_COLUMNS
SUMMARY_COLUMNS = [
    "panel_id", "region", "site_id", "n_concepts", "n_test_pairs", "concepts",
    "beats_persistence", "beats_self_ar", "mean_fcm_mae", "mean_self_ar_mae",
    "mean_persistence_mae", "mean_climatology_mae", "mean_delta_persistence",
    "mean_delta_self_ar", "best_concept_vs_self_ar", "best_delta_self_ar",
    "worst_concept_vs_self_ar", "worst_delta_self_ar",
]


def load_manifest(preview_dir: Path):
    path = Path(preview_dir) / "preview_manifest.json"
    if not path.exists():
        raise ValueError(f"missing preview_manifest.json under {preview_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def discover_panel_dirs(preview_dir):
    """Return [(panel_id, Path)] for panels the preview actually trained.

    Skipped/failed panels (per preview_manifest.json) are intentionally
    excluded: there is nothing real to visualize for them.
    """
    preview_dir = Path(preview_dir)
    manifest = load_manifest(preview_dir)
    discovered = []
    for item in manifest.get("results", []):
        if item.get("status") != "trained_preview":
            continue
        panel_id = item["panel_id"]
        panel_dir = preview_dir / panel_id
        if panel_dir.is_dir():
            discovered.append((panel_id, panel_dir))
    return discovered


def panel_region_site(manifest, panel_id):
    """Look up region/site_id from the daily-panel readiness ledger.

    This is metadata for chart labeling only; if it cannot be found the
    panel is still rendered, with region/site_id left blank rather than
    guessed from the panel_id string.
    """
    input_panels = manifest.get("input_panels")
    if not input_panels:
        return "", ""
    readiness_path = Path(input_panels) / "panel_readiness.csv"
    if not readiness_path.exists():
        return "", ""
    for row in read_csv(readiness_path):
        if row.get("panel_id") == panel_id:
            return row.get("region", ""), row.get("site_id", "")
    return "", ""


def load_metrics(panel_dir):
    path = Path(panel_dir) / "heldout_metrics.csv"
    if not path.exists():
        raise ValueError(f"missing heldout_metrics.csv under {panel_dir}")
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"heldout_metrics.csv under {panel_dir} has no rows")
    for row in rows:
        for col in ("n_test_pairs", "fcm_mae", "fcm_rmse", "self_ar_mae",
                    "persistence_mae", "train_climatology_mae",
                    "fcm_vs_persistence_mae_delta", "fcm_vs_self_ar_mae_delta",
                    "test_target_mean"):
            value = to_float(row.get(col))
            if value is None:
                raise ValueError(f"non-numeric {col!r} in {path}")
            row[col] = value
    return rows


def summarize_panel(panel_id, region, site_id, metrics):
    """One aggregate row per panel; NOT a claim of panel-level model skill
    beyond the mean of per-concept held-out MAE deltas it reports.
    """
    beats_persistence = sum(m["fcm_vs_persistence_mae_delta"] < 0 for m in metrics)
    beats_self_ar = sum(m["fcm_vs_self_ar_mae_delta"] < 0 for m in metrics)
    best = min(metrics, key=lambda m: m["fcm_vs_self_ar_mae_delta"])
    worst = max(metrics, key=lambda m: m["fcm_vs_self_ar_mae_delta"])
    return {
        "panel_id": panel_id, "region": region, "site_id": site_id,
        "n_concepts": len(metrics),
        "n_test_pairs": metrics[0]["n_test_pairs"],
        "concepts": ";".join(m["concept"] for m in metrics),
        "beats_persistence": beats_persistence,
        "beats_self_ar": beats_self_ar,
        "mean_fcm_mae": mean(m["fcm_mae"] for m in metrics),
        "mean_self_ar_mae": mean(m["self_ar_mae"] for m in metrics),
        "mean_persistence_mae": mean(m["persistence_mae"] for m in metrics),
        "mean_climatology_mae": mean(m["train_climatology_mae"] for m in metrics),
        "mean_delta_persistence": mean(m["fcm_vs_persistence_mae_delta"] for m in metrics),
        "mean_delta_self_ar": mean(m["fcm_vs_self_ar_mae_delta"] for m in metrics),
        "best_concept_vs_self_ar": best["concept"],
        "best_delta_self_ar": best["fcm_vs_self_ar_mae_delta"],
        "worst_concept_vs_self_ar": worst["concept"],
        "worst_delta_self_ar": worst["fcm_vs_self_ar_mae_delta"],
    }


def concept_summary_rows(panel_id, region, site_id, metrics):
    rows = []
    for m in metrics:
        row = {"panel_id": panel_id, "region": region, "site_id": site_id}
        row.update({col: m[col] for col in METRIC_COLUMNS})
        rows.append(row)
    return rows


def load_edge_matrix(panel_dir):
    """Return (concepts, matrix) with matrix[row=source][col=target].

    Order is first-seen in edge_weights.csv, which preview_fcm.py writes
    deterministically (concept order from the fitted model).
    """
    path = Path(panel_dir) / "edge_weights.csv"
    if not path.exists():
        raise ValueError(f"missing edge_weights.csv under {panel_dir}")
    rows = read_csv(path)
    concepts = []
    for row in rows:
        for key in ("source_concept", "target_concept"):
            if row[key] not in concepts:
                concepts.append(row[key])
    index = {c: i for i, c in enumerate(concepts)}
    matrix = [[0.0] * len(concepts) for _ in concepts]
    for row in rows:
        weight = to_float(row.get("weight"))
        if weight is None:
            raise ValueError(f"non-numeric edge weight in {path}")
        matrix[index[row["source_concept"]]][index[row["target_concept"]]] = weight
    return concepts, matrix
