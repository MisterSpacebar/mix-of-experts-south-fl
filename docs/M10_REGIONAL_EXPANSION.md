# Milestone 10 — regional observation expansion

## M10.1: bounded acquisition, not regional fitting

Freeze the M8 station models and M9 evidence atlas. The committed M9
Big Cypress shortlist contains five sites within 14 km of existing
references and a sixth 59 km away. Start with Faka-Union River near
the mouth (three compatible concepts in metadata), extend the shorter
East River record, and proceed in shortlist order. Existing Pumpkin River
and Black Creek panels cover the chosen request window; their observed
gaps remain. The earlier M8 identity manifest verified only Pumpkin River
and Black Creek: Faka-Union was planned but not attempted in that run.

Choose May 29–November 21, 2026 (177 calendar days) for this first
synchronized request: the earlier East River metadata ends November
22–23 depending on series, and the M9 recruitment snapshot begins May 29.
This is a bounded metadata window, not a guarantee of observations.
Do not count the extended East River record as an additional station.

```powershell
python -m unittest discover -s tests -v
python scripts/plan_m10_expansion.py --out data/m10/expansion_plan_v1
```

The output has a ranked batch index, excluded sites, source and batch
SHA-256 hashes, and one station per candidate history plan. Default:
five new sites plus one reference extension; 21 candidate series and
273 fourteen-day series-window requests (not a count of HTTP calls
including pagination, retries or preflight).

### Start with batch 01 ONLY

```powershell
python scripts/reconcile_fcm_series.py --plan data/m10/expansion_plan_v1/batch_01/history_plan.csv --out data/m10/identity_01 --probe-days 2 --min-delay 2 --execute
```

Check identity_manifest.json and series_identity_audit.csv, including
sensor sublocation/depth, source statistic, units, and datum. Confirm all
planned series are unambiguously verified. Then:

```powershell
python scripts/fetch_fcm_history.py --plan data/m10/identity_01/history_plan.csv --out data/m10/history_01 --max-requests 80 --delay-seconds 2 --execute
python scripts/build_fcm_panels.py --history data/m10/history_01 --out data/m10/daily_01
```

Set the existing USGS_API_KEY locally for sustained acquisition; do not
commit it. Stop on throttling or ambiguous identities and preserve the
failure audit. Inspect actual daily coverage, source flags and gaps before
proceeding. Use distinct output folders for later batches. The East River
extension replaces the old panel in a new evaluation run, never in M8/M9.

Stage without verified vertical datum is kept for station-local analysis
but is not a compatible cross-station absolute state. Salinity and
conductance are not independent physical variables by assumption; review
collinearity. A site with missing concepts should not silently disappear:
retain its acquisition audit and consider a separately specified reduced
concept panel.

### Central/South Biscayne track

Use the existing local agency inventory to generate a nearby shortlist:

```powershell
python scripts/plan_m9_recruitment.py --periods data/inventory/parameters_harmonized_v1/parameter_periods.csv --stations data/inventory/combined_v3/stations.csv --assignments data/m9/regional_readiness_v1_with_coords/station_assignments.csv --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --region central_south_biscayne --end 2026-11-21 --days 177 --max-panels 6 --max-concepts 4 --out data/m10/biscayne_recruitment_v1
```

The complete metadata inventory is not committed. Do not invent a
Biscayne candidate list. Review and batch its plan using plan_m8_batches.py,
then follow the same identity/download/QA procedure.

## M10.2: observed readiness and exogenous forcing (next)

Audit daily completeness separately by concept, station, and shared
one-day transition; do not interpolate gaps. Review basin/estuary
membership and actual hydrological connectivity from agency evidence,
not discovery rectangles or proximity. Verify instrument depth and
vertical references. Recruit NOAA observed tides, wind and observed
rainfall as separate forcing series; retain station identity, timing,
measurement units and observed coverage. No forecast-time leakage:
only predictors available at the issue date can enter a hindcast.

## M10.3: conditional regional prototype (not implemented)

Require at least three independent reviewed stations for a regional
scope; exact comparable concepts, units and relevant datum/depth
metadata, and at least 79 valid consecutive one-day transitions for
the proposed common scope (a minimum screen, not sufficient statistical
power). Report uninterrupted windows separately. Require sufficient
chronological train/validation/test coverage in each spatial fold.

Compare persistence, self-AR, station-local FCM, a regularized pooled
non-FCM baseline, and a pooled/shared-parameter FCM. Hold out an entire
station from regional fitting, scaling and tuning; train only on earlier
dates, and use the same target dates for all baselines. A target-local
model may use prior target observations but is a separately labelled
adaptation benchmark, not a zero-shot baseline. Fit scalers on training
data, report clipping and native-unit paired errors by site/concept.
Distinguish pooled regional expert from learned directed transport
coupling. Only fit the latter after verified connectivity and adequate
aligned multistation evidence. No regional FCM skill is claimed here.
