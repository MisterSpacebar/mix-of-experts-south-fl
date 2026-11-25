# Milestone 4 — Expanded South Florida discovery and observed-data pilot

This milestone extends the original Biscayne Bay / Florida Bay / Keys screening
areas inland and westward **without changing existing IDs**, and provides a
bounded extraction pipeline for real observations. It has two independent
tracks: discovery expansion and a representative observed-data pilot. The
pilot can run from the existing 21,988 metadata records, even if new
regional discovery has not yet completed.

**Scope:** Region-neutral environmental coverage. No FCM fitting is included.
Existing `data/` outputs should remain untracked and must not be overwritten.

## Track A — Expanded regional inventory

New WGS84 rectangular discovery areas in `southfl/regions.py`:

- Everglades interior
- Big Cypress
- Southwest Everglades coast and Ten Thousand Islands screening area
- Lake Okeechobee
- Everglades Agricultural Area
- Caloosahatchee connection
- St. Lucie connection

These rectangles deliberately overlap and are **not** ecological zones,
watersheds, legal boundaries, flow pathways or proof of mixing. The resulting
site count measures metadata coverage only. We will need polygon boundaries
and river/canal connectivity in a later step.

From the repo root (PowerShell; Python 3.10+):

```powershell
git fetch origin
git switch feat/expanded-region-observation-pilot
python -m unittest discover -s tests -v

# Optional smaller API probe before the whole regional extraction
python scripts/discover_regions.py --sources usgs wqp --regions lake_okeechobee everglades_interior --tiles 2 --out data/inventory/expanded_probe

# Full new regions (do not repeat old region queries)
python scripts/discover_regions.py --sources coops ndbc usgs wqp --regions everglades_interior big_cypress southwest_everglades_coast lake_okeechobee everglades_agricultural_area caloosahatchee st_lucie_connection --tiles 2 --out data/inventory/expanded_v1

# Merge 14,530 existing sites with newly discovered inland/west sites
python scripts/merge_station_discoveries.py --previous data/inventory/batch_v2 --expanded data/inventory/expanded_v1 --out data/inventory/combined_v3

# Discover parameters ONLY in expanded areas, using updated station IDs
python scripts/discover_parameters.py --stations data/inventory/combined_v3/stations.csv --sources coops ndbc usgs wqp --regions everglades_interior big_cypress southwest_everglades_coast lake_okeechobee everglades_agricultural_area caloosahatchee st_lucie_connection --tiles 2 --wqp-years 5 --out data/inventory/parameters_expanded_v1

# Merge new parameter records with your previously verified 21,988 records
python scripts/merge_parameter_periods.py --previous data/inventory/parameters_v2 --expanded data/inventory/parameters_expanded_v1 --stations data/inventory/combined_v3/stations.csv --out data/inventory/parameters_combined_v3
```

NOAA CO-OPS/NDBC are domain-wide metadata queries (run once, not per
tile); their station screening domain is expanded as well. USGS/WQP queries
are grouped by source, region and spatial tile. Each incomplete
discovery snapshot is recorded with a nonzero exit; **do not merge it as if
fully discovered**. If an agency response is too large, choose a **new output
directory** and retry with `--tiles 3` or `--tiles 4`. The scripts retain
all successful outputs and log failures. Metadata collisions are quarantined
and require manual reconciliation.

Large WQP exports are not necessarily fresh, and WQP's NWIS/USGS portion may
not contain updates after March 2024. Use USGS's current direct APIs for
newer USGS sensor observations.

## Track B — Actual observed-data pilot (can run independently now)

The pilot is a **deliberately small subset** of stations distributed among
regions based on candidate concepts, using the existing source metadata. It
does not declare models trainable and does not make a definitive ecological
sampling recommendation.

```powershell
# Create an explicit, inspectable source/site/time plan (NO internet required)
python scripts/plan_observation_pilot.py --periods data/inventory/parameters_v2/parameter_periods.csv --stations data/inventory/batch_v2/stations.csv --end 2026-10-31 --max-total 18 --per-region 3 --per-source 7 --out data/pilot/plans/first

# Inspect data/pilot/plans/first/pilot_plan.csv before any download
# Dry run prints task count without network access
python scripts/fetch_observation_pilot.py --plan data/pilot/plans/first/pilot_plan.csv --out data/pilot/runs/first

# Actual source API downloads (EXPLICIT --execute REQUIRED)
python scripts/fetch_observation_pilot.py --plan data/pilot/plans/first/pilot_plan.csv --out data/pilot/runs/first --execute
```

You can substitute the combined expanded files for both `--periods` and
`--stations` after Track A succeeds. Using the original metadata is fine
for this pilot: it tests ingestion, NOT South Florida-wide completeness.

Planner defaults, configurable in `--help`:
- USGS continuous: 14 calendar days per selected station/parameter.
  Use `--usgs-mode daily --days-usgs 30` for a small daily aggregate pilot.
- WQP discrete samples: up to 365 calendar days around a historical year
  with prior reported results. Some queries can legitimately return zero.
- CO-OPS six-minute observed water levels: maximum 14 days by default;
  NOAA has a roughly one-month API limit for six-minute records.
- At most 18 selected tasks by default, distributed across screening regions.
  Repeat with manually chosen representative strata if some data source
  or physical domain is underrepresented.

The planner selects candidate site/concept combinations by metadata recency
and a small concept priority set, preserving each underlying raw characteristic
or parameter code. It does not claim a statistically representative random
sample, nor does it guarantee all subsystems are included. A zero result is
NOT a negative ecological event or proof the monitoring station is inactive.

### Pilot output artifacts

- `pilot_plan.csv` + `plan_manifest.json`: fixed candidate source/site/
  concept/date windows and selection constraints.
- `observations.csv`: numeric values when available and **original reported
  values**, source units, QA qualifiers, result/sample identifiers, depth,
  fraction, method, timestamp basis and request URL. Non-detects are never zero.
- `sample_coverage.csv`: counts of source observations, numeric values,
  distinct sample dates, unit differences, provisional flags, and potentially
  repeated result IDs; leaves completeness blank.
- `ingestion_manifest.json`: per-task success, empty result or failure,
  query URLs, hashes of plan/output, provenance and source counts.

Time basis is explicit: USGS high-frequency and NOAA timestamped data are
converted to UTC; USGS daily values are dated calendar aggregates; WQP lab
samples retain local collection dates without fabricated UTC timestamps.
No interpolation, cross-dataset joining, unit conversion, censor imputation
or hidden forward/backward data filling occurs.

## Scientific acceptance criteria before FCMs

1. **Actual values:** sample counts, observed dates, usable numeric fraction,
   QA flags, and detection/censor limits at source-variable resolution.
2. **Temporal density:** identify instrument deployment and expected sampling
   schedule before estimating sensor completeness; annual WQP counts alone are
   insufficient.
3. **Methods:** inspect lab fraction/speciation, sample depth and units;
   reject inappropriate combinations (e.g., all nitrogen forms as total N).
4. **Space:** move from screening rectangles to polygon and connectivity
   graphs; preserve source and sublocation IDs.
5. **Duplication:** record-level reconciliation for overlapping EPA WQP,
   FDEP WIN, USGS records; spatial proximity does not prove duplication.
6. **Validation:** only after a stable observation panel should we evaluate
   independent FCM experts using chronological/spatial holdouts and baselines.

This first observed-data pilot supports USGS daily/continuous, WQP result
records, and NOAA CO-OPS observed water levels. It does **not** yet ingest the
SFWMD DBHYDRO, FDEP WIN direct export, FIU Keys, FWC, NOAA NCRMP, Coral Reef
Watch or GIS/Hazus datasets. Those require additional source-specific adapters
and appropriate ecological/annual temporal treatment.

Official service references:
- USGS OGC APIs: https://api.waterdata.usgs.gov/docs/ogcapi/
- WQP web services: https://waterqualitydata.epa.gov/webservices_documentation/
- NOAA CO-OPS data API: https://api.tidesandcurrents.noaa.gov/api/prod/

## Milestone 6: USGS live metadata end-time advances across snapshots

The verified new discovery contains 47,689 station candidates and 113,663
expanded parameter-period records. The combined station inventory contains
59,222 unique source-qualified locations. The initial cross-snapshot parameter
merge contained 354 quarantined duplicate USGS time-series keys, because
`end_utc` advanced between acquisition dates. These were investigated
against the actual uploaded conflict CSV on 2026-11-25:

- 354/354 same canonical USGS site and series ID, unchanged scientific
  attributes, and only an increasing `end_utc` difference (plus source query
  URL and region path).
- 81 distinct USGS locations affected.
- End timestamps advanced by 24–72 hours, without regressions.
- No changes to series units, initial timestamp, parameter code, statistic,
  sublocation, primary status, or other scientific metadata.

**Correct action: do not requery USGS or WQP merely to eliminate legitimate
streaming data changes.** Instead, use the strict cross-snapshot reconciliation
in `scripts/merge_parameter_periods.py`, now restricted to *USGS* time-series
metadata where all non-end scientific fields are identical, the start time is
valid, and the expanded `end_utc` is strictly later. Backward/unknown end
times and other changed fields are still quarantined.

Re-run only the local CSV merge, writing a **new snapshot**:

```powershell
git switch main
git pull
git fetch origin
git switch fix/usgs-live-metadata-snapshot-drift

python -m unittest discover -s tests -v

python scripts/merge_parameter_periods.py --previous data/inventory/parameters_v2 --expanded data/inventory/parameters_expanded_v1 --stations data/inventory/combined_v3/stations.csv --out data/inventory/parameters_combined_v4
```

Outputs in `parameters_combined_v4`:
- `parameter_periods.csv`: updated end dates for reconciled USGS time series.
- `concept_summary.csv`: recomputed from the complete reconciled metadata.
- `time_series_end_advances.csv`: one row per accepted end-date advance,
  retaining old/new timestamps, elapsed hours, source URLs, discovery
  regions and source-snapshot acquisition timestamps.
- `parameter_metadata_conflicts.csv`: **unresolved** genuine metadata
  discrepancies only.
- `parameter_manifest.json`: separate counts for exact overlaps, expected
  USGS advances and unresolved conflicts, plus metadata-only readiness flags.

If both original source files are unchanged, expected results are
**131,797 combined metadata rows**, **354 audited end advances** and
**0 unresolved conflicts**. These are predictions, not yet a locally verified
re-run. The original `parameters_combined_v3` remains unchanged for audit.

No observation records were altered. First and last USGS timestamps remain
period-of-record metadata, not proof of continuous usable data. Station and
parameter screening rectangles are not hydrological flow relationships.

### Follow-on data QA

For model selection, prioritize validating sensor-specific expected schedules,
observed data gaps, datum/units, sample depths, and independent stations.
The conflict report includes USGS groundwater elevations in **NGVD29** and
**NAVD88** among presently `unmapped` parameter codes. Those must not
be indiscriminately combined with surface gage height or with each other
without vertical-datum transformation and an explicit conceptual taxonomy.
