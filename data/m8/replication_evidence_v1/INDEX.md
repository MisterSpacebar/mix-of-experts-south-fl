# Milestone 8 — temporal and cross-station replication

This directory augments an existing immutable M8 training run.
Source model run: `data\m8\layers_replication_v1`.
Original models and source daily panels were not modified.

Station-local trained scope fits evaluated: 9.
Distinct observed station IDs: 3.
Expanding-window held-out fold/concept rows: 44.
Exploratory paired uncertainty rows: 60.
Transfer rows: 48.
**Regional subcategory, category, and overall FCMs remain NOT TRAINED.**

## Navigate evidence by level

- [category/hydrology](levels/category/hydrology/FINDINGS.md): 3 distinct sites
- [category/water_quality](levels/category/water_quality/FINDINGS.md): 3 distinct sites
- [dataset/full_station](levels/dataset/FINDINGS.md): 3 distinct sites
- [Overall region: NOT TRAINED](levels/overall/STATUS.md)

## Global evaluation tables

- [Model readiness](evaluation_registry.csv)
- [Temporal folds](temporal_folds_all.csv)
- [Paired block-bootstrap uncertainty](paired_uncertainty_all.csv)
- [Cross-station donor transfer](cross_station_transfer.csv)
- [Transfer eligibility ledger](cross_station_transfer_readiness.csv)
- [Cross-station edge sign recurrence](cross_station_edge_signs.csv)

Intervals are exploratory on one measured held-out period; station and training folds are not interchangeable independent experimental units.
