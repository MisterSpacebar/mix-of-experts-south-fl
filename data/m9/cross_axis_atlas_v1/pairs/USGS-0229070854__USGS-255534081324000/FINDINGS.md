# USGS-0229070854 / USGS-255534081324000 — evidence comparison

**REGIONAL AND CROSS-STATION FCM: NOT TRAINED.**
Geographic pair status: `not_a_geographic_screening_candidate`.
Overlap: 164 jointly observed days; 149 paired one-day transitions; longest uninterrupted overlap 13 days.
Shared discovery rectangles: `none`.
Straight-line source-point distance: 123.64 km.
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
- **USGS-255534081324000** — [full directed FCM](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/visuals/network.svg) · [station findings](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/FINDINGS.md) · [source provenance](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/DATA.md)

## Reproducibility

[M9.1 source screening index](../../../spatial_candidate_screen_v1/INDEX.md) (browse by region).
Both site FCMs were independently fitted; any similarity in coefficients or observed daily changes is descriptive only.
