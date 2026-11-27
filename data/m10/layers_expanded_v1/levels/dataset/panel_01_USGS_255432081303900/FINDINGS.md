# panel_01_USGS_255432081303900: full dataset expert

USGS-255432081303900 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: discharge, salinity, water_temperature, gage_height.
Consecutive observed one-day pairs: 176; train 105, validation 35, test 36.
Chronological test interval: 2026-10-17 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| discharge | 143.3725 | 171.3413 | 176.4471 | ft^3/s |
| salinity | 1.5706 | 1.7711 | 1.7266 | ppt |
| water_temperature | 2.1114 | 2.0450 | 0.5131 | degC |
| gage_height | 0.1895 | 0.2060 | 0.1986 | ft |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
