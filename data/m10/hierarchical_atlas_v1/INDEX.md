# M10.4 — hierarchical research evidence atlas

8 stations; 95 registry entries; 4 regional folds; 4021 reproduced predictions.
No new fits or deployment. All routes are archive-only.

[Open offline HTML atlas](atlas.html) · [Expert registry](expert_registry.csv) · [Route metrics](route_metrics.csv)

## Scientific synthesis

M10.3.1 absolute-state activation saturated outside donor training ranges. M10.3.2 fixed-coefficient activation ablation recovered the pooled ridge result. Residual experts use persistence as the anchor; no general skill advantage was demonstrated. Observed weather/coastal-level proxies did not consistently improve direct forecasts. M10.3.4 validation-selected convex mixtures retain persistence when complexity does not help.

| Concept | Policy | Scope | n | MAE | Persistence MAE |
|---|---|---|---:|---:|---:|
| salinity | adapted | unforced | 144 | 1.5286 | 1.5257 |
| salinity | adapted | weather | 144 | 1.5044 | 1.5257 |
| salinity | adapted | weather_water_level | 144 | 1.4686 | 1.5257 |
| salinity | zero_shot | unforced | 144 | 1.5301 | 1.5257 |
| salinity | zero_shot | weather | 144 | 1.4909 | 1.5257 |
| salinity | zero_shot | weather_water_level | 144 | 1.4935 | 1.5257 |
| water_temperature | adapted | unforced | 144 | 0.5441 | 0.5441 |
| water_temperature | adapted | weather | 144 | 0.5441 | 0.5441 |
| water_temperature | adapted | weather_water_level | 144 | 0.5441 | 0.5441 |
| water_temperature | zero_shot | unforced | 144 | 0.5441 | 0.5441 |
| water_temperature | zero_shot | weather | 144 | 0.5441 | 0.5441 |
| water_temperature | zero_shot | weather_water_level | 144 | 0.5441 | 0.5441 |

The adapted weather+level salinity mixture is an exploratory candidate, not a selected deployment policy. No test-based automatic selection is performed. Next: independent region/season replication, particularly Biscayne Bay; verify exact sensor depths, hydrological connectivity and forcing provenance.

See [lineage](manifest.json), [station edges](station_edges.csv), [regional residual edges](residual_edges.csv) and [gate weights](mixture_weights.csv). The original M9 evidence atlas remains immutable.
