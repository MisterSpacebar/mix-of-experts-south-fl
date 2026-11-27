# hydrology/surface_flow: within-station subcategory prototype

USGS-0229070854 · central_south_biscayne. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, gage_height.
Consecutive observed one-day pairs: 176; train 105, validation 35, test 36.
Chronological test interval: 2026-10-20 through 2026-11-24.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 64.4633 | 49.4392 | 28.9659 | ft^3/s |
| gage_height | 0.3249 | 0.3169 | 0.1654 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| discharge | 64.4633 | 92.7174 | -28.2541 |
| gage_height | 0.3249 | 0.2959 | +0.0290 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.

## Redundant concept scope

This scope contains exactly the same station/concepts as `levels/category/hydrology/panel_04_USGS_0229070854`. The separately invoked deterministic fit does **not** add independent observational evidence.
