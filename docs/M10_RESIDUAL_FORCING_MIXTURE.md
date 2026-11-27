# M10.3.2–4 — residual dynamics, observed forcing, and convex expert blends

One exploratory experiment, three separated stages. No previous model or
data snapshot is overwritten. Same fixed cohort, donor folds and test dates
as M10.3.1. This season has already been inspected: no prospective skill
claim, deployment fit, transport coupling, or causal identification.

## Run

```powershell
python -m unittest discover -s tests -v
python scripts/run_m10_residual_forcing_mixture.py --verify-raw --acquire-forcing data/m10/forcing_v1 --out data/m10/residual_forcing_mixture_v1
Get-Content data/m10/residual_forcing_mixture_v1/INDEX.md
```

The acquisition uses public NOAA APIs, no key. A failed source request is
recorded, not interpolated; the residual and unforced gate experiments
continue. For a rerun, reuse the saved source snapshot with
`--forcing data/m10/forcing_v1` and a new model output directory.
For an entirely offline run omit both forcing flags.

## Stage 1: exact activation ablation and residual FCM

Replay original fitted bounded model; remove only activation clipping
with identical coefficients and scaler. Fail if original predictions do
not replay. Compare bounded and unbounded residual models, predicting
scaled one-day changes added to observed previous-day state. Inputs
are standardized from training previous states; changes scaled by
training RMS, not centered. Ridge alpha tuned on validation; post-fit
FCM coefficient clipping [-1,1] and delta activation [-3,3] apply to
the bounded variant. Zero predicted change is persistence. No physical
range guarantee or recursive stability claim.

## Stage 2: observed forcing

- [NOAA NCEI Naples Municipal Airport USW00012897](https://www.ncei.noaa.gov/cdo-web/datasets/GHCND/stations/GHCND%3AUSW00012897/detail):
  PRCP, AWND, TMIN and TMAX in metric units, reject missing/failed quality
  flags; trace zero is retained as reported. Source calendar date D-2 for
  target UTC day D, conservative relative to local calendar completion.
- [NOAA CO-OPS Fort Myers 8725520](https://tidesandcurrents.noaa.gov/stationhome.html?id=8725520):
  observed six-minute water level, MSL, metric, UTC D-1; daily mean
  and range only with >=192 valid samples and >=20-hour span; reject
  nonzero flags, accept verified/provisional. Naples gauge inventory is
  historical, so Fort Myers is a deliberately broad proxy, not a local
  tide measurement. No silent replacement with tide predictions.
- [NCEI API](https://www.ncei.noaa.gov/access/search/documentation/data-service/)
  and [CO-OPS API](https://api.tidesandcurrents.noaa.gov/api/prod/).

These are retrospective observed archives. Lagging prevents use of
future measurement dates; actual historical publication latency/revisions
are not verified. No claim of operational as-issued availability.

Fit weather and weather+water-level variants separately. For each,
compare to unforced residual fitted on identical complete-case train and
validation rows and evaluated on identical test targets. If any donor
has <35 train or <15 validation pairs, skip and report. No imputation
or test-driven source substitution. Source response JSON and manifest
are preserved with hashes; feature CSV is reconstructed before use.

## Stage 3: mixture of experts

Convex weights in increments of .25, per concept, sum to one.
Zero-shot: donor validation only (regional + persistence).
Adapted: target pre-test validation (regional + target-local + persistence).
Forced variants use matching available inputs and fall back to the
unforced gate when forcing is absent. Gate tuning reuses validation
used for component tuning; no test labels, no claim of nested independent
gate validation. These are fixed validation-selected mixtures, not a
contextual learned gate. Missing forcing on a test date is not a dropped
day in fallback policies. No comparison across unmatched subsets.

## Outputs

INDEX.md, long-form predictions.csv, metrics.csv, paired_comparisons.csv,
fold_models.json (coefficients, normalizers, validation weights),
forcing_coverage.csv and manifest.json. Metrics include exact matched
persistence error; paired comparisons include forced vs matched-unforced,
fallback vs unforced and activation ablation. Seven-day synchronized
moving-block intervals only when the matched dates support them; no
independent-new-site inference or multiplicity correction. Aggregate
subset metrics weight observed rows, not necessarily equal sites; inspect
n and n_sites. Save all negative results.

Commit the forcing and model output folders, not old source data.
