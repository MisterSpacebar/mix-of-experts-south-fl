# water_quality: within-station category prototype

USGS-255327081275900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature.
Consecutive observed one-day pairs: 161; train 96, validation 32, test 33.
Chronological test interval: 2026-10-20 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 1.0101 | 0.9895 | 0.7525 | ppt |
| water_temperature | 2.0831 | 2.0125 | 0.5438 | degC |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 1.0101 | 1.1490 | -0.1389 |
| water_temperature | 2.0831 | 2.1035 | -0.0204 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
