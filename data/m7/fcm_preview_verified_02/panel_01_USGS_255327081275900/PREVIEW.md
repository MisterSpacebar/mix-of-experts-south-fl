# First dynamic FCM preview: panel_01_USGS_255327081275900

Canonical station: `USGS-255327081275900`. Screening region: `big_cypress`.
Concepts: discharge, salinity, water_temperature, gage_height. Source units: discharge=ft^3/s;salinity=ppt;water_temperature=degC;gage_height=ft.
Vertical references: discharge=;salinity=;water_temperature=;gage_height=.
Chronological pairs: 89. Train 53, validation 17, test 19.
Validation-chosen ridge alpha: 0.1.

| Concept | FCM MAE | Self-AR MAE | Persistence MAE |
|---|---:|---:|---:|
| discharge | 31.7944 | 33.0904 | 36.5636 |
| salinity | 1.7558 | 1.6186 | 0.9359 |
| water_temperature | 1.5274 | 1.5566 | 0.4857 |
| gage_height | 0.2230 | 0.2336 | 0.2598 |

Negative MAE delta versus a baseline indicates lower error.
Metrics are one-day-ahead, *conditional on the previous observed day*.
Weights are signed lag-one predictive associations, not validated causal effects.
The seven-step forward rollout is illustrative and unvalidated.
Do not use as an operational environmental or hypoxia warning model.
No cross-region weights or expert mixture has been fitted.
