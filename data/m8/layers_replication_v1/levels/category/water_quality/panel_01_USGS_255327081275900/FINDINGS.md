# water_quality: within-station category prototype

USGS-255327081275900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature.
Consecutive observed one-day pairs: 89; train 53, validation 17, test 19.
Chronological test interval: 2026-10-08 through 2026-10-30.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 1.7080 | 1.6186 | 0.9359 | ppt |
| water_temperature | 1.5579 | 1.5566 | 0.4857 | degC |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 1.7080 | 1.7558 | -0.0478 |
| water_temperature | 1.5579 | 1.5274 | +0.0305 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
