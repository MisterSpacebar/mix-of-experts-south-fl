# hydrology/surface_flow: within-station subcategory prototype

USGS-255534081324000 · southwest_everglades_coast. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, gage_height.
Consecutive observed one-day pairs: 152; train 91, validation 30, test 31.
Chronological test interval: 2026-10-20 through 2026-11-23.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 7.0428 | 7.2573 | 7.7307 | ft^3/s |
| gage_height | 0.1720 | 0.1921 | 0.1782 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| discharge | 7.0428 | 8.4662 | -1.4234 |
| gage_height | 0.1720 | 0.1914 | -0.0194 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.

## Redundant concept scope

This scope contains exactly the same station/concepts as `levels/category/hydrology/panel_02_USGS_255534081324000`. The separately invoked deterministic fit does **not** add independent observational evidence.
