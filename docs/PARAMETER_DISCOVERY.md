# Parameter and period-of-record discovery (Milestone 3)

This milestone takes the **14,530 station candidates** from the completed
`batch_v2` metadata discovery and inventories candidate environmental
parameters and historical availability. It DOES NOT download raw observations,
estimate completeness percentages, or train an FCM.

## Source contracts (checked against the official service documentation)

| Source | How parameter availability is discovered | What the evidence supports |
|---|---|---|
| USGS Water Data | `/ogcapi/v1/collections/time-series-metadata/items` with WGS84 bbox and pagination | Individual time-series IDs, parameter codes, units, begin/end timestamps; **gaps may be large** |
| EPA Water Quality Portal (WQP) | `/data/summary/monitoringLocation/search`, `dataProfile=periodOfRecord` | Per-site, per-characteristic, per-year activity and result counts (not continuous coverage) |
| NOAA CO-OPS | MDAPI individual station `expand=details,products` | Confirmed station metadata; establishment/removal is **not** product-specific measurement availability |
| NOAA NDBC | Historical stdmet archive index | Station-year archive file exists; no per-variable observation counts or field verification |

WQP and USGS can expose overlapping water-quality records. This step **does
not** interpret WQP result counts and USGS time-series metadata as independent
observations. Reconcile actual sample IDs, methods, sensor channels and
timestamps later.

We conservatively map source-specific parameter names and codes to shared
candidate concepts in `southfl/parameters.py`; no nutrient speciation is
inferred from generic names. Raw names, codes, and series identifiers remain
in the output.

## Run locally (Python 3.10+, no third-party packages)

On Windows PowerShell:

```powershell
git switch main
git pull
git fetch origin
git switch feat/parameter-period-coverage

python -m unittest discover -s tests -v

# Quick: 3 CO-OPS station metadata records and NDBC annual-file index
python scripts/discover_parameters.py --sources coops ndbc --out data/inventory/parameters_noaa

# USGS time-series period metadata for one region
python scripts/discover_parameters.py --sources usgs --regions north_biscayne --out data/inventory/parameters_usgs_north

# WQP nutrient/physical annual activity summaries for one region, most recent 5 years
python scripts/discover_parameters.py --sources wqp --regions florida_bay --wqp-years 5 --out data/inventory/parameters_wqp_bay

# Optional biological characteristic summary, e.g. chlorophyll measurements
python scripts/discover_parameters.py --sources wqp --regions upper_keys --wqp-types Biological --out data/inventory/parameters_wqp_bio

# Full discovery; can generate large requests, run only if regional probes succeed
python scripts/discover_parameters.py --sources coops ndbc usgs wqp --wqp-years 5 --out data/inventory/parameters_v1
```

The script expects `data/inventory/batch_v2/stations.csv` by default. The
input file is **local and ignored by Git**. You can select another with
`--stations path/to/stations.csv`.

The script rejects a nonempty output directory unless `--overwrite` is
specified, to avoid erasing successful previous discovery results. Use a new
out directory when comparing runs.

`--wqp-types Nutrient Physical Biological` is available to include
biological characteristics; the default is Nutrient and Physical to reduce
query burden. WQP chlorophyll classifications and other biological variables
should be inspected by their raw characteristic names and sample methods.

`--wqp-years all` is available for historical studies but may produce large
regional responses and exceed the deliberately conservative 18 MB response cap.
Run smaller regions, or split a broad region into smaller queries before
raising the cap. Page-capped USGS queries fail loudly: do not silently count
the partial result as complete.

## Outputs

| File | What it contains |
|---|---|
| `parameter_periods.csv` | Normalized one-row-per-series (USGS), one-row-per-site/characteristic/year (WQP), or evidence-only NOAA records |
| `concept_summary.csv` | Number of sites and series, region, candidate concept, date hints, annual WQP result reports, priority |
| `parameter_metadata_conflicts.csv` | Conflicting metadata from repeated overlapping regional queries (quarantined) |
| `parameter_manifest.json` | Input, requested sources/regions, query success/failures, row counts, and scientific limitations |

The manifest explicitly sets `observation_coverage_verified=false`.
An API failure is recorded and results in exit code 2 even if other queries
succeed; partial outputs are still saved for diagnosis. Empty successful
responses and failed queries have different statuses.

`concept_summary.csv` **never declares a model trainable from metadata**.
It uses `readiness=metadata_only_not_trainable`. If a WQP annual record has
`n_results=50`, that means 50 reported results across the year, NOT 50
independent dates, adequate spatial coverage, or continuous measurement.

The date columns for USGS are the first and most recent recorded time-series
timestamps (not necessarily uninterrupted operations). WQP has only year
precision; CO-OPS dates are retained as station metadata notes, never as
observed start/end. NDBC historical-file years are file availability hints.

## Interpretation and next ingestion milestone

Initial high-priority physical and water-quality concepts: water temperature,
salinity, dissolved oxygen, water stage and discharge; expand to conductance,
precipitation, turbidity, chlorophyll and measured nutrient forms where
supported. Qualify results by:

1. **Observed sample quality**: missing, censored, provisional, sensor failure,
   instrument installation, lab reporting limits and changes in methods.
2. **Temporal evidence**: actual sample dates and event coverage, not simply
   first/last timestamps or annual record totals.
3. **Spatial evidence**: verified site type (canal, estuary, offshore),
   depth and region polygon, not just rough rectangular bounding boxes.
4. **Data overlap**: WQP duplicates of WIN/FDEP, USGS-to-WQP chemistry
   replication, same station in multiple regional boxes.
5. **Correct causal direction**: distinguish ocean/tidal forcing from freshwater
   controls and land-use pressures before learning FCM edges.

Source-specific DBHYDRO, FDEP WIN, FIU Keys, FWC CREMP/FIM, NCRMP and GIS
ingestion remain future work. The earlier source catalog tracks them, but this
milestone does not falsely imply their measurement coverage was obtained.

Official documentation:
- USGS OGC API: https://api.waterdata.usgs.gov/docs/ogcapi/
- USGS time-series schema: https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/schema?f=html
- EPA WQP summary service: https://waterqualitydata.epa.gov/webservices_documentation/
- NOAA CO-OPS metadata: https://api.tidesandcurrents.noaa.gov/mdapi/prod/
- NOAA NDBC historical archives: https://www.ndbc.noaa.gov/historical_data.shtml

USGS OGC v1 changed its time-series date fields to UTC-valued `begin` and
`end` and removed the old `begin_utc`/`end_utc` fields. The adapter
writes normalized `begin_utc`/`end_utc` CSV columns from the current v1
fields and retains statistic ID, sublocation ID, primary/provisional flag,
and gap interval when provided. Consult the v1 schema rather than the old v0.
