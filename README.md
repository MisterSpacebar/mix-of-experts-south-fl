# South Florida Coastal Ecosystem — Mixture-of-Experts FCM

A reproducible, source-first foundation for regionalized hierarchical fuzzy cognitive maps across Biscayne Bay, Florida Bay, the Florida Keys, and connected coastal watersheds.

## Milestone status

- **Milestone 1:** Structured source registry (`catalog/datasets.json`; 18 candidate datasets), acquisition priorities, NOAA CO-OPS observed-water-level downloader.
- **Milestone 2:** Metadata-only station discovery adapters for NOAA CO-OPS, NOAA NDBC, USGS Water Data and EPA Water Quality Portal; regional assignment, co-location review, and observed-record/year coverage summaries.
- **Milestone 3 (new):** Parameter-level and period-of-record discovery from the local 14,530-station inventory. USGS time-series metadata and WQP annual characteristic counts are the principal evidence; NOAA CO-OPS and NDBC provide weaker product/archive availability indicators. The program writes normalized metadata, concept summaries, conflict reports, and a manifest. No observed completeness or model skill is claimed.
- **Not yet done:** Full ecological/socioeconomic source ingestion, complete station-variable temporal coverage, scientifically validated cross-system causal relationships, and operational FCM deployment. API access is network-dependent, and the source adapters may need adjustment to agency schema changes.

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

## USGS hydraulic taxonomy and vertical-datum audit

The latest metadata QC update separates groundwater elevation,
stream-stage elevation, site-relative gage height, water velocity and
coastal observed water level. Known USGS elevation codes now retain
**NGVD29 or NAVD88** in a separate `vertical_datum` field; regional
concept summaries are stratified by datum. A local migration command
reclassifies verified CSV snapshots without downloading measurements.

See [hydraulic concept mapping and metadata migration](docs/HYDRAULIC_TAXONOMY.md).
No vertical conversions or FCM trainability are inferred.

## Milestone 7: Observed-data QA and first FCM preview

The project now includes an **offline QA audit** for the 16,398-record
pilot and a strict next-phase pipeline for longer **same-site USGS**
multivariate time-series: choose series from harmonized metadata, download
bounded historical windows, build observed-only daily panels, and fit a
small dynamic FCM with chronological train/validation/test and self-AR/
persistence/climatology baselines.

The preview exports signed network and held-out hindcast SVGs, edge weights,
test predictions and an illustrative (unvalidated) forward rollout.
**No trained model is bundled**: real outputs require user-side opt-in
API downloads and will be refused when temporal overlap is insufficient.

See [Milestone 7 runbook](docs/M7_FCM_PREVIEW.md) for full local commands.
The first stage is:

```bash
python scripts/audit_model_readiness.py --observations data/pilot/runs/first/observations.csv --out data/m7/pilot_readiness_v1
python scripts/plan_fcm_history.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --end 2026-10-31 --days 120 --out data/m7/history_plan_v1
```

## Milestone 7 source-series recovery

The first longer USGS pilot exposed two recoverable integration blockers:
metadata/observation series-ID mismatch and HTTP 429 anonymous rate limits.
Before any renewed long download, use a **short, source-verified preflight**
that checks a selected station/parameter against fresh targeted USGS
metadata and observed time-series IDs, writes an audit, and allows only
unambiguous replacements. Optional free `USGS_API_KEY` authentication is
sent only via the `X-Api-Key` header, with bounded 429 backoff and request
pacing.

See [the USGS key and series-identity recovery runbook](docs/M7_USGS_RECOVERY.md).
The failing initial history run remains preserved: no unverified FCM
training or hidden substitution occurred.

## Visualization package and planned FCM hierarchy

`visuals/` provides per-panel baseline and edge-weight charts, dimensionless
cross-panel performance summaries, and **taxonomy-aware projections**:
subcategory concept-grouped edge heatmaps, category/subcategory inventories,
cross-subcategory link ledgers, and an explicit trained/not-trained status
report. These are descriptive **views of existing trained station experts**,
not separately trained subcategory/category/overall FCMs. The latter remain
future research stages and are never fabricated from one station's matrix.

Install the optional plotting libraries with
`python -m pip install -r requirements.txt` (GitHub Actions does this
automatically for the visualization regression tests). Re-render an existing
preview into a *new* directory:

```powershell
python scripts/render_fcm_visuals.py --preview data/m7/fcm_preview_verified_02 --out data/m7/fcm_preview_verified_02/visuals_v2
```

The baseline comparison normalizes MAE by per-concept persistence MAE and
the cross-panel comparison uses dimensionless skill (not averaged errors
with different physical units). See [FCM visualization and hierarchy
runbook](docs/FCM_VISUALS_HIERARCHY.md).

## Documentation

- [18-dataset source catalog](catalog/datasets.json)
- [Source selection, data QA and acquisition plan](docs/DATASETS.md)
- [Station discovery/coverage instructions and limitations](docs/DISCOVERY.md)
- [Parameter and period-of-record inventory instructions](docs/PARAMETER_DISCOVERY.md)
- [Expanded region discovery and observed-data pilot](docs/EXPANDED_REGIONS_AND_OBSERVATIONS.md)
- [Hydraulic concept taxonomy and vertical-datum migration](docs/HYDRAULIC_TAXONOMY.md)
- [Observed-data QA, history and dynamic FCM preview (Milestone 7)](docs/M7_FCM_PREVIEW.md)
- [USGS time-series identity and API-key recovery](docs/M7_USGS_RECOVERY.md)
- [FCM plots, scale-free comparison, and hierarchy display](docs/FCM_VISUALS_HIERARCHY.md)

## Modeling design (planned)

1. Station- and variable-level data coverage audits before model selection.
2. Independent FCM experts trained on genuine observations, respecting missingness and source identities.
3. Subsystem-level mixtures: hydrology/water quality, physical/oceanographic, ecology, and socioeconomic services.
4. Lagged regional coupling with signed hypotheses, temporal aggregation and uncertainty-aware gating.
5. Chronological and spatial validation against conventional baselines.

The geographic rectangles are screening envelopes only, not watershed boundaries. Treat duplicated WQX/FDEP WIN records as one observation after an explicit record-level reconciliation. Never fabricate high-frequency measurements from sparse biological surveys.
