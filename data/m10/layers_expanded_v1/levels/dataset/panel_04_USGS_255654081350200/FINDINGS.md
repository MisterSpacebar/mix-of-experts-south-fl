# panel_04_USGS_255654081350200: full dataset expert

USGS-255654081350200 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, water_temperature, specific_conductance.
Consecutive observed one-day pairs: 173; train 103, validation 34, test 36.
Chronological test interval: 2026-10-17 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 2.5175 | 2.3934 | 2.0865 | ppt |
| water_temperature | 1.9785 | 1.8668 | 0.5099 | degC |
| specific_conductance | 3841.9434 | 3849.9364 | 3190.4601 | uS/cm |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.
