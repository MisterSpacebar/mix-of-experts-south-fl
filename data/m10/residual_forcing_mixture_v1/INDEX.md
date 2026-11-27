# M10.3.2–4 — exploratory residual, forcing and mixture experiments

4 spatial folds; 288 original matched targets. Forcing fold fits: 8.
Same previously inspected test season; no prospective confirmation or deployment.

| Concept | Model | Sites | n | MAE | Matched persistence MAE | Delta |
|---|---|---:|---:|---:|---:|---:|
| salinity | adapted_blend | 4 | 144 | 1.5286 | 1.5257 | 0.0029 |
| salinity | level_activation_ablation | 4 | 144 | 1.5058 | 1.5257 | -0.0199 |
| salinity | level_bounded | 4 | 144 | 3.5668 | 1.5257 | 2.0411 |
| salinity | persistence | 4 | 144 | 1.5257 | 1.5257 | 0.0000 |
| salinity | residual_local | 4 | 144 | 1.5444 | 1.5257 | 0.0187 |
| salinity | residual_regional | 4 | 144 | 1.5095 | 1.5257 | -0.0162 |
| salinity | residual_unbounded | 4 | 144 | 1.5095 | 1.5257 | -0.0162 |
| salinity | v1_pooled_ridge | 4 | 144 | 1.5058 | 1.5257 | -0.0199 |
| salinity | v1_pooled_self_ar | 4 | 144 | 1.4967 | 1.5257 | -0.0290 |
| salinity | v1_target_local_fcm | 4 | 144 | 1.7695 | 1.5257 | 0.2438 |
| salinity | weather_adapted_fallback | 4 | 144 | 1.5044 | 1.5257 | -0.0213 |
| salinity | weather_adapted_matched | 4 | 128 | 1.5312 | 1.5516 | -0.0204 |
| salinity | weather_forced | 4 | 128 | 1.5210 | 1.5516 | -0.0306 |
| salinity | weather_matched_unforced | 4 | 128 | 1.5503 | 1.5516 | -0.0013 |
| salinity | weather_water_level_adapted_fallback | 4 | 144 | 1.4686 | 1.5257 | -0.0571 |
| salinity | weather_water_level_adapted_matched | 4 | 64 | 1.8169 | 1.9283 | -0.1113 |
| salinity | weather_water_level_forced | 4 | 64 | 1.8575 | 1.9283 | -0.0708 |
| salinity | weather_water_level_matched_unforced | 4 | 64 | 1.9209 | 1.9283 | -0.0074 |
| salinity | weather_water_level_zero_shot_fallback | 4 | 144 | 1.4935 | 1.5257 | -0.0322 |
| salinity | weather_water_level_zero_shot_matched | 4 | 64 | 1.8664 | 1.9283 | -0.0619 |
| salinity | weather_zero_shot_fallback | 4 | 144 | 1.4909 | 1.5257 | -0.0348 |
| salinity | weather_zero_shot_matched | 4 | 128 | 1.5178 | 1.5516 | -0.0338 |
| salinity | zero_shot_blend | 4 | 144 | 1.5301 | 1.5257 | 0.0044 |
| water_temperature | adapted_blend | 4 | 144 | 0.5441 | 0.5441 | 0.0000 |
| water_temperature | level_activation_ablation | 4 | 144 | 1.0373 | 0.5441 | 0.4933 |
| water_temperature | level_bounded | 4 | 144 | 1.6573 | 0.5441 | 1.1133 |
| water_temperature | persistence | 4 | 144 | 0.5441 | 0.5441 | 0.0000 |
| water_temperature | residual_local | 4 | 144 | 0.7761 | 0.5441 | 0.2320 |
| water_temperature | residual_regional | 4 | 144 | 0.8852 | 0.5441 | 0.3411 |
| water_temperature | residual_unbounded | 4 | 144 | 0.8852 | 0.5441 | 0.3411 |
| water_temperature | v1_pooled_ridge | 4 | 144 | 1.0373 | 0.5441 | 0.4933 |
| water_temperature | v1_pooled_self_ar | 4 | 144 | 0.7571 | 0.5441 | 0.2131 |
| water_temperature | v1_target_local_fcm | 4 | 144 | 1.8349 | 0.5441 | 1.2909 |
| water_temperature | weather_adapted_fallback | 4 | 144 | 0.5441 | 0.5441 | 0.0000 |
| water_temperature | weather_adapted_matched | 4 | 128 | 0.5619 | 0.5619 | 0.0000 |
| water_temperature | weather_forced | 4 | 128 | 1.1122 | 0.5619 | 0.5503 |
| water_temperature | weather_matched_unforced | 4 | 128 | 0.9300 | 0.5619 | 0.3682 |
| water_temperature | weather_water_level_adapted_fallback | 4 | 144 | 0.5441 | 0.5441 | 0.0000 |
| water_temperature | weather_water_level_adapted_matched | 4 | 64 | 0.5532 | 0.5532 | 0.0000 |
| water_temperature | weather_water_level_forced | 4 | 64 | 1.0724 | 0.5532 | 0.5192 |
| water_temperature | weather_water_level_matched_unforced | 4 | 64 | 0.9070 | 0.5532 | 0.3538 |
| water_temperature | weather_water_level_zero_shot_fallback | 4 | 144 | 0.5441 | 0.5441 | 0.0000 |
| water_temperature | weather_water_level_zero_shot_matched | 4 | 64 | 0.5532 | 0.5532 | 0.0000 |
| water_temperature | weather_zero_shot_fallback | 4 | 144 | 0.5441 | 0.5441 | 0.0000 |
| water_temperature | weather_zero_shot_matched | 4 | 128 | 0.5619 | 0.5619 | 0.0000 |
| water_temperature | zero_shot_blend | 4 | 144 | 0.5441 | 0.5441 | 0.0000 |

Compare forced vs matched-unforced on exactly the same rows in paired_comparisons.csv.
Different model coverage is not a fair unconditional ranking. Fallback policies are all-date within fitted folds.
Seven-day intervals are conditional on the observed season/sites and omitted when synchronous blocks cannot cover the dates.
Zero-shot blends use donor validation only; adapted blends use target historical validation.
Weather and water levels are regional proxies, archive-based, not verified as-issued forecasts.

- [Metrics](metrics.csv) · [Matched comparisons](paired_comparisons.csv)
- [Predictions](predictions.csv) · [Gate weights and fits](fold_models.json)
- [Forcing coverage](forcing_coverage.csv) · [Lineage](manifest.json)
