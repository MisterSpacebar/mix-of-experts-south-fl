# Dataset acquisition plan (v0.1)

**Status:** source discovery and acquisition scaffolding, not a claim that datasets have been downloaded or audited. `catalog/datasets.json` is a list of candidates; candidate variables, sampling cadence and geographic footprint must be confirmed **per station and per release**. The source of record takes precedence over aggregators.

## Geography

- North Biscayne Bay and its canal/urban watershed
- Central and South Biscayne Bay
- Florida Bay
- Upper, Middle and Lower Florida Keys
- Connected reef tract and offshore Florida Straits

This geography is a scoping plan, not a claim of common hydrological connectivity. Preserve latitude, longitude, station ID, platform type, depth, datum, and agency source before assigning region.

## Priority 0: observations needed for initial physical and water-quality FCMs

| Dataset ID | Product to select | Acquisition / primary output | QA caveat |
|---|---|---|---|
| `sfwmd_dbhydro_hydro` | Stage, structure discharge, rainfall by selected stations | DBHYDRO station-series export/API after inspecting site IDs, data types and periods | Stage elevation datums differ; discharge signs and structures matter |
| `sfwmd_dbhydro_quality` | Discrete chemistry at relevant SFWMD sites | DBHYDRO water-quality sample exports | Samples and laboratory detection limits are not continuous data |
| `fdep_win` | WIN results for relevant monitoring locations | WIN water-quality export, station metadata | Preserve analyte, fractions, detection flags, depth |
| `epa_wqp` | Water Quality Portal monitoring locations and results | WQP query/download; use for gap-filling and cross-agency discovery | Must remove records that duplicate FDEP and other providers |
| `noaa_ndbc` | Historical standard meteorological observations near coast / reef tract | NDBC station historical data files, with station-year checks | Buoys measure different fields and deployment periods |
| `noaa_coops` | Observed (not predicted) water levels | CO-OPS Data API JSON; starter downloader supplied | Same datum required for stage comparison; selected station must actually measure product |
| `usgs_water` | Gage height/discharge/temperature/salinity, where available | USGS Water Data APIs or official exports | Unit, monitoring location, approved/provisional status |
 
## Priority 1: slower ecological and exposure experts

| Dataset ID | Product | Interpretation |
|---|---|---|
| `fiu_keys_wq` | Long-running Keys / Florida Bay water-quality network | Confirm FIU download path, sites, method and intervals |
| `noaa_crw` | CRW 5-km SST anomaly and degree heating weeks | Pixel-level thermal exposure, not in-situ reef-bottom temperature |
| `noaa_ncrmp_benthic` | Benthic surveys | Preserve campaign, transect, method and survey year |
| `noaa_ncrmp_fish` | Reef fish surveys | Preserve sampling effort/design; avoid direct comparison of incompatible surveys |
| `fwc_cremp` | CREMP coral surveys | FWC program; survey footprint must be checked before Biscayne generalization |
| `fwc_fim` | Fisheries-independent inshore surveys | Access may involve a formal data request |
| `keys_seagrass` | Florida Bay/Keys seagrass monitoring | Confirm release-specific direct download and site history |
| `fwc_landings` | Commercial landings volume/value | Landing county is not capture location |
| `miami_dade_gis` / `monroe_gis` | Parcel and land-use layers | Use snapshot timestamps; geospatial joins and assessments need validation |

## Priority 2: modeled consequences

- `fema_hazus`: flood exposure, damage, and losses generated from explicitly documented hazard scenarios. Never label as observed damages or mix as if contemporaneous water-quality sensor data.

## Shared observation schema (proposed)

`dataset_id,provider,site_id,source_record_id,timestamp_utc,local_date,latitude,longitude,depth_m,variable,reported_value,units,method,quality_flag,detection_limit,observed_or_derived,retrieved_at_utc,source_url`

Retain raw and processed layers. Timestamp and **available-at** time are different fields for leakage-safe forecasts. Retain missingness; never silently interpolate survey data into high-frequency sensor measurements. Keep sampling location and physical depth instead of averaging all South Florida sites.

## Duplication and cross-source reconciliation

- Compare organization, project, site ID, sample/activity ID, characteristic, collection timestamp, depth, and measurement value before a cross-source merge.
- FDEP WIN and EPA WQP may distribute the same monitoring observation. WQP is not automatically an independent expert.
- Regionalized models may share concepts, but must preserve provenance and avoid double-counting observation support.
- When NOAA NDBC and other platforms are colocated, check equipment/deployment continuity rather than assuming they are duplicates or independent.

## Minimum data acceptance checks

1. Source authority, usage terms, extraction method, download date, and checksum.
2. Station metadata and CRS, reliable dates and time zones, units, vertical datum, depths, and QA flags.
3. Observed coverage by year, month, station, and variable, with gap and censoring reports.
4. Sampling cadence and effective sample count; detect repeated exports and program overlap.
5. Spatial overlap with regional polygons and suitable sample sizes for each candidate expert.
6. Train/test periods and source-availability timestamps before fitting any edges.

## Immediate reproducible steps

```bash
python scripts/catalog.py
python scripts/catalog.py --json
# Example: NOAA Key West 8724580 — only retrieve this date span if coverage exists
python scripts/fetch_coops.py --station 8724580 --begin 20260101 --end 20260107
python -m unittest discover -s tests -v
```

The NOAA script performs a live API request only when explicitly run. A successful registry validation does **not** confirm the external dataset's data availability.

## Subsequent milestone

Implement metadata-only discovery first for SFWMD, WIN/WQP, NOAA, USGS and FIU. Produce `station_coverage.csv` keyed by dataset/site/variable; follow with paired data ingestion and observed-only harmonization. Only then train independent physical and water-quality FCMs. Keep temporal survey models separate until ecological datasets pass QA.
