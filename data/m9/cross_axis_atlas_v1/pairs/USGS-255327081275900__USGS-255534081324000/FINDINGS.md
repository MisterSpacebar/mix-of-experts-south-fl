# USGS-255327081275900 / USGS-255534081324000 — evidence comparison

**REGIONAL AND CROSS-STATION FCM: NOT TRAINED.**
Geographic pair status: `geographically_screened_only`.
Overlap: 89 jointly observed days; 70 paired one-day transitions; longest uninterrupted overlap 7 days.
Shared discovery rectangles: `big_cypress;southwest_everglades_coast`.
Straight-line source-point distance: 9.51 km.
Recorded physical-compatibility screen: discharge;salinity;water_temperature.
Unverified stage datums: gage_height.

## Two SEPARATE evidence types

- [Contrast separately fitted station predictive weights](visuals/station_fcm_contrast.png) — NOT pooled model parameters
- [Comparison of all source-trained edges](edge_weight_contrast.csv)
- [Concurrent UTC daily-change correlations](visuals/aligned_change_correlations.png) — observational co-fluctuation only
- [Numerical observed-change correlation table](observed_change_covariation.csv)

Exploratory cross-site change correlations computed for 9 compatible concept pairs, using 70 aligned one-day changes; no temporal shifts, interpolation or partial station pseudo-replication.
These correlations can arise from shared tides, rainfall or seasonal forcing; they are NOT learned spatial FCM links, forecasting skill or verified water transport.

### Largest exploratory co-fluctuations

- water_temperature at site A vs water_temperature at site B: same-day change r=+0.87 (n=70); **not a causal FCM edge**
- discharge at site A vs discharge at site B: same-day change r=+0.68 (n=70); **not a causal FCM edge**
- salinity at site A vs salinity at site B: same-day change r=+0.54 (n=70); **not a causal FCM edge**
- discharge at site A vs salinity at site B: same-day change r=-0.23 (n=70); **not a causal FCM edge**
- water_temperature at site A vs salinity at site B: same-day change r=+0.23 (n=70); **not a causal FCM edge**

## Original station FCMs (trained separately)

- **USGS-255327081275900** — [full directed FCM](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/visuals/network.svg) · [station findings](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/FINDINGS.md) · [source provenance](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/DATA.md)
- **USGS-255534081324000** — [full directed FCM](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/visuals/network.svg) · [station findings](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/FINDINGS.md) · [source provenance](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/DATA.md)

## Reproducibility

[M9.1 source screening index](../../../spatial_candidate_screen_v1/INDEX.md) (browse by region).
Both site FCMs were independently fitted; any similarity in coefficients or observed daily changes is descriptive only.
