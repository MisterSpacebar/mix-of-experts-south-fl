# hydrology/surface_flow: within-station subcategory prototype

USGS-255327081275900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, gage_height.
Consecutive observed one-day pairs: 161; train 96, validation 32, test 33.
Chronological test interval: 2026-10-20 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 23.5288 | 25.3663 | 26.5467 | ft^3/s |
| gage_height | 0.1966 | 0.1870 | 0.1777 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| discharge | 23.5288 | 24.0587 | -0.5299 |
| gage_height | 0.1966 | 0.1709 | +0.0257 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.

## Redundant concept scope

This scope contains exactly the same station/concepts as `levels/category/hydrology/panel_01_USGS_255327081275900`. The separately invoked deterministic fit does **not** add independent observational evidence.
