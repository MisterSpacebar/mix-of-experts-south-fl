# Milestone 8 — scientific evidence browser

This is a **read-only diagnostic layer** over existing measured station FCM results. No new regional model was fitted.

Independent observed station IDs: 3.
Previously scored donor→target concept comparisons: 48.
Recomputed and audited comparisons: 48.
Recorded edge comparisons: 24.
Potentially misleading bootstrap intervals flagged: 7.
**Regional category and overall FCMs are NOT TRAINED.**

[Scope coverage chart](scope_coverage.png)

## Browse by hierarchy layer

- [category / ecology](levels/category/ecology/FINDINGS.md) — 0 fits; 0 evaluated station pairs; no_station_models_in_this_scope
- [category / hydrology](levels/category/hydrology/FINDINGS.md) — 3 fits; 6 evaluated station pairs; station_transfer_evidence_available
- [category / oceanography](levels/category/oceanography/FINDINGS.md) — 0 fits; 0 evaluated station pairs; no_station_models_in_this_scope
- [category / socioeconomic](levels/category/socioeconomic/FINDINGS.md) — 0 fits; 0 evaluated station pairs; no_station_models_in_this_scope
- [category / water_quality](levels/category/water_quality/FINDINGS.md) — 3 fits; 6 evaluated station pairs; station_transfer_evidence_available
- [dataset / full_station](levels/dataset/full_station/FINDINGS.md) — 3 fits; 6 evaluated station pairs; station_transfer_evidence_available
- [overall / south_florida](levels/overall/FINDINGS.md) — 0 fits; 0 evaluated station pairs; regional_overall_not_trained
- [subcategory / hydrology/surface_flow](levels/subcategory/hydrology/surface_flow/FINDINGS.md) — 3 fits; 0 evaluated station pairs; redundant_concept_scope_not_independent
- [subcategory / water_quality/salinity_and_conductance](levels/subcategory/water_quality/salinity_and_conductance/FINDINGS.md) — 0 fits; 0 evaluated station pairs; observed_but_no_independent_specialist
- [subcategory / water_quality/thermal_conditions](levels/subcategory/water_quality/thermal_conditions/FINDINGS.md) — 0 fits; 0 evaluated station pairs; observed_but_no_independent_specialist

## Data quality and interpretation

- [Transfer model-shift and datum audit](transfer_failure_audit.csv)
- [Edge sign **and magnitude** audit](edge_strength_audit.csv)
- [Bootstrap interval consistency](bootstrap_interval_audit.csv)
- [Scope summary table](scope_summary.csv)

A transfer can be numerically evaluated with identical units while remaining **physically unverified** due to missing stage datums or station-regime differences. Likewise, 3/3 agreeing signs on tiny weights is weak evidence. These are screening diagnostics, not a newly trained South Florida mixture model.

Original results: [M8 training browser](../layers_replication_v1/INDEX.md) · [M8 replication browser](../replication_evidence_v1/INDEX.md)
