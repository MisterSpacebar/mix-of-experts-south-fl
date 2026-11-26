# Robustness — category — hydrology; USGS-255534081324000

Source fitted model: `data\m8\layers_replication_v1\levels\category\hydrology\panel_02_USGS_255534081324000`.
Observed daily panel: `data\m8\replication_daily_01\panel_02_USGS_255534081324000.csv`.
Verified daily panel SHA256: `8a52b809b35c89b038b07dd0afdbaefe3296f2920b67caf2b66f1635ed2f1d17`.
Physical metadata status: physical_metadata_checked.

Expanding-origin fits with non-overlapping held-out dates: 3.
Paired exploratory block-bootstrap summaries: 6.
All calculations use existing observed values and original chronological splits; no target labels enter model fitting.

[Temporal skill plot](visuals/temporal_skill.png) · [Temporal fold metrics](temporal_folds.csv) · [Temporal edge weights](temporal_edge_weights.csv) · [Paired error uncertainty](paired_uncertainty.csv)

These fold models reuse earlier observations during later fits; their training sets overlap even though held-out dates do not.
Block bootstrap CIs describe within-period error uncertainty only, not station-level reproducibility, operational skill or causal edge confidence.
