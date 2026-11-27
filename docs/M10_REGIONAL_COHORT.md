# M10.1.2 / M10.2 — complete western acquisition and regional cohort readiness

## Corrected baseline

M10 temporal recovery preserved the three original complete daily-row
sets and added 14,823 observations. The corrected Faka-Union panel and
fresh East River panel span May 29–November 21, 2026; recovered Pumpkin
and Black Creek extend three days further. Within the common window,
the three western stations share 163 complete days, 159 valid one-day
transitions and a 95-day uninterrupted stretch. Black Creek remains a
separate geographic comparison, not part of the western cohort.

## Run the corrected cohort audit now

```powershell
python -m unittest discover -s tests -v
python scripts/audit_m10_regional_cohort.py --verify-raw --out data/m10/cohort_corrected_v1
```

The audit cross-checks corrected history, panel and identity manifests,
exact source series, metadata units, sensor-position/statistic codes,
per-day observed counts and spans and daily-row identities. Raw SHA
verification is opt-in (recommended locally); it accepts only exact
digest match or explicitly reported reversible LF/CRLF reconstruction.
This checks raw bytes and daily counts, not independently recalculated
daily means. No outputs overwrite earlier runs.

The initial shared scope is salinity + water temperature (reported
Near Bottom, instantaneous statistic 00011, matching units). Geographic
membership is checked against source-derived coordinates from M9
assignments and recruitment shortlist, not just primary region labels.
Missing or different reported depth categories are explicitly excluded.
Exact sensor depths, tidal regime and hydrological connectivity remain
unverified. Stage is not a shared state without datum review; discharge
direction conventions still need review. Full-panel complete days are
used conservatively even for the two-concept scope.

Calendar cutoffs are fixed at 60% and 80% of the requested date span
before examining outcomes. Fold plans hold out an entire target site
from donor training, normalization and validation. Previous-day target
observations may be available at forecast issue time; target-local
fitting, if later evaluated, must be labelled separately. The
temporal/metadata screen is not proof of predictive skill.

## Complete the remaining four station acquisitions

The existing batch plans are already committed. Run the following
PowerShell loop from the repository root after the initial audit.
It stops on a nonzero command exit; inspect each identity audit and
panel readiness output before continuing. Each station uses a distinct
output directory. Existing outputs must not be overwritten.

```powershell
foreach ($b in @("03","04","05","06")) {
    python scripts/reconcile_fcm_series.py --plan "data/m10/expansion_plan_v1/batch_$b/history_plan.csv" --out "data/m10/identity_$b" --probe-days 2 --min-delay 2 --execute
    if ($LASTEXITCODE -ne 0) { throw "Identity preflight failed for $b" }
    Get-Content "data/m10/identity_$b/series_identity_audit.csv"
    if ((Read-Host "Proceed with verified batch $b? (yes/no)") -ne "yes") { break }
    python scripts/fetch_fcm_history.py --plan "data/m10/identity_$b/history_plan.csv" --out "data/m10/history_$b" --max-requests 80 --delay-seconds 2 --execute
    if ($LASTEXITCODE -ne 0) { throw "Acquisition failed for $b" }
    python scripts/build_fcm_panels.py --history "data/m10/history_$b" --out "data/m10/daily_$b"
    if ($LASTEXITCODE -ne 0) { throw "Panel QA failed for $b" }
    Get-Content "data/m10/daily_$b/panel_readiness.csv"
}
```

The remaining acquisition plan contains 13 series and 169 series-window
requests, excluding pagination, retries and preflight. Maintain the
USGS key in the local environment. Do not automatically substitute
ambiguous or changed source identities; review them. A station failing
the water-quality sensor/depth screen remains useful local evidence.

## Rerun the readiness audit and refit local experts

After all successful acquisitions (omit snapshot arguments for batches
that did not produce complete verified history):

```powershell
python scripts/audit_m10_regional_cohort.py --verify-raw --snapshot data/m10/daily_03 data/m10/history_03 data/m10/identity_03 --snapshot data/m10/daily_04 data/m10/history_04 data/m10/identity_04 --snapshot data/m10/daily_05 data/m10/history_05 data/m10/identity_05 --snapshot data/m10/daily_06 data/m10/history_06 data/m10/identity_06 --out data/m10/cohort_expanded_v1
python scripts/train_m8_layers.py --panels data/m10/daily_01_recovered --panels data/m10/daily_02 --panels data/m10/daily_m8_recovered --panels data/m10/daily_03 --panels data/m10/daily_04 --panels data/m10/daily_05 --panels data/m10/daily_06 --out data/m10/layers_expanded_v1
```

Keep the corrected and expanded cohort reports, source identity audits,
history/panel manifests and observed daily panels. New raw files can
be kept locally or archived separately when repository size becomes
a concern; preserve original hashes and make raw inputs available
to rerun verification. Do not remove existing committed history.

## Next research phase

Use the resulting cohort and fixed fold plan to implement a true
shared-parameter FCM with station-local state vectors, donor-only
training/validation, equal-site or explicitly reported observation
weighting, persistence and independently tuned self-AR baselines,
unconstrained pooled ridge, and a separate target-local adaptation
benchmark on identical held-out dates. Report native-unit errors
per site/concept, paired uncertainty, and leave-one-station-out
performance rather than treating pooled station-days as independent
experiments. Do not infer directed interstation transport or a
validated mixture gate. Agency watershed/estuary and forcing-source
review follows in M10.2; no external forcing is invented here.
