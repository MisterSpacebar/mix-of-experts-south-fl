# Big Cypress — candidate geography

**GEOGRAPHIC REGION FCM: NOT TRAINED.**
Discovery rectangle only: region membership is not a watershed, verified transport connection or flow direction.

Unique sites with verified coordinates in envelope: 2.
Unique screened source station pairs: 1.
Pairs meeting accumulated 79-transition criterion: 0.
Pairs are counted by their global pair ID; they may appear in more than one rectangle without representing additional independent data.

## Evidence and figures

- [Dashed candidate node graph](visuals/candidate_station_graph.svg) — not a learned FCM
- [Shared-days vs one-day transitions](visuals/temporal_overlap.png)
- [Candidate pair ledger](candidate_pairs.csv)
- [Concept/subsystem readiness](candidate_scope_evidence.csv)

## Candidate pairs and modeling gates

- **USGS-255327081275900 / USGS-255534081324000**: 89 overlapping observed days; 70 valid 1-day transitions; 7 longest uninterrupted days; 3 measured, same-unit/datum-eligible concepts; status `insufficient_aligned_one_day_transitions`

## Original trained station FCMs

- **USGS-255327081275900**: [station FCM SVG](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/visuals/network.svg) · [FINDINGS](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/FINDINGS.md) · [source lineage](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/DATA.md)
- **USGS-255534081324000**: [station FCM SVG](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/visuals/network.svg) · [FINDINGS](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/FINDINGS.md) · [source lineage](../../../../m8/layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/DATA.md)

## Subsystems (screening only)

- [hydrology](subsystems/hydrology/FINDINGS.md)
- [water_quality](subsystems/water_quality/FINDINGS.md)
- [oceanography](subsystems/oceanography/FINDINGS.md)
- [ecology](subsystems/ecology/FINDINGS.md)
- [socioeconomic](subsystems/socioeconomic/FINDINGS.md)
