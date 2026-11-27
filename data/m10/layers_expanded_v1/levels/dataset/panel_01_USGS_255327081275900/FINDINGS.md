# panel_01_USGS_255327081275900: full dataset expert

USGS-255327081275900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, salinity, water_temperature, gage_height.
Consecutive observed one-day pairs: 161; train 96, validation 32, test 33.
Chronological test interval: 2026-10-20 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 24.0587 | 25.3663 | 26.5467 | ft^3/s |
| salinity | 1.1490 | 0.9895 | 0.7525 | ppt |
| water_temperature | 2.1035 | 2.0125 | 0.5438 | degC |
| gage_height | 0.1709 | 0.1870 | 0.1777 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
