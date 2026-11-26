# water_quality: within-station category prototype

USGS-0229070854 · central_south_biscayne. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature.
Consecutive observed one-day pairs: 151; train 90, validation 30, test 31.
Chronological test interval: 2026-10-20 through 2026-11-23.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 0.0216 | 0.0208 | 0.0157 | ppt |
| water_temperature | 0.2386 | 0.3049 | 0.2024 | degC |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 0.0216 | 0.0244 | -0.0027 |
| water_temperature | 0.2386 | 0.3330 | -0.0944 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
