# Milestone 7 — Observation QA, longer history, and a first data-driven FCM preview

**Status:** Implemented tools and offline tests. Data outputs and trained model
results are generated only when you run them on local, git-ignored
observations. A successful pipeline does not prove causal relationships,
operational forecasting skill, or an ecosystem-wide mixture of experts.

## Baseline from previous milestones

- 59,222 geographically screened station candidates; those are not all
  independent functioning sensors.
- 131,797 harmonized parameter-period metadata records, 0 unresolved
  metadata conflicts, 1,941 reclassifications/datum enrichments.
- 16,398 locally downloaded pilot observations across 16 tasks; one task
  legitimately returned zero, and WQP sampling is sparse relative to sensors.
- The uploaded harmonized inventory contains **4,403 USGS** and **126,991 WQP**
  metadata records (with 7 CO-OPS and 396 NDBC metadata entries), *not*
  independent training examples.
- At least 64 USGS locations in that snapshot have 3+ distinct relevant
  concepts with metadata ending in October 2026 or later, but actual overlap
  and active deployment remain to be verified.

The initial learning path uses **same-site, same-time** USGS continuous
measurements. No geospatial joins are assumed simply because stations share
a discovery rectangle. NOAA/WQP pilot records are audited but not silently
converted into high-frequency training data.

## Step 1 — Review existing observed pilot (offline)

On the new branch or after merging the PR:

```powershell
git switch main
git pull
# Or check out the review branch before merging:
git fetch origin
git switch feat/m7-fcm-readiness-preview

python -m unittest discover -s tests -v

python scripts/audit_model_readiness.py --observations data/pilot/runs/first/observations.csv --out data/m7/pilot_readiness_v1
```

Produces:
- `series_readiness.csv`: source-series value/sample-day counts, censoring,
  provisional flags, repeated result IDs, duplicate timestamp/value conflicts,
  first and last actual sample date, observed timestamp gap summaries.
- `same_site_concept_pairs.csv`: days with observed numeric values for
  multiple concepts at one canonical station. Shared days are **not**
  automatically synchronous measurements.
- `readiness_manifest.json`: source hash, row counts and QA issues.
  No missingness interpolation or inferred percentage completeness.

## Step 2 — Plan multivariate historical series from metadata (offline)

```powershell
python scripts/plan_fcm_history.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --end 2026-10-31 --days 120 --max-panels 3 --max-concepts 4 --out data/m7/history_plan_v1
```

Inspect `history_plan.csv` **before any network requests**. A panel is
selected from one canonical USGS monitoring site with at least three
relevant concept codes and apparent common period-of-record. A recent
series end date does **not** establish actual continuous data. Each row
specifies exact source `time_series_id`, parameter code, raw unit, datum,
start and end date.

For a controlled one-site probe, use an explicit site from the harmonized
metadata, for example:

```powershell
python scripts/plan_fcm_history.py --site USGS-255327081275900 --days 120 --max-panels 1 --end 2026-10-31 --out data/m7/history_plan_probe
```

This is an inventory-derived candidate, not an assertion that it has
adequate real data. The default selection considers South Florida's available
regions, without privileging Biscayne Bay.

## Step 3 — Download observed longer histories (network, opt-in)

```powershell
python scripts/fetch_fcm_history.py --plan data/m7/history_plan_v1/history_plan.csv --out data/m7/history_run_v1

# After reviewing the planned number of API calls
python scripts/fetch_fcm_history.py --plan data/m7/history_plan_v1/history_plan.csv --out data/m7/history_run_v1 --execute
```

Each continuous series is requested in 14-day nonoverlapping windows.
Safety limits: at most 366 calendar days per task, 32 selected tasks and
200 bounded requests by default (configurable but deliberately capped).
Downloads validate canonical site, parameter code, concept, **exact time
series ID**, original units and vertical datum, retain source request URLs,
and reject conflicting values at the same series timestamp.

Outputs:
- `observations.csv`: raw observed values and original provenance.
- `history_plan_used.csv`: exact source-series selection.
- `history_manifest.json`: hashes, counts, rejected unrelated series,
  failed/empty tasks, and **incomplete panel identifiers**.

A missing time window, schema drift, value conflict or unsuccessful request
does not become a zero or interpolated measurement. Incomplete panels are
not advanced to model fitting.

## Step 4 — Construct observed-only daily panels (offline)

```powershell
python scripts/build_fcm_panels.py --history data/m7/history_run_v1 --min-samples 8 --min-span-hours 8 --out data/m7/daily_panels_v1
```

High-frequency measurements are aggregated to UTC-calendar-day arithmetic
means only when **each** selected concept has at least 8 valid source
measurements spanning at least 8 hours on that day. The method avoids
pretending that one isolated sensor reading measures a full day; nonetheless,
it is **not** uptime-adjusted or a verified representative daily mean.
Provisional source values remain unless `--approved-only` is used. Rejected,
invalid, nonnumeric and censored values are excluded from numeric modeling
but retained in raw inputs.

No:
- filling missing days or borrowing future observations;
- merging incompatible units or NGVD29/NAVD88;
- station averaging, arbitrary co-location joins or fake measurements from
  EPA WQP discrete sample dates;
- mixing multiple USGS sublocations/series into one concept.

Outputs: one `panel_*.csv` per site, `panel_readiness.csv` with actual
complete days/consecutive one-day pairs, and `panels_manifest.json`.
Panel candidates need >=79 complete *consecutive* transitions for the next
stage. The script reports insufficient cases explicitly.

## Step 5 — Fit the first held-out FCM preview (offline)

```powershell
python scripts/preview_fcm.py --panels data/m7/daily_panels_v1 --out data/m7/fcm_preview_v1
```

For each eligible panel, the preview fits a **bounded linear-threshold
dynamic fuzzy cognitive map** on a vector of observed environmental states:

```text
z[t+1] = clip( b + z[t] · W, -3, 3 )
```

Here `z` is standardized *only using the chronological training portion*,
`b` is an intercept and `W` is a bounded, signed ridge-regularized
predictive association matrix. `W[source, target]` indicates a
one-observation-day-lag relationship, **not a verified causal effect**.

The script:
1. Builds only consecutive measured day pairs without interpolation.
2. Uses chronological 60% training / 20% validation / 20% final test.
3. Selects ridge regularization using validation **only**.
4. Evaluates held-out one-day predictions, conditioned on the previously
   observed day's inputs.
5. Compares FCM to persistence, individual concept AR(1) and training
   climatology baselines in the source's native units.
6. Draws interpretable SVG outputs and writes raw test predictions.
7. Exports a **clearly unvalidated** seven-day free-running simulation as a
   diagnostic illustration, not a validated ecological forecast.

Outputs per `panel_*`:
- `fcm_model.json` and `edge_weights.csv` (including self-memory weights).
- `heldout_metrics.csv` and `heldout_predictions.csv`.
- `fcm_network.svg` and `heldout_hindcast.svg` (self-contained).
- `illustrative_rollout.csv` (unvalidated forward simulation).
- `PREVIEW.md` with chronological partitions and a baseline comparison.

The root `preview_manifest.json` records which models ran or why they were
**skipped**. No valid panel => zero model fits and nonzero exit, not a
fabricated FCM demonstration.

### Scientific interpretation

The fitted signed arrows may reflect shared drivers, collinearity,
autocorrelation or monitoring artifacts. Salinity and conductance are highly
related measurements; large weights between them would not demonstrate a
causal effect. A model that loses to persistence or self-AR is **not**
evidence of forecasting improvement, although its descriptive network may
still help identify hypotheses. The test sample is also a single held-out
period; uncertainty, transferability and interventions remain unvalidated.

This is the **first dataset-level regional FCM preview**, *not* a complete
mixture-of-experts system. Later milestones:
- Multiple spatially replicated held-out experts per subsystem and region.
- GAM/lag regression and conditional independence checks, plus negative
  controls to refine candidate directions and functional forms.
- Ecological/reef survey ingestion at appropriate sampling timescales.
- Cross-subsystem coupling with transparent experts and gated comparisons
  against station/region simple baselines.

## Dependencies and safeguards

This milestone uses only the Python 3.11 standard library. Agency downloads
are explicit and may need endpoint-specific updates if services change.
Existing `data/` snapshots remain untracked/immutable; each output command
refuses a nonempty destination. CI tests use synthetic/mocked fixture data
and **do not** demonstrate any live environmental FCM performance.

Do not present the illustrative edges or 7-day rollout as causal dynamics,
policy recommendations, hypoxia early-warning capability or ecological risk.
