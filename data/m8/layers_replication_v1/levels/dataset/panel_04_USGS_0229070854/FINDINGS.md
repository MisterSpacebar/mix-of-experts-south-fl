# panel_04_USGS_0229070854: full dataset expert

USGS-0229070854 · central_south_biscayne. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, salinity, water_temperature, gage_height.
Consecutive observed one-day pairs: 151; train 90, validation 30, test 31.
Chronological test interval: 2026-10-20 through 2026-11-23.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 98.6128 | 56.4995 | 31.1122 | ft^3/s |
| salinity | 0.0244 | 0.0208 | 0.0157 | ppt |
| water_temperature | 0.3330 | 0.3049 | 0.2024 | degC |
| gage_height | 0.2912 | 0.3147 | 0.1658 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
