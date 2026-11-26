# FCM visuals — scientific reporting and hierarchy scaffolding

This package **visualizes existing trained station-level FCM previews**. It
does not train or infer separate subcategory, category, or South Florida-wide
FCMs. The hierarchy directories are concept/edge *views of existing fitted
panels* and an explicit inventory of layers yet to be trained.

## GitHub Actions dependency fix

The visualization tests import Matplotlib. GitHub Actions must install the
committed `requirements.txt` before `python -m unittest discover -s tests -v`.
This PR adds that step; locally use `python -m pip install -r requirements.txt`.
No agency API credentials or downloads are needed.

## Run on the existing 41,341-observation model preview

From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v

# Use a NEW output directory if prior visuals exist. Neither the model nor
# the source CSV/JSON files are touched.
python scripts/render_fcm_visuals.py --preview data/m7/fcm_preview_verified_02 --out data/m7/fcm_preview_verified_02/visuals_v2
```

## File structure

```text
visuals_v2/
  panels/
    <panel_id>/
      baseline_comparison.png             # MAE / persistence MAE by concept
      edge_weight_heatmap.png             # source-concept × target-concept
  cross_panel/
    panel_summary.csv                     # dimensionaless median skill
    concept_summary.csv                   # native MAEs + per-concept skill
    cross_panel_performance_summary.png   # scale-free median skill
  hierarchy/
    concept_coverage.csv                  # grouped by category/subcategory
    hierarchy_status.csv                  # actual trained vs not trained
    subcategory_coverage.png              # concept counts, not model skill
    hierarchy_overview.png                # trained vs planned levels
    cross_subcategory_edges.csv           # raw directed links crossing groups
    all_classified_edges.csv              # every original learned edge
    panels/
      <panel_id>/
        concept_assignments.csv
        classified_edges.csv
        subcategory_grouped_heatmap.png    # SAME fitted edge matrix, reordered
    subcategories/
      <category>/
        <subcategory>/
          <panel_id>_internal_edges.csv    # view of already learned edges
    categories/
      <category>/
        <panel_id>_concepts.csv            # concept membership only
  visuals_manifest.json
```

No category-level or subcategory-level weight matrix is manufactured, and
cross-category edges remain in the cross-subcategory ledger rather than being
hidden. The current four-variable USGS panel spans at least hydrology
(surface flow: discharge/gage height) and water quality (salinity and thermal
conditions): a single **mixed-concept dataset expert**, not four independent
subcategory experts.

**The concept taxonomy is versioned**, defined in `visuals/hierarchy.py`,
and conservatively maps known measurement concepts only. Unrecognized
concepts are `unclassified`, not guessed. Category/source identities in
`catalog/datasets.json` describe agency datasets; this visual taxonomy
describes individual modeled environmental concepts. A USGS station can
therefore contain both hydrology and water-quality concepts.

## Performance scale matters

Discharge, stage, salinity and temperature have incompatible native units.
Cross-concept raw MAEs or absolute MAE *differences* must not be averaged.
The baseline comparison now plots **MAE / persistence MAE** for each
concept (persistence=1, lower is better). The cross-panel chart plots the
median over **dimensionless skill** scores:

```text
Skill = 1 - MAE_FCM / MAE_baseline
```

Positive skill favors FCM; negative favors the baseline. When a baseline
achieves zero MAE, its skill is **undefined**, excluded from the median,
and counted as unavailable; it is not forced to zero or infinity.
Raw native-unit MAEs and the original model results remain available for
reporting per concept.

These are single-held-out-period, one-day-ahead, previous-observation-
conditioned predictive comparisons, not calibrated uncertainty or causal
effects. A category-level visualization of concept membership is not
evidence of a trained category expert.

## To obtain actual hierarchical FCMs later

1. Fit multiple independently validated, spatially and temporally supported
   **dataset/subcategory experts**, instead of partitioning one station
   weight matrix and claiming independent learned models.
2. Train/validate **category-level experts and gating/aggregation** across
   compatible stations and data streams; retain physical units, datums,
   sampling cadence and holdout separation.
3. Estimate and test **cross-category coupling/overall expert** with
   correctly lagged evidence rather than summing weights from unrelated
   station panels.

Until then, `hierarchy_status.csv` deliberately marks all subcategory,
category and overall FCMs **not_trained**, even if concepts appear under
their descriptive taxonomy. This is the intended architecture without
overstating implementation.
