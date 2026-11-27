# panel_03_USGS_255138081321701: full dataset expert

USGS-255138081321701 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature, specific_conductance.
Consecutive observed one-day pairs: 172; train 103, validation 34, test 35.
Chronological test interval: 2026-10-18 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 1.1373 | 1.1391 | 0.4726 | ppt |
| water_temperature | 2.3650 | 2.3471 | 0.5438 | degC |
| specific_conductance | 1601.2507 | 1600.4087 | 627.7381 | uS/cm |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
