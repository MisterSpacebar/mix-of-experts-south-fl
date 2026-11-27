# hydrology: within-station category prototype

USGS-255432081303900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, gage_height.
Consecutive observed one-day pairs: 176; train 105, validation 35, test 36.
Chronological test interval: 2026-10-17 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 146.1682 | 171.3413 | 176.4471 | ft^3/s |
| gage_height | 0.2097 | 0.2060 | 0.1986 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| discharge | 146.1682 | 143.3725 | +2.7957 |
| gage_height | 0.2097 | 0.1895 | +0.0202 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
