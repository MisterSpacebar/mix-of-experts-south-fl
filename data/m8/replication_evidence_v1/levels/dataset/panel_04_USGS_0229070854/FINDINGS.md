# Robustness — dataset — full_station; USGS-0229070854

Source fitted model: `data\m8\layers_replication_v1\levels\dataset\panel_04_USGS_0229070854`.
Observed daily panel: `data\m8\replication_daily_01\panel_04_USGS_0229070854.csv`.
Verified daily panel SHA256: `3ff025e2b3814407ac74f57b115caec8ea87596f1b14945c1e0dab3912ae4654`.
Physical metadata status: physical_metadata_checked.

Expanding-origin fits with non-overlapping held-out dates: 1.
Paired exploratory block-bootstrap summaries: 8.
All calculations use existing observed values and original chronological splits; no target labels enter model fitting.

[Temporal skill plot](visuals/temporal_skill.png) · [Temporal fold metrics](temporal_folds.csv) · [Temporal edge weights](temporal_edge_weights.csv) · [Paired error uncertainty](paired_uncertainty.csv)

These fold models reuse earlier observations during later fits; their training sets overlap even though held-out dates do not.
Block bootstrap CIs describe within-period error uncertainty only, not station-level reproducibility, operational skill or causal edge confidence.
