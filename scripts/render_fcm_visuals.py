"""Render tidy visualization outputs for an existing FCM preview directory.

Input is the output of scripts/preview_fcm.py (a fcm_preview_* directory with
a preview_manifest.json and one subdirectory per trained panel). This script
does not fit models, download data, or modify the original preview outputs.
It creates a NEW directory (default: <preview>/visuals) with:

- panels/<panel_id>/baseline_comparison.png
- panels/<panel_id>/edge_weight_heatmap.png
- cross_panel/panel_summary.csv
- cross_panel/concept_summary.csv
- cross_panel/cross_panel_performance_summary.png
- visuals_manifest.json

python scripts/render_fcm_visuals.py --preview data/m7/fcm_preview_verified_02
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visuals.render import render_all


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preview", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--dpi", type=int, default=180)
    a = p.parse_args()
    report = render_all(a.preview, a.out, dpi=a.dpi)
    dest = a.out or (a.preview / "visuals")
    print(f"Rendered visuals for {report['n_panels']} panels -> {dest}")
    if not report["n_panels"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
