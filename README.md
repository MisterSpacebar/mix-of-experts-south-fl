# South Florida Coastal Ecosystem — Mixture-of-Experts FCM

A reproducible, source-first foundation for regionalized hierarchical fuzzy cognitive maps across Biscayne Bay, Florida Bay, the Florida Keys, and connected coastal watersheds.

## Milestone status

- **Milestone 1:** Structured source registry (`catalog/datasets.json`; 18 candidate datasets), acquisition priorities, NOAA CO-OPS observed-water-level downloader.
- **Milestone 2:** Metadata-only station discovery adapters for NOAA CO-OPS, NOAA NDBC, USGS Water Data and EPA Water Quality Portal; regional assignment, co-location review, and observed-record/year coverage summaries.
- **Milestone 3 (new):** Parameter-level and period-of-record discovery from the local 14,530-station inventory. USGS time-series metadata and WQP annual characteristic counts are the principal evidence; NOAA CO-OPS and NDBC provide weaker product/archive availability indicators. The program writes normalized metadata, concept summaries, conflict reports, and a manifest. No observed completeness or model skill is claimed.
- **Not yet done:** Live bulk downloads, complete source product inventories, verified sensor-variable coverage, deduplication of actual measurements, and FCM model fitting. API access is network-dependent, and the source adapters may need adjustment to agency schema changes.

## Quick start (Python 3.10+, standard library only)

```bash
python scripts/catalog.py
python -m unittest discover -s tests -v

# First small metadata run (network needed)
python -m southfl discover --sources coops ndbc --out data/inventory/initial

# Source-by-source regional metadata discovery (can take time)
python -m southfl discover --sources usgs --bbox=-80.55,25.3,-80.05,25.95 --out data/inventory/usgs_biscayne
python -m southfl discover --sources wqp --bbox=-80.55,25.3,-80.05,25.95 --out data/inventory/wqp_biscayne

# Direct observed water-level example (live CO-OPS request)
python scripts/fetch_coops.py --station 8724580 --begin 20260101 --end 20260107
```

The downloader example may fail for dates without supported station products. Discovery failures exit nonzero and are recorded in the manifest. No source exports are checked into Git.

## Parameter discovery (Milestone 3)

```bash
# Start with a small source-specific run
python scripts/discover_parameters.py --sources usgs --regions north_biscayne --out data/inventory/parameters_usgs_north
python scripts/discover_parameters.py --sources wqp --regions florida_bay --wqp-years 5 --out data/inventory/parameters_wqp_bay

# After regional probes succeed
python scripts/discover_parameters.py --sources coops ndbc usgs wqp --wqp-years 5 --out data/inventory/parameters_v1
```

This requires the untracked `data/inventory/batch_v2/stations.csv` from
station discovery. **Do not infer sample completeness from first/last dates
or an annual WQP result count.** See the source-specific instructions below.

## Milestone 4: Expanded South Florida and observed-data pilot

Added expanded screening regions for Everglades interior, Big Cypress,
southwest coast, Lake Okeechobee, EAA, Caloosahatchee and St. Lucie.
Station and parameter discovery can run only in these added areas with
small spatial tiles, then merge with earlier snapshots without overwriting.

A separate two-step ingestion pilot generates a balanced, bounded site/
concept/date plan (offline) and then fetches **real source observations**
from modern USGS OGC (continuous/daily), EPA WQP (discrete sample results),
and NOAA CO-OPS (observed water level), using an explicit `--execute`.
Actual sample-date counts and source flags are retained; model trainability
and completeness are **not** inferred from metadata.

See [the full Milestone 4 runbook](docs/EXPANDED_REGIONS_AND_OBSERVATIONS.md).

## Documentation

- [18-dataset source catalog](catalog/datasets.json)
- [Source selection, data QA and acquisition plan](docs/DATASETS.md)
- [Station discovery/coverage instructions and limitations](docs/DISCOVERY.md)
- [Parameter and period-of-record inventory instructions](docs/PARAMETER_DISCOVERY.md)
- [Expanded region discovery and observed-data pilot](docs/EXPANDED_REGIONS_AND_OBSERVATIONS.md)

## Modeling design (planned)

1. Station- and variable-level data coverage audits before model selection.
2. Independent FCM experts trained on genuine observations, respecting missingness and source identities.
3. Subsystem-level mixtures: hydrology/water quality, physical/oceanographic, ecology, and socioeconomic services.
4. Lagged regional coupling with signed hypotheses, temporal aggregation and uncertainty-aware gating.
5. Chronological and spatial validation against conventional baselines.

The geographic rectangles are screening envelopes only, not watershed boundaries. Treat duplicated WQX/FDEP WIN records as one observation after an explicit record-level reconciliation. Never fabricate high-frequency measurements from sparse biological surveys.
