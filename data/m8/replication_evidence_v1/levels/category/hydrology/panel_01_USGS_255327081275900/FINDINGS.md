# Robustness — category — hydrology; USGS-255327081275900

Source fitted model: `data\m8\layers_replication_v1\levels\category\hydrology\panel_01_USGS_255327081275900`.
Observed daily panel: `data\m7\daily_panels_verified_01\panel_01_USGS_255327081275900.csv`.
Verified daily panel SHA256: `c18f40c29ad3ec9288d1f1c4da6e8f96d66c5ce64cd8f92f8119cf3d661252af`.
Physical metadata status: physical_metadata_checked.

Expanding-origin fits with non-overlapping held-out dates: 1.
Paired exploratory block-bootstrap summaries: 6.
All calculations use existing observed values and original chronological splits; no target labels enter model fitting.

[Temporal skill plot](visuals/temporal_skill.png) · [Temporal fold metrics](temporal_folds.csv) · [Temporal edge weights](temporal_edge_weights.csv) · [Paired error uncertainty](paired_uncertainty.csv)

These fold models reuse earlier observations during later fits; their training sets overlap even though held-out dates do not.
Block bootstrap CIs describe within-period error uncertainty only, not station-level reproducibility, operational skill or causal edge confidence.
