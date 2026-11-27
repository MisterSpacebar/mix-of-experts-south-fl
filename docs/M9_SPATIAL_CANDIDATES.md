# Milestone 9.1 — spatial candidate screening, temporal alignment and recruitment

The previous geographic-readiness report correctly used each station's
single **primary discovery region**. But two source-located stations
may fall in multiple overlapping screening rectangles without being
assigned to the same primary region. That doesn't establish basin
connectivity; it does justify making them candidates for a documented
spatial screening review.

This phase **does not train a geographic, subsystem, or regional FCM**.
It audits the evidence that would be needed to design such a model.

## Run immediately using the committed real three-station snapshot

No USGS network call, no private inventory, no model retraining is needed:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v

python scripts/screen_m9_spatial_candidates.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --assignments data/m9/regional_readiness_v1_with_coords/station_assignments.csv --out data/m9/spatial_candidate_screen_v1 --max-distance-km 30 --min-pairs 79
```

Start at `data/m9/spatial_candidate_screen_v1/INDEX.md`. The previous
M9 regional browser remains untouched. For a fresh local full agency
coordinate inventory, replace `--assignments ...` with
`--stations data/inventory/combined_v3/stations.csv`, and choose a
different output directory. Do not provide both flags.

The `--stations` option additionally exports an explicit
`coordinate_inventory_exclusions.csv` record for legacy
agency-prefixed IDs (e.g., `FL005-02286320`) and coordinates missing
for a modeled canonical station. These IDs are **not silently converted
to a different canonical station key**. Conflicting coordinates for
the same canonical USGS site still fail closed. The saved three-row M9
assignment file does not contain the other 8,000+ inventory records,
so alternative namespace exclusion counts are explicitly *not audited*
in that mode.

### Expected real-data results

| Pair | Shared complete daily observations | Aligned one-day transitions | Longest uninterrupted shared days | Distance |
|---|---:|---:|---:|---:|
| East River / Pumpkin River | 89 | 70 | 7 | approx. 9.5 km |
| East River / Black Creek Canal | 88 | 70 | 7 | approx. 114 km |
| Pumpkin River / Black Creek Canal | 164 | 149 | 13 | approx. 124 km |

Only the East River / Pumpkin River pair meets the default 30-km
proximity/discovery-region screening rules. Its source coordinates
place **both stations** inside the broad Big Cypress *and* Southwest
Everglades Coast discovery rectangles, although its existing modeled
station profiles each have a different primary region.

It is **one independent site pair**, represented as a candidate
within two metadata rectangles. Do not double-count it as two
replications, infer a transport path, or assume both stations share a
hydrological catchment merely from their distance.

All four concepts have matching recorded native units between this
pair. `gage_height` has no verified common vertical reference, so
three concepts (discharge, salinity, water temperature) are
reportable as unit/datum-compatible for preliminary screening.
A **hydrology-only** two-variable cross-station model lacks a second
verified compatible concept until the stage datum is resolved.
The **water-quality** pair has two compatible concepts but only 70
aligned one-day transitions: below the reference 79 required by
the current FCM approach. It is a data-expansion candidate, **not**
a ready-to-fit regional expert.

The `n_common_one_day_transitions` count correctly accumulates
separate truly consecutive day-pairs across real gaps without
interpolation. The longest *uninterrupted* stretch is reported
separately. Neither metric silently substitutes for the other.

## New browseable outputs

```text
data/m9/spatial_candidate_screen_v1/
  INDEX.md                                  # Start here
  manifest.json                             # Input hashes, all regional FCMs untrained
  candidate_station_pairs.csv               # Each unordered station pair exactly ONCE
  candidate_pair_subsystems.csv             # Same pair, different concept-category gates
  discovery_region_summary.csv              # 14 regions, true distinct station counts
  cross_rectangle_pair_memberships.csv      # Repeated rectangle context, same pair ID
  source_station_provenance.csv              # Canonical source sites + geographic provenance
  coordinate_inventory_exclusions.csv       # Full ID audit only in --stations mode
  visuals/
    candidate_station_graph.svg             # Dashed, undirected, NOT fitted FCM arrows
    temporal_readiness_comparison.png       # Shared days vs aligned one-day transitions
    candidate_rectangle_counts.png
  regions/
    big_cypress/
      FINDINGS.md
      candidate_pairs.csv
      candidate_scope_evidence.csv
      visuals/
        candidate_station_graph.svg
        temporal_overlap.png
      subsystems/
        hydrology/FINDINGS.md
        hydrology/surface_flow/FINDINGS.md
        water_quality/FINDINGS.md
        water_quality/salinity_and_conductance/FINDINGS.md
        water_quality/thermal_conditions/FINDINGS.md
        ...
    southwest_everglades_coast/...
    central_south_biscayne/...             # 0 same-envelope pairs at present
    ...                                    # all 14 discovery rectangles
```

The region pages link to the unchanged *actually fitted* station-level
FCM network SVGs, DATA.md source lineages, and FINDINGS.md results.
These links are clearly distinct from the **undirected** geography
screening diagrams.

## Recruit new candidates near already measured stations

The new metadata-only ranking helper consumes the locally available
agency station inventory and parameter period snapshot, original daily
panel metadata, and the saved source-verified M9 coordinate assignment.

For Central/South Biscayne:

```powershell
python scripts/plan_m9_recruitment.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --assignments data/m9/regional_readiness_v1_with_coords/station_assignments.csv --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --region central_south_biscayne --end 2026-11-24 --days 180 --max-panels 6 --max-concepts 4 --max-distance-km 60 --out data/m9/biscayne_recruitment_v1
```

For Big Cypress (which uses East River and Pumpkin River as proximity
references **without** treating them as the same independently trained
region expert):

```powershell
python scripts/plan_m9_recruitment.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --assignments data/m9/regional_readiness_v1_with_coords/station_assignments.csv --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --region big_cypress --end 2026-11-24 --days 180 --max-panels 6 --max-concepts 4 --max-distance-km 60 --out data/m9/big_cypress_recruitment_v1
```

Read each output's `README.md`,
`metadata_recruitment_shortlist.csv` and `history_plan.csv`.
The ranking prioritizes the count of compatible concepts with the
nearest existing observed site (excluding missing stage reference),
then straight-line proximity and metadata concept coverage. It
**does not** assert that records exist on every day within the
metadata period-of-record. No true hydrological connectivity is
claimed.

An empty shortlist fails clearly rather than inventing trainable sites.

The generated `history_plan.csv` uses the existing source-ID schema.
Next:

```powershell
python scripts/plan_m8_batches.py --plan data/m9/biscayne_recruitment_v1/history_plan.csv --max-requests 80 --max-batches 8 --out data/m9/biscayne_recruit_batches_v1
```

Review each bounded batch, run the original short live source
identity preflight, and only then request the actual observations
and rebuild QA'd station panels. The source inventory's mixed
identifier namespaces are documented in
`inventory_identifier_exclusions.csv`; these are not automatically
merged or treated as separate verified monitoring sites.

The 2026-11-24 end date matches the previous period metadata
snapshot. It is **not** a prediction of available dates in future
metadata refreshes.

## Remaining gate before actual regional FCM training

This milestone still lacks independently verified watershed/estuary
membership and transport pathways, compatible cross-station vertical
references, sufficient temporally aligned observations, a
source-series QA-verified multistation input panel, and a spatial
held-out evaluation design. We must test against persistence,
station-local FCMs, and conservative no-transfer baselines, not
average existing station FCM weights or interpret screened geography
as causal directional arrows.

Once more compatible observed stations exist within a reviewed
hydrological region, the *subsequent* phase can train the first
explicitly spatial, region-restricted predictive FCM and add
proper directed trained edge/network diagrams beside its outputs.
