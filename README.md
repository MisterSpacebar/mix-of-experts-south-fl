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
with different physical units). Each trained station panel also receives
directed node-link SVGs for its full FCM, each populated category and
subcategory, and cross-category bridges where present. Browse them using
`visuals_v2/hierarchy/NETWORK_INDEX.md` and per-panel `NETWORKS.md`.
These are views of the same trained model, not independently trained
higher-level experts. Use `--min-edge 0` with a new output directory
to display all weak non-self links. See [FCM visualization and hierarchy
runbook](docs/FCM_VISUALS_HIERARCHY.md).

## Milestone 8: expanded station FCMs and per-layer evidence

Milestone 8 adds a separate **offline training + findings/visual browser**
for observed-only station panels. Each station is refitted and eligible
subcategories/categories get **new independently fitted station-local FCM
prototypes**, with chronological held-out comparisons to the full station
model. Models require at least two measured concepts. Every level has
data-lineage, findings, held-out performance and network/heatmap figures
where data permit. This does **not** pool stations, train integrated
regional categories or learn an overall mixture.

For the existing successful Big Cypress observed daily panel:

```powershell
python scripts/train_m8_layers.py --panels data/m7/daily_panels_verified_01 --out data/m8/layers_first_v1
```

Browse `data/m8/layers_first_v1/INDEX.md`. For expansion to more stations,
`scripts/plan_m8_batches.py` partitions a larger offline
`plan_fcm_history.py` candidate plan by bounded request counts; each batch
still requires a fresh identity preflight, source download and QA before
modeling. See [Milestone 8 layered experts guide](docs/M8_LAYERED_EXPERTS.md).

## Milestone 8 continuation: repeated station evidence and robustness

The next stage extends station-level FCM evaluation across additional
USGS monitoring sites and longer 180–365-day historical records using
the existing **bounded source-identity verified** acquisition workflow.
`plan_fcm_history.py --exclude-site` now excludes already-fitted sites
*before ranking* new candidates.

An offline evaluator adds non-overlapping chronological test folds,
paired block-bootstrap error differences, strict physical-unit/datum
matched donor→target station transfers, and descriptive edge sign
recurrence. Each model layer retains navigable `FINDINGS.md` and
visual diagnostics. No regional subcategory/category/overall FCM or
learned mixture-of-experts gate is claimed.

```powershell
# Run on an existing multi-station M8 model run and the exact daily input folders:
python scripts/evaluate_m8_replication.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --out data/m8/replication_evidence_v1
```

See [replication, station transfer and longer-history runbook](docs/M8_REPLICATION_AND_TRANSFER.md)
for the acquisition steps and how to browse findings/figures by layer.

## Evidence browser: interpret replication before fitting regional experts

The three-station Milestone 8 snapshot contains source-specific FCMs,
independent-station edge sign comparisons, and donor-to-target transfer
results. A new read-only browser separates **observed evidence** from
**untrained regional models** and links each layer's node-link diagrams,
findings, and provenance:

```powershell
python scripts/browse_m8_evidence.py --models data/m8/layers_replication_v1 --evidence data/m8/replication_evidence_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --out data/m8/evidence_browser_v1
```

Open `data/m8/evidence_browser_v1/INDEX.md` for the navigable summary.
The browser recomputes prior transfers to verify MAE parity, flags
cross-station datum gaps for stage measurements, identifies near-zero
edges that happen to have consistent signs, and audits bootstrap
intervals that do not contain their own original point estimates.
It makes **no** new fitted regional experts or pooled edge matrices.
See [M8 evidence browser runbook](docs/M8_EVIDENCE_BROWSER.md).

## Milestone 9: geographic-region FCM readiness

Geographic regions are a **second modeling axis**, alongside
environmental categories/subcategories. The new read-only regional
browser inventories *observed* site assignments, source-dated concept
coverage, verified (optional) station coordinates, within-region
independent-station overlap, native unit/datum compatibility and
training readiness by region × subsystem. Every regional FCM remains
**NOT TRAINED** until independent in-region stations, provenance,
connectivity and held-out spatial validation support real fitting.

```powershell
python scripts/build_m9_region_readiness.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --out data/m9/regional_readiness_v1

# After reading M9 region coverage, recruit more stations in one target area:
python scripts/plan_fcm_history.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --end 2026-11-24 --days 180 --max-panels 6 --max-concepts 4 --region central_south_biscayne --exclude-site USGS-0229070854 --out data/m9/biscayne_history_candidates_v1
```

Read `data/m9/regional_readiness_v1/INDEX.md`. With the existing
three-station dataset, each station belongs to a **different** selected
screening region, so no region has an independent within-region
station pair. The per-region station→concept SVG documents observed
variables only, not learned regional FCM arrows. Optional `--stations`
adds source-verified point coordinates from the locally ignored
station-inventory file (no invented GIS points).

See [M9 Geographic Readiness and Region-Specific Evidence](docs/M9_GEOGRAPHIC_READINESS.md)
for source hashes, QA criteria, visual interpretation and bounded
regional station expansion.

## Milestone 9.1: screened candidate geography, not yet regional FCMs

Source-verified coordinates reveal the East River and Pumpkin River
station panels lie in two overlapping discovery rectangles and about
9.5 km apart, even though their original primary screening regions
differ. The updated offline browser records each canonical pair ONCE,
reports 89 shared observed days vs 70 valid paired one-day transitions
(the longest uninterrupted interval is only 7 days), checks source
unit/datum compatibility, and retains the original M8 station FCM
diagrams in each geographic findings page.

```powershell
python scripts/screen_m9_spatial_candidates.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --assignments data/m9/regional_readiness_v1_with_coords/station_assignments.csv --out data/m9/spatial_candidate_screen_v1
```

Open `data/m9/spatial_candidate_screen_v1/INDEX.md`. The new
`scripts/plan_m9_recruitment.py` also creates bounded **metadata-only**
shortlists and a compatible `history_plan.csv` for screened nearby
stations when local agency inventory and period metadata are supplied.
It audits skipped alternate USGS ID namespaces without fabricating
canonical matches. **No regional predictive FCM is trained.**
See [M9.1 spatial screening and recruitment guide](docs/M9_SPATIAL_CANDIDATES.md).

## Milestone 9.2 — unified geography × environmental FCM evidence atlas

The data are less disconnected than the older category and geography
figures suggest. The trained full station FCMs contain *cross-category*
directed predictive links, while the M9.1 dashed geographic-pair line
has a different, noncausal meaning. The new cross-axis atlas brings
both types into a **single labeled SVG** with separate source-backed
coefficient tables and exploratory aligned cross-station daily-change
correlation charts. All original station models remain unchanged; no
regional FCM, environmental gate or inferred transport connection
is fabricated.

```powershell
python scripts/build_m9_cross_axis_atlas.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --assignments data/m9/regional_readiness_v1_with_coords/station_assignments.csv --screen data/m9/spatial_candidate_screen_v1 --out data/m9/cross_axis_atlas_v1
```

Open `data/m9/cross_axis_atlas_v1/INDEX.md` and click
`visuals/geography_category_evidence_atlas.svg` for the combined
overview. [M9.2 evidence atlas guide](docs/M9_CROSS_AXIS_ATLAS.md)
details relationship types, filters, full category/region reports,
source integrity and scientific interpretation.

## Milestone 10 — regional observation expansion

Start ranked, synchronized, station-bounded acquisition with the committed
M9 recruitment snapshot. No network calls or new model fits occur during
planning. See [M10 runbook](docs/M10_REGIONAL_EXPANSION.md).

```powershell
python scripts/plan_m10_expansion.py --out data/m10/expansion_plan_v1
```

## M10.1.1 — continuous acquisition temporal integrity

Continuous USGS acquisition uses explicit UTC day intervals. Earlier
history runs may omit request-endpoint days; see the [recovery runbook](docs/M10_TEMPORAL_INTEGRITY.md) for a controlled live probe, targeted source recovery, and synchronized East River expansion. Prior snapshots remain unchanged.

## M10.1.2 / M10.2 — corrected regional cohort readiness

The corrected four-station snapshot enables a geography- and sensor-aware
water-quality cohort audit with fixed chronological held-out station folds.
See [M10 regional cohort and acquisition runbook](docs/M10_REGIONAL_COHORT.md).

```powershell
python scripts/audit_m10_regional_cohort.py --verify-raw --out data/m10/cohort_corrected_v1
```

## M10.3.1 — shared regional FCM hindcast

Evaluate the first shared-parameter water-quality FCM against persistence,
pooled self-AR, unconstrained ridge and a separately labelled target-local
FCM on fixed spatial and chronological folds. See [M10 regional FCM](docs/M10_REGIONAL_FCM.md).

```powershell
python scripts/train_m10_regional_fcm.py --verify-raw --out data/m10/regional_fcm_v1
```

## M10.3.2–4 — residual FCM, forcing and expert mixtures

One staged exploratory run on the existing spatial folds. See [combined experiment runbook](docs/M10_RESIDUAL_FORCING_MIXTURE.md).

```powershell
python scripts/run_m10_residual_forcing_mixture.py --verify-raw --acquire-forcing data/m10/forcing_v1 --out data/m10/residual_forcing_mixture_v1
```

## M10.4 — hierarchical expert registry and evidence atlas

Replay frozen station/category and regional mixture experts through an archive-only research router. See [M10.4 runbook](docs/M10_HIERARCHICAL_ATLAS.md).

```powershell
python scripts/build_m10_hierarchical_atlas.py --verify-raw --out data/m10/hierarchical_atlas_v1
```

## M11 — consolidated Biscayne Bay replication

See [M11 runbook](docs/M11_BISCAYNE_PIPELINE.md). One resumable acquisition and model integration pipeline; M10 snapshots remain immutable.

```powershell
python scripts/run_m11_biscayne.py --execute --resume --out data/m11/biscayne_v1
```

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
- [Milestone 8: station-local scoped expert fitting and per-layer evidence](docs/M8_LAYERED_EXPERTS.md)
- [Milestone 8 continuation: independent station replication and transfer](docs/M8_REPLICATION_AND_TRANSFER.md)
- [M8 scientific evidence browser and transfer-failure diagnostics](docs/M8_EVIDENCE_BROWSER.md)
- [M9 geographic region FCM inventory and readiness](docs/M9_GEOGRAPHIC_READINESS.md)
- [M9.1 spatial candidate pairs and regional source recruitment](docs/M9_SPATIAL_CANDIDATES.md)
- [M9.2 geography × environmental FCM evidence atlas](docs/M9_CROSS_AXIS_ATLAS.md)

## Modeling design (planned)

1. Station- and variable-level data coverage audits before model selection.
2. Independent FCM experts trained on genuine observations, respecting missingness and source identities.
3. Subsystem-level mixtures: hydrology/water quality, physical/oceanographic, ecology, and socioeconomic services.
4. Lagged regional coupling with signed hypotheses, temporal aggregation and uncertainty-aware gating.
5. Chronological and spatial validation against conventional baselines.

The geographic rectangles are screening envelopes only, not watershed boundaries. Treat duplicated WQX/FDEP WIN records as one observation after an explicit record-level reconciliation. Never fabricate high-frequency measurements from sparse biological surveys.
