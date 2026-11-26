# Milestone 8 continuation — multi-station replication and sensitivity

This is the next **evidence-gathering** stage after the successful Big
Cypress 120-day station FCM and the first 2-variable hydrology specialist.
That initial specialist achieved a lower discharge MAE than the full
four-variable model on its single 19-day test interval, but it does not
yet establish station transfer or season-general skill.

The work here adds **bounded acquisition planning** and an entirely
**offline, read-only replication evaluator**. No new observed USGS data
or cross-station model was downloaded/trained in CI or in this PR.
The user's original 120-day Big Cypress snapshot should remain unchanged.

## First: expand the observed evidence at multiple stations

Use the verified local metadata snapshots, and exclude the initial
station **before candidate ranking**. The optional `--max-per-region 2` cap prevents candidate discovery\nfrom selecting only one screened region; it may yield fewer than eight\nstations when the other regions lack comparable metadata. A discovery\nregion is not a hydrologically verified catchment. The planner does\nnot assume coincident, complete, or modern observations from metadata alone.

```powershell
python -m unittest discover -s tests -v

python scripts/plan_fcm_history.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --end 2026-10-31 --days 180 --max-panels 8 --max-concepts 4 --max-per-region 2 --exclude-site USGS-255327081275900 --out data/m8/replication_candidates_180d_v1

python scripts/plan_m8_batches.py --plan data/m8/replication_candidates_180d_v1/history_plan.csv --max-requests 80 --max-batches 8 --out data/m8/replication_batches_180d_v1
```

Read `replication_batches_180d_v1/BATCHES.md` and the actual index before
making network calls. Each batch is limited to complete, same-station
tasks, so it cannot partially fabricate an FCM station.

For each available batch (begin with the first only):

```powershell
python scripts/reconcile_fcm_series.py --plan data/m8/replication_batches_180d_v1/batch_01/history_plan.csv --out data/m8/replication_identity_01 --probe-days 2 --min-delay 2 --execute

# Inspect identity audit FIRST, including failed or ambiguous series.
python scripts/fetch_fcm_history.py --plan data/m8/replication_identity_01/history_plan.csv --out data/m8/replication_history_01 --delay-seconds 2 --execute

python scripts/build_fcm_panels.py --history data/m8/replication_history_01 --out data/m8/replication_daily_01
```

The local `USGS_API_KEY` environment variable must be set for sustained
authenticated acquisition; **do not record it in a manifest or Git**.
If USGS throttles again, stop and use the partial-failure manifest; do
not repeatedly loop on the same endpoint. Repeat with distinct numbered
outputs only for batches that actually exist and pass verification.

Then optionally extend to **365 days**, using a *new* planning snapshot
and **higher explicit bounded request caps** (four source series across
365 days need roughly 108 fourteen-day requests for one station).
For that case, use `--max-requests 140` on `plan_m8_batches.py`; the
history downloader's default `--max-requests 200` can accommodate the
verified plan, but should still be paced and executed station by station.
The source endpoints and available data may impose tighter practical
limits. A longer date range is **not** a valid new independent station.

## Train all qualifying station-local experts, keep older runs immutable

For the first batch plus the existing 120-day reference station:

```powershell
python scripts/train_m8_layers.py --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --out data/m8/layers_replication_v1
```

Add further `--panels` inputs only after those batches have created
verified `panel_readiness.csv` and `panels_manifest.json` files. The
trainer refuses duplicate panel IDs and preserves each station's
source hash, source units, geodetic datum, training windows, findings
and node-link figures. `INDEX.md` remains the entry point.

Important: for a *different 365-day snapshot of the same station*,
train it in a **separate run**, not alongside that station's earlier
120-day panel without reviewing overlapping sample identity. Alternative
window evaluations share data and must never be counted as independent
spatial replications.

## Run the new robustness and replication evaluator

```powershell
python scripts/evaluate_m8_replication.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --out data/m8/replication_evidence_v1 --max-folds 3 --block-days 7 --bootstrap 400 --min-sites 3
```

Start at `data/m8/replication_evidence_v1/INDEX.md`.

### What is evaluated

**Temporal sensitivity:** expanding-window refits of each uniquely
trained station-local scope. Validation always precedes test; successive
folds have **non-overlapping held-out days**, although their expanding
training histories overlap. Fold-by-concept skill (FCM against an
individually tuned self-AR or persistence) is reported without averaging
incompatible native-unit MAEs. Additional folds are not assumed to be
independent experiments.

**Paired error uncertainty:** measured test-day errors of the FCM,
self-AR(1), persistence and, for specialists, their same-site full FCM.
The evaluator resamples contiguous observed UTC test-day error blocks
with replacement, using a deterministic seed, to estimate an exploratory
95% percentile interval for the **paired MAE difference**. Positive
differences favor the comparison baseline, negative differences favor
FCM/specialist. With only 19 test days, intervals can be wide and
sensitive to block length; they are not proof of generalization or
calibrated risk. Missing contiguous blocks produce no invented CIs.

**Cross-station edge recurrence:** only separately fitted stations
with the same concept set and **exact source measurement units and
vertical datums** can contribute to a sign recurrence. A minimum of
three independent stations (configurable, default 3) is required to
label an edge a descriptive replication candidate. We do not combine
station matrices or interpret predictive edges as causal.

**Donor-to-target transfer:** a model fitted on site A predicts the
predeclared held-out dates at site B **without any B-side fitting,
scaler adjustment or hyperparameter tuning**. It may access B's previous
observed day's state for conditional one-step forecasts. Matching
concepts, raw units and vertical datums are mandatory; different site
IDs are mandatory. Results compare transferred MAE with target
persistence and the target's independently trained local FCM. If units,
datums, concept sets or observed test alignment don't match, results
are explicitly blocked or fail closed. This is a **cross-station
forecasting probe**, not an operational region-wide ensemble.

### Easy-to-browse results

```text
replication_evidence_v1/
  INDEX.md                              # START HERE
  manifest.json                         # immutable source model-run hash
  evaluation_registry.csv               # every fitted/redundant/blocked scope
  temporal_folds_all.csv                # chronological holdout fold metrics
  temporal_edges_all.csv
  paired_uncertainty_all.csv            # native-unit paired difference CIs
  cross_station_edge_signs.csv          # descriptive recurrence; no pooled model
  cross_station_transfer.csv            # donor to target per-concept scores
  cross_station_transfer_readiness.csv  # blocked, eligible, unevaluable pairs
  cross_station_transfer_predictions.csv
  scope_readiness.csv
  levels/
    dataset/
      FINDINGS.md
      visuals/
        edge_sign_recurrence.png
        station_transfer_skill.png
      <panel_id>/
        FINDINGS.md
        temporal_folds.csv
        temporal_edge_weights.csv
        paired_uncertainty.csv
        visuals/temporal_skill.png
    category/
      hydrology/
        FINDINGS.md
        edge_replication.csv
        station_transfer.csv
        visuals/edge_sign_recurrence.png
        visuals/station_transfer_skill.png
        <panel_id>/FINDINGS.md, visuals/temporal_skill.png, ...
    subcategory/
      hydrology/
        surface_flow/
          FINDINGS.md, edge_replication.csv, ...
          <panel_id>/FINDINGS.md, ...
    overall/
      STATUS.md                          # STILL NOT TRAINED
      FINDINGS.md                        # only a source-linked evidence index
```

Every level displays **findings, status and plots** alongside source
references. The evaluator is separate from the model-fitting pipeline
so prior M7 and M8 outputs remain untouched. This also preserves the
first Big Cypress 120-day discharge MAE comparison as an independent
*historical reference*, rather than overwriting it with future
model fits.

### Scientific next decision

A genuine integrated subcategory/category expert or gated mixture
should be attempted only after independent stations provide compatible
overlapping state variables and held-out predictive-transfer evidence.
Do not treat recurrence of signs alone as external predictive validity.
No amount of station-level USGS continuous data substitutes for the
ecological and socioeconomic sources or for explicit handling of their
different temporal scales.

**Important limit:** source period metadata and compiled tests establish
neither real data availability nor actual transfer skill. The new
robustness tables become scientific findings *only* after running against
locally verified agency observations.
