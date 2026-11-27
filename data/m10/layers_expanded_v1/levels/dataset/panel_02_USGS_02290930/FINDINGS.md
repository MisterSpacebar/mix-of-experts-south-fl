# panel_02_USGS_02290930: full dataset expert

USGS-02290930 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature, gage_height, specific_conductance.
Consecutive observed one-day pairs: 169; train 101, validation 33, test 35.
Chronological test interval: 2026-10-18 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 2.4090 | 2.3745 | 1.8102 | ppt |
| water_temperature | 2.1869 | 1.8921 | 0.5516 | degC |
| gage_height | 0.2212 | 0.2029 | 0.2052 | ft |
| specific_conductance | 3567.7439 | 3543.0052 | 2652.5595 | uS/cm |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
