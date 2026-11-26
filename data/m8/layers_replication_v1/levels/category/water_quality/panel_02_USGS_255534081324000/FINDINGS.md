# water_quality: within-station category prototype

USGS-255534081324000 · southwest_everglades_coast. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature.
Consecutive observed one-day pairs: 152; train 91, validation 30, test 31.
Chronological test interval: 2026-10-20 through 2026-11-23.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 1.4567 | 1.4038 | 1.2481 | ppt |
| water_temperature | 1.3973 | 1.2892 | 0.4944 | degC |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 1.4567 | 1.3776 | +0.0791 |
| water_temperature | 1.3973 | 1.4493 | -0.0519 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
