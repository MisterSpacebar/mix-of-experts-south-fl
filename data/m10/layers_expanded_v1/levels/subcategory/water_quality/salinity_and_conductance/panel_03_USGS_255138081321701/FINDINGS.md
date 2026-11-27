# water_quality/salinity_and_conductance: within-station subcategory prototype

USGS-255138081321701 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, specific_conductance.
Consecutive observed one-day pairs: 172; train 103, validation 34, test 35.
Chronological test interval: 2026-10-18 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 1.1376 | 1.1391 | 0.4726 | ppt |
| specific_conductance | 1600.9246 | 1600.4087 | 627.7381 | uS/cm |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 1.1376 | 1.1373 | +0.0004 |
| specific_conductance | 1600.9246 | 1601.2507 | -0.3260 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
