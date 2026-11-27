# M9.2 — Integrated geographic × environmental evidence atlas

**Not a regional FCM.** This combines independently trained station edges, metadata geographic screening, and exploratory observed change co-fluctuation WITHOUT pooling or learning interstation directed edges.

Fitted independent full station FCMs: 3.
Original directed station coefficients retained: 48.
Within-station, cross-category arrows passing display threshold (|w| ≥ 0.08): 14.
Unique canonical source station pairs: 3.
Geographically screened station pairs: 1.
Exploratory cross-site daily-change variable combinations: 9 (scored: 9).
**Geographic regional experts / cross-site FCM links / overall South Florida FCM: NOT TRAINED.**

## See the connected evidence

- [**Combined geography × environmental FCM atlas**](visuals/geography_category_evidence_atlas.svg) — SOLID signed arrows are trained *inside station cards*; DASHED undirected rail is only geographic screening
- [Regional × category coverage grid](visuals/region_category_coverage.png) — number of independently fitted source stations, not region FCMs
- [Full within-station directed concept edges](trained_station_edges_by_subsystem.csv)
- [Category-to-category bridge counts by source station](within_station_category_bridges.csv)
- [Cross-station contrast of independently trained FCM weights](cross_station_fcm_edge_contrasts.csv)
- [Observed cross-site concurrent daily-change covariation](screened_cross_site_daily_change_associations.csv) — separate exploratory observational result, NOT learned arrows

## Browse each geographic region

- [North Biscayne](regions/north_biscayne/FINDINGS.md)
- [Central South Biscayne](regions/central_south_biscayne/FINDINGS.md)
- [Florida Bay](regions/florida_bay/FINDINGS.md)
- [Upper Keys](regions/upper_keys/FINDINGS.md)
- [Middle Keys](regions/middle_keys/FINDINGS.md)
- [Lower Keys](regions/lower_keys/FINDINGS.md)
- [Dry Tortugas](regions/dry_tortugas/FINDINGS.md)
- [Everglades Interior](regions/everglades_interior/FINDINGS.md)
- [Big Cypress](regions/big_cypress/FINDINGS.md)
- [Southwest Everglades Coast](regions/southwest_everglades_coast/FINDINGS.md)
- [Lake Okeechobee](regions/lake_okeechobee/FINDINGS.md)
- [Everglades Agricultural Area](regions/everglades_agricultural_area/FINDINGS.md)
- [Caloosahatchee](regions/caloosahatchee/FINDINGS.md)
- [St Lucie Connection](regions/st_lucie_connection/FINDINGS.md)

## Browse environmental categories

- [Hydrology](categories/hydrology/FINDINGS.md)
- [Water Quality](categories/water_quality/FINDINGS.md)
- [Oceanography](categories/oceanography/FINDINGS.md)
- [Ecology](categories/ecology/FINDINGS.md)
- [Socioeconomic](categories/socioeconomic/FINDINGS.md)

## Compare independently measured station pairs

- [USGS-0229070854 / USGS-255327081275900](pairs/USGS-0229070854__USGS-255327081275900/FINDINGS.md) — distant comparison
- [USGS-0229070854 / USGS-255534081324000](pairs/USGS-0229070854__USGS-255534081324000/FINDINGS.md) — distant comparison
- [USGS-255327081275900 / USGS-255534081324000](pairs/USGS-255327081275900__USGS-255534081324000/FINDINGS.md) — geographic screen candidate

## Scientific interpretation

FCM source → target direction represents day-t to day-t+1 conditional prediction at **one station**, not an intervention.
Orange/blue signs and magnitudes may change with station, training period or model definition; do not merge these matrices.
Geographic dashed lines indicate source-located screening. They are NOT proof of flow or connection.
Observed cross-site daily-change Pearson correlations use the same actual matched one-day transitions at both sites and have no learned direction. Shared rainfall/tides/seasonality can explain covariation.
Gage height is excluded from cross-site covariation without verified matching geodetic references. More data and verified connections are required for an integrated regional FCM.

## Source lineage

- [M8 trained station model index](../../m8/layers_replication_v1/INDEX.md)
- [M9.1 geographic candidate-screening index](../spatial_candidate_screen_v1/INDEX.md)
