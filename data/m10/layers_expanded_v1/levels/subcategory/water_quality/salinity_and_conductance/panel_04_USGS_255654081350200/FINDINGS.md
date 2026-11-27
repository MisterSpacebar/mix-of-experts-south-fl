# water_quality/salinity_and_conductance: within-station subcategory prototype

USGS-255654081350200 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, specific_conductance.
Consecutive observed one-day pairs: 173; train 103, validation 34, test 36.
Chronological test interval: 2026-10-17 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 2.4160 | 2.3934 | 2.0865 | ppt |
| specific_conductance | 3865.7731 | 3849.9364 | 3190.4601 | uS/cm |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 2.4160 | 2.5175 | -0.1015 |
| specific_conductance | 3865.7731 | 3841.9434 | +23.8297 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
