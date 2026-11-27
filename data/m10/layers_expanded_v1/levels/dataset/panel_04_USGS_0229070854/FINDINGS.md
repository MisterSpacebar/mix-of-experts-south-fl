# panel_04_USGS_0229070854: full dataset expert

USGS-0229070854 · central_south_biscayne. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, salinity, water_temperature, gage_height.
Consecutive observed one-day pairs: 176; train 105, validation 35, test 36.
Chronological test interval: 2026-10-20 through 2026-11-24.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 92.7174 | 49.4392 | 28.9659 | ft^3/s |
| salinity | 0.0244 | 0.0201 | 0.0152 | ppt |
| water_temperature | 0.4026 | 0.3890 | 0.1991 | degC |
| gage_height | 0.2959 | 0.3169 | 0.1654 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
