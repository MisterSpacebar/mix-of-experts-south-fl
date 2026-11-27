# M10.3.1 — shared regional water-quality FCM

4 spatial folds; 288 matched station-date-concept targets. No deployed model or spatial transport fit.

## Aggregate held-out native-unit MAE

| Concept | Persistence | Pooled self-AR | Pooled ridge | Regional FCM | Target-local FCM |
|---|---:|---:|---:|---:|---:|
| salinity (ppt) | 1.5257 | 1.4967 | 1.5058 | 3.5668 | 1.7695 |
| water_temperature (degC) | 0.5441 | 0.7571 | 1.0373 | 1.6573 | 1.8349 |

## Regional FCM minus baseline MAE (7-day paired blocks)

Negative favors regional FCM; conditional temporal intervals, not new-site inference.

| Concept | Baseline | Delta | 95% interval |
|---|---|---:|---:|
| salinity | persistence | 2.0411 | [1.0981, 2.6516] |
| salinity | pooled_self_ar | 2.0701 | [1.0703, 2.7209] |
| salinity | pooled_ridge | 2.0610 | [1.0481, 2.7132] |
| salinity | target_local_fcm | 1.7973 | [1.0801, 2.3339] |
| water_temperature | persistence | 1.1133 | [0.4939, 1.6744] |
| water_temperature | pooled_self_ar | 0.9002 | [0.3781, 1.3628] |
| water_temperature | pooled_ridge | 0.6200 | [0.1481, 1.0542] |
| water_temperature | target_local_fcm | -0.1776 | [-0.2582, -0.0919] |

- [Per-site and aggregate metrics](metrics.csv)
- [Matched predictions and clipping diagnostics](predictions.csv)
- [Block-length sensitivity](paired_comparisons.csv)
- [Fold parameters and donor-only scalers](fold_models.json)
- [FCM edges](edge_weights.csv) · [Lineage](manifest.json)

Target-local FCM uses target history and is an adaptation reference, not zero-shot. Previous-day target observations are available at issue time. These data have already been examined descriptively; results are retrospective, not prospective confirmation. Exact sensor depth, common forcing and connectivity remain unverified.
