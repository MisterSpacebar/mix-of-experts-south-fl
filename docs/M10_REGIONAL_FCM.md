# M10.3.1 — first shared regional FCM experiment

Run from the repository root after merging the PR:

```powershell
git checkout main
git pull origin main
python -m unittest discover -s tests -v
python scripts/train_m10_regional_fcm.py --verify-raw --out data/m10/regional_fcm_v1
Get-Content data/m10/regional_fcm_v1/INDEX.md
```

No new source download or USGS key is needed. Existing source artifacts
are immutable. The command re-audits the committed expanded cohort and
verifies original hashes (with explicit reversible line-ending handling)
and raw files. The optional raw check can be omitted for fast offline
regression, in which case prior raw-verification provenance is retained
but the run does not claim to have rehashed the raw files.

Four eligible near-bottom sites; two concepts: salinity and water
temperature. All splits use fixed target dates: training through
September 11, validation through October 16, test October 17–November 21,
2026. Each fold holds one site out of all regional scaling, training and
validation. Within-site consecutive observed pairs are pooled; no
interstation transitions are created. Test dates must match across sites.
A previous-day target observation is a legitimate forecast input; no
test target is used to tune any model. Target-local FCM is a separate
adaptation benchmark allowed to use target pre-test history.

## Models

- Persistence: previous observed value.
- Pooled self-AR: independently tuned, unconstrained scalar ridge per
  concept, donor-only.
- Pooled ridge: unconstrained multivariate ridge, identity activation.
- Regional FCM: same weighted ridge design, edge coefficients clipped to
  [-1,1] before validation, bounded linear activation [-3,3] in standardized
  output space, following existing station model conventions. Post-fit
  coefficient clipping is not a box-constrained optimization solver.
- Target-local FCM: same FCM method on only target train/validation data.

Train-only means/scales use previous states; total weight per station
is equal (normalized to sample count). All multivariate models select
their own ridge alpha by equal-concept standardized validation MAE;
self-AR tunes each target separately. No refit on validation or test.
FCM weights are source-to-target predictive associations, not causal
effects. An unconstrained ridge comparison tests the combined effect of
edge clipping and bounded activation, not either alone.

## Outputs

INDEX.md, metrics.csv (native-unit MAE, RMSE, bias and clipping counts),
predictions.csv (all five predictions for each matched target),
fold_models.json (normalizers, alpha, coefficient rows and training
sites), edge_weights.csv and paired_comparisons.csv. Aggregate errors
weight sites equally because the same 36 target dates are required.
Paired moving-block bootstrap resamples dates synchronously across
stations, with 3/7/14-day blocks, 2,000 draws by default and fixed seed.
Intervals are conditional on the fitted folds and observed test season,
not confidence intervals for independent new stations or causal effects.
No correction for multiple comparisons; interpret descriptively.
Input outside 3 SD is flagged, not clipped. FCM output clipping counts
are exported; physical validity is not guaranteed by standardized bounds.

The test season has been inspected descriptively during previous
milestones; this is retrospective spatial/temporal hindcasting, not
an untouched prospective replication. Do not promote a model based
on test performance alone. No final deployment fit, forcing data,
hydrological connectivity, exact sensor depth, mixture gate, or explicit
transport coupling is asserted.

After review, commit only the new output directory:

```powershell
git add data/m10/regional_fcm_v1
git commit -m "M10.3: evaluate shared regional water-quality FCM"
git push origin main
```
