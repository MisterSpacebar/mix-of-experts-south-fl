# panel_02_USGS_255534081324000: full dataset expert

USGS-255534081324000 · southwest_everglades_coast. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, salinity, water_temperature, gage_height.
Consecutive observed one-day pairs: 177; train 106, validation 35, test 36.
Chronological test interval: 2026-10-20 through 2026-11-24.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 7.4804 | 7.6684 | 8.0465 | ft^3/s |
| salinity | 1.3273 | 1.3881 | 1.3019 | ppt |
| water_temperature | 1.3954 | 1.2834 | 0.5229 | degC |
| gage_height | 0.1889 | 0.2031 | 0.1852 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
