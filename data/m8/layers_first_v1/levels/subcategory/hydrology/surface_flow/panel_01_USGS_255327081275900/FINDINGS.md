# hydrology/surface_flow: within-station subcategory prototype

USGS-255327081275900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, gage_height.
Consecutive observed one-day pairs: 89; train 53, validation 17, test 19.
Chronological test interval: 2026-10-08 through 2026-10-30.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 27.6321 | 33.0904 | 36.5636 | ft^3/s |
| gage_height | 0.2351 | 0.2336 | 0.2598 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| discharge | 27.6321 | 31.7944 | -4.1623 |
| gage_height | 0.2351 | 0.2230 | +0.0121 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.

## Redundant concept scope

This scope contains exactly the same station/concepts as `levels/category/hydrology/panel_01_USGS_255327081275900`. The separately invoked deterministic fit does **not** add independent observational evidence.
