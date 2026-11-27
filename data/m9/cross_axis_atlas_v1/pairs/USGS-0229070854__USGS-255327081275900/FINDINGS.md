# USGS-0229070854 / USGS-255327081275900 — evidence comparison

**REGIONAL AND CROSS-STATION FCM: NOT TRAINED.**
Geographic pair status: `not_a_geographic_screening_candidate`.
Overlap: 88 jointly observed days; 70 paired one-day transitions; longest uninterrupted overlap 7 days.
Shared discovery rectangles: `none`.
Straight-line source-point distance: 114.14 km.
Recorded physical-compatibility screen: discharge;salinity;water_temperature.
Unverified stage datums: gage_height.

## Two SEPARATE evidence types

- [Contrast separately fitted station predictive weights](visuals/station_fcm_contrast.png) — NOT pooled model parameters
- [Comparison of all source-trained edges](edge_weight_contrast.csv)
- [Concurrent UTC daily-change correlations](visuals/aligned_change_correlations.png) — observational co-fluctuation only
- [Numerical observed-change correlation table](observed_change_covariation.csv)

The pair did NOT pass the broad discovery/proximity screen. No cross-site change association was calculated.

## Original station FCMs (trained separately)

- **USGS-0229070854** — [full directed FCM](../../../../m8/layers_replication_v1/levels/dataset/panel_04_USGS_0229070854/visuals/network.svg) · [station findings](../../../../m8/layers_replication_v1/levels/dataset/panel_04_USGS_0229070854/FINDINGS.md) · [source provenance](../../../../m8/layers_replication_v1/levels/dataset/panel_04_USGS_0229070854/DATA.md)
- **USGS-255327081275900** — [full directed FCM](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/visuals/network.svg) · [station findings](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/FINDINGS.md) · [source provenance](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/DATA.md)

## Reproducibility

[M9.1 source screening index](../../../spatial_candidate_screen_v1/INDEX.md) (browse by region).
Both site FCMs were independently fitted; any similarity in coefficients or observed daily changes is descriptive only.
