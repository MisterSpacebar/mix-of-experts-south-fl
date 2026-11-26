# panel_02_USGS_255534081324000: full dataset expert

USGS-255534081324000 · southwest_everglades_coast. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, salinity, water_temperature, gage_height.
Consecutive observed one-day pairs: 152; train 91, validation 30, test 31.
Chronological test interval: 2026-10-20 through 2026-11-23.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 8.4662 | 7.2573 | 7.7307 | ft^3/s |
| salinity | 1.3776 | 1.4038 | 1.2481 | ppt |
| water_temperature | 1.4493 | 1.2892 | 0.4944 | degC |
| gage_height | 0.1914 | 0.1921 | 0.1782 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
