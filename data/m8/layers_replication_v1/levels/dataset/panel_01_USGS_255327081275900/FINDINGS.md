# panel_01_USGS_255327081275900: full dataset expert

USGS-255327081275900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, salinity, water_temperature, gage_height.
Consecutive observed one-day pairs: 89; train 53, validation 17, test 19.
Chronological test interval: 2026-10-08 through 2026-10-30.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 31.7944 | 33.0904 | 36.5636 | ft^3/s |
| salinity | 1.7558 | 1.6186 | 0.9359 | ppt |
| water_temperature | 1.5274 | 1.5566 | 0.4857 | degC |
| gage_height | 0.2230 | 0.2336 | 0.2598 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
