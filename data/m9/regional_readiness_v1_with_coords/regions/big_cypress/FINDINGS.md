# Big Cypress — geographic evidence

**Geographic-region FCM: NOT TRAINED.**
**Geographic status:** `one_station_only_no_regional_model`.

This is an overlapping metadata discovery rectangle, not a verified hydrological region or water transport network.
Observed station panels: 1; independent sites: 1.
Existing independently fitted station FCMs: 1.
Possible station pairs within this region: 0.
Pairs with >= 79 shared consecutive UTC days, at least two matching native units, and no missing stage datum among selected concepts: 0.
Verified coordinates from optional inventory: 1/1.
Hydrological connectivity or flow direction: **not evaluated**.

## Explore the evidence

- [Station→measured-concept diagram](visuals/observed_station_concept_graph.svg) (NOT an FCM node-edge network)
- [Observed daily coverage](visuals/observed_daily_timeline.png)
- [Discovery region envelope and verified station points](visuals/discovery_rectangle.png)
- [Stations and source coordinates](observed_stations.csv)
- [Concepts, units and reported vertical datums](observed_concepts.csv)
- [Independent-site overlap and compatibility ledger](station_overlap_pairs.csv)
- [Category and subcategory readiness](regional_scope_readiness.csv)

## Station FCMs already fitted elsewhere

- **USGS-255327081275900** — station FCM [node-link SVG](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/visuals/network.svg) · [Findings](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/FINDINGS.md) · [Source lineage](../../../../m8/layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/DATA.md)

## Environmental subsystem evidence within region

- [hydrology](subsystems/hydrology/FINDINGS.md): one_station_only_no_regional_model
- [water_quality](subsystems/water_quality/FINDINGS.md): one_station_only_no_regional_model
- [oceanography](subsystems/oceanography/FINDINGS.md): no_observed_station_panels
- [ecology](subsystems/ecology/FINDINGS.md): no_observed_station_panels
- [socioeconomic](subsystems/socioeconomic/FINDINGS.md): no_observed_station_panels

## Geographic modeling gate

Regional model training must wait for independently verified station membership, physical connections, enough synchronized overlapping observations, measurement units/datums and spatially held-out validation.
The assigned screening region is not proof of connectivity.
No invented regional network weights or causal arrows are drawn.
