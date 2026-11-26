# Milestone 8 — multiple station FCMs, scoped specialists and browsable evidence

## What this milestone actually trains

**The hierarchy is still under construction.** Milestone 7 trained one
four-concept mixed-station FCM (Big Cypress). Milestone 8 adds a reproducible
way to do the next two scientific tasks:

1. **More independent full/dataset FCMs:** metadata-discovered USGS stations
   are separated into bounded source-identity-verified download batches.
   Observed daily panels can then be passed to a shared offline trainer.
2. **Independently fitted station-local scope prototypes:** each successful
   full station panel gets a fresh, restricted-concept FCM fit for each
   category and subcategory with **at least two** real measured concepts.
   These restricted fits use the same chronological 60/20/20 methodology
   and self-AR/persistence baselines, but are **new models**, not copies of
   the full panel's weights. The code refuses single-node 'FCMs'.

The code does **not** pool stations or learn regional subcategory/category
experts, gating, feedback between ecosystems, or an overall South Florida
FCM. Those still require repeated spatial validation, compatible clocks
and verified sources. No new USGS observations are stored in Git.

## First: reuse the existing real USGS daily panel (no download)

On the Milestone 8 branch or after merging it:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v

python scripts/train_m8_layers.py --panels data/m7/daily_panels_verified_01 --out data/m8/layers_first_v1
```

Start reading `data/m8/layers_first_v1/INDEX.md`, not the raw CSVs.

The four-concept Big Cypress panel should be eligible to fit a new
full model, a station-local **hydrology category** model (discharge and
gage height), a **water-quality category** model (salinity and
temperature) and a **surface-flow subcategory** model (discharge
and gage height). The salinity-and-conductance and thermal-conditions
subcategories have one concept each and therefore **will be skipped** as
new specialist models. This is the *expected eligibility*, not a claim
about measured FCM skill. Actual results come from the local run.

## Outputs

```text
data/m8/layers_first_v1/
  INDEX.md                            # Start here
  manifest.json                       # Counts and scientifically honest status
  model_registry.csv                  # Every trained/skipped level and panel
  matched_specialist_comparisons.csv  # Same held-out dates as full station
  levels/
    dataset/
      INDEX.md
      <station_panel>/
        DATA.md                       # site, source series, units, datums, SHA
        FINDINGS.md                   # validation periods and error comparisons
        fcm_model.json
        heldout_metrics.csv
        heldout_predictions.csv
        edge_weights.csv
        illustrative_rollout.csv
        visuals/
          network.svg                 # actual new fitted model
          edge_weight_heatmap.png
          baseline_comparison.png
          heldout_hindcast.svg
    subcategory/
      <category>/<subcategory>/
        INDEX.md
        DATA.md                       # number of participating stations
        FINDINGS.md                   # descriptive results across station fits
        station_performance.csv
        visuals/station_skill.png     # if trainable station fits are present
        <station_panel>/
          DATA.md, FINDINGS.md
          matched_full_comparison.csv
          edge_weights.csv, heldout_metrics.csv, heldout_predictions.csv
          fcm_model.json
          visuals/network.svg, edge_weight_heatmap.png,
                  baseline_comparison.png, heldout_hindcast.svg
          # or STATUS.md for a one-concept/untrainable scope
    category/
      <category>/
        INDEX.md, DATA.md, FINDINGS.md, station_performance.csv
        visuals/station_skill.png (if at least one station-local fit)
        <station_panel>/...           # same per-station evidence/visual layout
    overall/
      STATUS.md                       # still NOT trained
      DATA.md, FINDINGS.md
      concept_coverage.csv, regional_expert_status.csv
      visuals/concept_coverage.png, visuals/training_status.png
```

The performance charts compare each concept in dimensionless
FCM-versus-baseline skill; native-unit MAE remains visible per concept.
The restricted specialist vs full dataset FCM comparison is permitted
**only when test dates and actual target values match exactly**.
Neither a favorable test score nor a consistent arrow in one station
establishes regional generalization, predictive calibration or causality.

## Expansion: get several USGS stations while respecting API limits

Plan up to 6 geographically screened, multivariate candidate stations
from your local harmonized inventory, excluding the first successful
Big Cypress station. Metadata period-of-record **is not proof of
observational coverage**.

```powershell
python scripts/plan_fcm_history.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --end 2026-10-31 --days 180 --max-panels 6 --max-concepts 4 --out data/m8/history_candidates_v1

python scripts/plan_m8_batches.py --plan data/m8/history_candidates_v1/history_plan.csv --exclude-site USGS-255327081275900 --max-requests 80 --out data/m8/history_batches_v1
```

Inspect `history_batches_v1/BATCHES.md` and `batch_index.csv`.
Each batch contains **whole stations**; it makes no network requests.
For example, to process its first bounded set:

```powershell
python scripts/reconcile_fcm_series.py --plan data/m8/history_batches_v1/batch_01/history_plan.csv --out data/m8/identity_batch_01 --probe-days 2 --min-delay 2 --execute

# Inspect identity_batch_01/series_identity_audit.csv before proceeding.
python scripts/fetch_fcm_history.py --plan data/m8/identity_batch_01/history_plan.csv --out data/m8/history_batch_01 --delay-seconds 2 --execute

python scripts/build_fcm_panels.py --history data/m8/history_batch_01 --out data/m8/daily_batch_01
```

The identity step requires a local `USGS_API_KEY` (do not commit or
log the credential). The existing downloader stops on rate limit.
Repeat the three commands with fresh `_02`, `_03` directories for
other planned batches, reviewing each source-identity audit and QA
ledger. A batch with no complete verified station plan correctly
stops rather than inventing a series.

Then fit across **separate stations without mixing their measurements**:

```powershell
python scripts/train_m8_layers.py --panels data/m7/daily_panels_verified_01 --panels data/m8/daily_batch_01 --panels data/m8/daily_batch_02 --out data/m8/layers_multisite_v1
```

Only specify directories that actually exist and contain a valid
`panel_readiness.csv` and source-hash manifest. Repeated panel IDs are
blocked instead of being silently merged.

## How to interpret per-layer findings

| Level | Outputs | What it does NOT claim |
|---|---|---|
| Dataset/station | Newly refitted full FCM, trained holdouts, diagrams, units and provenance | Transfer skill to a different station |
| Subcategory | Fresh within-station restricted FCM if >=2 concepts; one per station; observed data/skill rollup | A single region-wide subcategory expert |
| Category | Fresh within-station restricted FCM if >=2 concepts; cross-station skill *comparison* | Learned station pooling, ensemble gating or hydrological connectivity |
| Overall | Concept coverage and hierarchy status, honest untrained findings | Trained cross-category network or overall MoE |

Arrows are directed one-day predictive associations with signed weights,
not policy/causal effects. Avoid reading the network diagram as hydrological
flow direction. The 7-day dynamic rollout is illustrative, not a validated
multi-step forecast.

## Next decision gate

Once multiple stations have enough overlapping observations, examine
station-by-station edge signs and **external station holdouts** before
attempting a regional subcategory expert. Add the separate NOAA CO-OPS/NDBC,
WQP, SFWMD, ecology and socioeconomic data adapters with sampling frequency
and units/datum safeguards. Multi-time-scale gating and regional cross-
category coupling come *after* this evidence, not as a cosmetic visualization.
