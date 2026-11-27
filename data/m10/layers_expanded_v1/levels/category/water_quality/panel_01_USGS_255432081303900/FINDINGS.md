# water_quality: within-station category prototype

USGS-255432081303900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature.
Consecutive observed one-day pairs: 176; train 105, validation 35, test 36.
Chronological test interval: 2026-10-17 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 1.7832 | 1.7711 | 1.7266 | ppt |
| water_temperature | 2.0952 | 2.0450 | 0.5131 | degC |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 1.7832 | 1.5706 | +0.2126 |
| water_temperature | 2.0952 | 2.1114 | -0.0162 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
