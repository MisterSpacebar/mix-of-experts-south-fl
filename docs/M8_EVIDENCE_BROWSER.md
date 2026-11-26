# Milestone 8 — evidence browser, transfer failure audit, and regional readiness

This is a **read-only** review layer over two *already completed* Milestone 8
results directories. It does not refit an FCM, pool station coefficients,
or retrain a regional expert. It preserves the original snapshots and
all their PNG/SVG scientific outputs.

## Run on the committed three-site replication

From the repository root (on the feature branch, or after merging):

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v

python scripts/browse_m8_evidence.py --models data/m8/layers_replication_v1 --evidence data/m8/replication_evidence_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --out data/m8/evidence_browser_v1 --edge-threshold 0.08
```

Start at `data/m8/evidence_browser_v1/INDEX.md` (the navigation page).
Use a **new** output directory for each run. Nothing within `--models`,
`--evidence`, or `--panels` is overwritten.

### Output map

```text
data/m8/evidence_browser_v1/
  INDEX.md
  manifest.json
  scope_coverage.png
  scope_summary.csv
  transfer_failure_audit.csv
  edge_strength_audit.csv
  bootstrap_interval_audit.csv
  levels/
    dataset/full_station/
      FINDINGS.md, transfer_diagnostics.csv, edge_evidence.csv,
      bootstrap_audit.csv, visuals/
    category/hydrology/
      FINDINGS.md
      transfer_diagnostics.csv
      edge_evidence.csv
      visuals/
        transfer_vs_persistence.png   # log10 error ratio, readable extremes
        edge_magnitude_and_sign.png   # positive/negative + magnitude
    category/water_quality/...
    category/oceanography/...         # honest no trained models
    category/ecology/...
    category/socioeconomic/...
    subcategory/hydrology/surface_flow/... # redundant category concepts
    subcategory/water_quality/salinity_and_conductance/...
    subcategory/water_quality/thermal_conditions/...
    overall/
      FINDINGS.md                     # coverage only; NOT TRAINED
```

Each per-scope FINDINGS.md links to already-fitted **per-station node-link
SVG diagrams**, model findings, and source-series provenance. They remain
in `layers_replication_v1/levels/<level>/<scope>/<station>/visuals/network.svg`.
The current evidence-browsing extension draws **diagnostic charts**, not
an imaginary regional node-link FCM.

## The distinction between missing and unvalidated data

- `station_transfer_evidence_available`: the source CSV has scored
  donor→target station pairs; a bad score is still a **valid observed
  negative result**.
- `station_models_without_transfer_evidence`: one or more fitted
  station-local models, but no distinct-station transfer for that scope.
- `redundant_concept_scope_not_independent`: same source concepts
  duplicated under category and subcategory folders. The existing
  fitted artifact is linked, not counted as independent site evidence.
- `observed_but_no_independent_specialist`: single-variable concepts
  have observations, but no multivariate subcategory FCM.
- `no_station_models_in_this_scope`: the current observed station
  set contains no eligible model for that category.
- `regional_overall_not_trained`: no integrated South Florida model
  has been fitted.

**Do not interpret missing regional fitted models as missing comparable
station observations or as blank performance plots.**

## Diagnose transfer failures

The current donor-only FCM uses the source station's train-only
normalization, fixed weights and fixed +/-3-standard-deviation
prediction clip, transferred onto the target station's previous-day
observations.

The new audit recomputes every *already scored* transfer from the
source model and target held-out dates, then verifies its MAE matches
the frozen `cross_station_transfer.csv`. It exports:

- The ratio `transfer_MAE / persistence_MAE` (above 1 indicates
  worse-than-persistence transfer; undefined for a zero-error baseline)
  and a log10 plot that accommodates extremely large losses.
- Donor training mean and standard deviation, target's preceding
  observation mean, and fraction of target inputs beyond +/-3 donor
  training standard deviations.
- Fraction of donor-based target forecasts at the FCM's normalized
  +/-3 output clipping boundary.
- Recorded raw source unit and vertical datum for each donor and
  target; an explicit `reference_datum_unverified` state for stage
  concepts when datum metadata is blank.

A reported `gage_height=ft` at three sites does **not** verify
consistent vertical reference frames. Missing stage datums require
manual source-series review before claims about physical transfer
compatibility. The audit does not change previously calculated
prediction errors or retroactively claim they were invalid as numerical
comparisons.

## Edge sign recurrence is not edge strength

A sign-consistency score of 1.0 at three stations can occur with weak
weights of -0.02, -0.04, and -0.07. Such edges should not be called
robust coupling merely because all signs match.

`edge_strength_audit.csv` rereads the three **original independent
station weight matrices**, validates that their signs and site counts
agree with the replication summary, and grades each directed edge:

- `insufficient_independent_sites`
- `weak_weight_in_at_least_one_site` when any absolute station
  weight falls below the explicit threshold
- `mixed_sign_across_sites`
- `unanimous_sign_at_display_threshold`, a *descriptive screening*
  flag, never a causal or regional fitted edge

Use `--edge-threshold 0` to inspect the sensitivity of the grades
without deleting or changing any original weight.

## Paired uncertainty warnings

A percentile block-bootstrap interval can fail to include its **own
original full-period paired MAE difference** when it samples only
contiguous runs from a held-out record with gaps. The existing
Big Cypress hydrology specialist-vs-full interval shows exactly why
this needs auditing: the point estimate favors the specialist, while
the reported block-bootstrap interval does not include that point.

The new `bootstrap_interval_audit.csv` flags such discrepancies
rather than silently treating an apparently precise bootstrap interval
as proof of superiority. This diagnostic does not fix the resampling
method itself. Recompute uncertainty with a reviewed gap-aware block
design and block-length sensitivity before using intervals in
strong inference.

## Scientific limits and next steps

- Only station-local dataset, hydrology and water-quality FCMs have
  been fitted. Regional subcategory/category/overall MoE remains untrained.
- Externally transferred source coefficients perform poorly on target
  stations. This may combine true regime shifts, site-relative stage
  references, training-period imbalance and bounds/normalization behavior.
  Diagnose rather than assume a single cause.
- Scope and event data must be reviewed before geographic connectivity,
  ecology, fisheries, and socioeconomic expert construction.
- Prior true observations are versioned in the repository's latest
  commit; treat raw USGS pulls and generated figures as substantial
  version-controlled data rather than assuming `data/m8` is always ignored.

**Decision gate for any regional expert:** better source metadata, at
least several independently evaluated compatible stations, tests of
within-site temporal skill, donor-to-target transfer, and a supervised
non-leaky regional reference baseline.
