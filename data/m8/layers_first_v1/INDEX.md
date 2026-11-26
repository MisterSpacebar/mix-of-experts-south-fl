# Milestone 8 — FCM hierarchy and evidence browser

Observed station panels supplied: 1.
New full dataset-level fits: 1.
Within-station restricted-concept specialist fits: 3.
Unique station/concept-set signatures: 2; duplicate category/subcategory signatures are flagged in the registry.
**Regional subcategory, category and overall experts: NOT TRAINED.**

All model results are chronological held-out fits, not causal identification or spatial generalization.

## Browse by level

- [Dataset / station experts](levels/dataset/INDEX.md)
- [Category: hydrology](levels/category/hydrology/INDEX.md)
- [Category: water_quality](levels/category/water_quality/INDEX.md)
- [Category: oceanography](levels/category/oceanography/INDEX.md)
- [Category: ecology](levels/category/ecology/INDEX.md)
- [Category: socioeconomic](levels/category/socioeconomic/INDEX.md)
- [Subcategory: hydrology/surface_flow](levels/subcategory/hydrology/surface_flow/INDEX.md)
- [Subcategory: water_quality/salinity_and_conductance](levels/subcategory/water_quality/salinity_and_conductance/INDEX.md)
- [Subcategory: water_quality/thermal_conditions](levels/subcategory/water_quality/thermal_conditions/INDEX.md)
- [Overall system — untrained](levels/overall/STATUS.md)

## Cross-panel evidence
- [Model registry](model_registry.csv)
- [Matched specialist/full comparisons](matched_specialist_comparisons.csv)
Each fitted scope has DATA.md, FINDINGS.md, native-unit metrics, edge weights and a visuals/ folder. Unfitted scopes have STATUS.md.
All full-vs-specialist comparisons are on identical held-out dates.
No test-set winner is automatically promoted to a regional expert.

To add sites, download new verified histories in bounded batches; then point this offline tool at multiple daily-panel directories.
