# Milestone 9 — geographic FCM evidence and spatial modeling readiness

This is the **first regional-modeling milestone**, not the first trained
regional FCM. Geographic regions are an *additional modeling axis*, beside
hydrology/water quality/oceanography/ecology/socioeconomics. The first
step is an audited, navigable region × subsystem evidence ledger that
preserves the existing station-level training outputs.

The 14 region labels in `southfl/regions.py` are overlapping **station
discovery rectangles**, not verified drainage basins, management
boundaries, or directions of physical transport. No station is
automatically counted in two regions because its point lies in two
overlapping rectangles.

## Run now on the real three-station dataset in Git

```powershell
git fetch origin
git switch feat/m9-regional-readiness-evidence
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v

python scripts/build_m9_region_readiness.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --out data/m9/regional_readiness_v1
```

Open `data/m9/regional_readiness_v1/INDEX.md`.

By design, this snapshot has one trained station each in
`big_cypress`, `southwest_everglades_coast`, and
`central_south_biscayne`. Consequently, it contains **zero
independent two-station pairs within the same selected region**.
No region has a trained integrated FCM or enough spatial replication
for the three-station readiness gate. All of the remaining 11 screening
regions are shown explicitly as not currently represented by these
observed panels; this does **not** mean those regions lack agency data.

The browser reads *previously produced* station FCMs and sources. The
full original repository tables, trained networks and user observations
are left untouched. New outputs require an empty directory.

## Add source-verified station coordinates (optional but recommended)

The project intentionally gitignores `data/inventory/`; the three
station-panel CSVs contain no authoritative latitude/longitude. The
runner does **not** guess station coordinates from the station ID or
invent map pins from a rectangular envelope.

If available locally, supply the deduplicated observed USGS station
metadata CSV:

```powershell
python scripts/build_m9_region_readiness.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --stations data/inventory/combined_v3/stations.csv --out data/m9/regional_readiness_with_coords_v1
```

The optional inventory must use canonical agency-qualified station
IDs, WGS84 latitude/longitude, and the source registry schema.
Conflicting station coordinates fail closed; source point coordinates
are never converted to inferred flow connections. A station may belong
to multiple **candidate discovery rectangles**, but its primary
evidence grouping remains the region selected in its original panel
plan. No automatic ecological boundary assignment is performed.

## What every region receives

```text
data/m9/regional_readiness_v1/
  INDEX.md                            # start here
  manifest.json                       # source hashes + all regional FCMs untrained
  station_assignments.csv             # original primary region, location status
  region_index.csv                    # all 14 screening regions
  region_scope_readiness.csv          # region x subsystem x subcategory
  within_region_pairs.csv             # independent stations only
  concept_observation_coverage.csv    # observed days, units and datums
  visuals/
    regional_station_coverage.png
  regions/
    central_south_biscayne/
      FINDINGS.md                     # regional model status and source links
      observed_stations.csv
      observed_concepts.csv
      station_overlap_pairs.csv
      regional_scope_readiness.csv
      visuals/
        observed_station_concept_graph.svg # measurement membership, NOT FCM edges
        observed_daily_timeline.png        # exact observed UTC days, gaps shown
        discovery_rectangle.png            # WGS84 envelope and verified points
      subsystems/
        hydrology/FINDINGS.md
        hydrology/surface_flow/FINDINGS.md
        water_quality/FINDINGS.md
        water_quality/salinity_and_conductance/FINDINGS.md
        water_quality/thermal_conditions/FINDINGS.md
        oceanography/FINDINGS.md
        ecology/FINDINGS.md
        socioeconomic/FINDINGS.md
    big_cypress/...
    southwest_everglades_coast/...
    florida_bay/...                   # present even without trained stations
    north_biscayne/...
    upper_keys/...
    ...                               # all 14 discovery regions
```

Each regional `FINDINGS.md` links back to the **actual trained
station-level SVG**, `DATA.md` lineage, and `FINDINGS.md` in
`data/m8/layers_replication_v1`.

The new station→concept SVG is a **bipartite observed-data availability
diagram**, not a new fitted node-edge FCM and not a hydrological flow
network. Its gray lines mean only that a station measured a concept.
A proper directed regional FCM diagram will only be created after
a valid spatial model actually exists.

## Readiness criteria

A candidate regional scope needs, at minimum:

1. Distinct stations **in the same currently assigned screening
   region** (default `--min-sites 3`).
2. Two or more mutually shared measured concepts from the same
   category/subcategory scope, with matching recorded units and
   any required verified vertical reference datums.
3. A qualifying pair with at least **79 consecutive complete observed
   UTC days** in common (default `--min-overlap-days 79`).
4. Verified source station coordinates, not geolocations inferred from
   agency ID numbers.
5. **Separately reviewed** actual watershed/estuary connectivity,
   transport directions and train/validation/test spatial partitioning.

Passing the first four is **not permission to fit or interpret a
regional causal FCM automatically**. The fifth remains unimplemented
in M9's first phase. The readiness state
`candidate_for_connectivity_and_spatial_holdout_review` explicitly
denotes this review gate; `regional_fcm_status` is always
`NOT_TRAINED`.

Unknown/blank reference datums for `gage_height`, `water_level`,
or groundwater elevations are flagged as **unverified**. They cannot
be treated as directly comparable geodetic elevations across stations,
even when each is measured in feet.

Other statuses distinguish missing observations, only one station,
insufficient multivariate common concepts, insufficient overlapping
time windows, insufficient independent stations and unknown
coordinates. All pair ledgers preserve the actual overlap date counts
without interpolating or pooling observed values.

## Targeted acquisition: recruit *within* a region

The history planner now accepts `--region` (repeatable) so the next
data collection round can deliberately recruit multiple independent
stations from one screened region rather than automatically spreading
one station into each region.

For example, using the locally retained inventory:

```powershell
python scripts/plan_fcm_history.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --end 2026-11-24 --days 180 --max-panels 6 --max-concepts 4 --region central_south_biscayne --exclude-site USGS-0229070854 --out data/m9/biscayne_history_candidates_v1

python scripts/plan_m8_batches.py --plan data/m9/biscayne_history_candidates_v1/history_plan.csv --out data/m9/biscayne_history_batches_v1 --max-requests 80 --max-batches 8
```

`--end 2026-11-24` matches the previously verified snapshot,
not a promise of today's metadata freshness or observed data
availability. The selected candidates still require the existing
`reconcile_fcm_series.py --execute` ID preflight, rate-limited
`fetch_fcm_history.py --execute` download and `build_fcm_panels.py`
observed-only QA **before** adding them to an M8 training run.
See `docs/M8_REPLICATION_AND_TRANSFER.md`.

Repeat for `north_biscayne`, `florida_bay`, `big_cypress` or
`southwest_everglades_coast` as metadata coverage permits. Request
success and observed completeness are different things.

## Next modeling phase after this evidence gate

A separate future training module will evaluate multistation
regional *predictive* structures with station-specific offsets,
explicit physical data harmonization, synchronization, source-aware
measurement quality, withheld stations and alternative persistence/
local-station baselines. It should use verified geographic/flow
connectivity rather than inventing relationships from a bounding
box, minimum map distance or averaging station FCM weights.

Region-specific hydrology/water-quality subcategory expert outputs
should live beside the corresponding region `FINDINGS.md`, never
be counted twice because one station belongs to overlapping
discovery windows, and must not be labelled regional until actually
trained and externally assessed.
