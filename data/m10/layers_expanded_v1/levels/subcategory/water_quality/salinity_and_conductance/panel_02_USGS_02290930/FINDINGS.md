# water_quality/salinity_and_conductance: within-station subcategory prototype

USGS-02290930 · big_cypress. **Independently fitted within one station**, not an integrated regional category expert.

Concepts: salinity, specific_conductance.
Consecutive observed one-day pairs: 169; train 101, validation 33, test 35.
Chronological test interval: 2026-10-18 through 2026-11-21.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |
|---|---:|---:|---:|---|
| salinity | 2.3804 | 2.3745 | 1.8102 | ppt |
| specific_conductance | 3524.1392 | 3543.0052 | 2652.5595 | uS/cm |

[Node-link FCM](visuals/network.svg) · [Held-out hindcast](visuals/heldout_hindcast.svg) · [Baseline chart](visuals/baseline_comparison.png) · [Edge heatmap](visuals/edge_weight_heatmap.png)

These are one-day-ahead predictive associations on one held-out period. Edges are not proven causal. Multi-day simulation is unvalidated. Model complexity and test-set reuse limit inference.

## Comparison to full station FCM on identical held-out days

| Concept | Specialist MAE | Full panel MAE | Difference |
|---|---:|---:|---:|
| salinity | 2.3804 | 2.4090 | -0.0286 |
| specific_conductance | 3524.1392 | 3567.7439 | -43.6047 |

Negative difference favors this station-local specialist. Comparison is descriptive, not a separately validated regional category/mixture expert.
