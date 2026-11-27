# M10.1.1 — continuous USGS temporal integrity

## Evidence and scope

All 13 omitted Faka-Union UTC days are the final days of 14-day
request windows (including the final shorter window); the same pattern
appears in M7 and M8. The old date-only endpoint likely returned only
midnight. The agency's [OGC continuous schema](https://api.waterdata.usgs.gov/ogcapi/v0/collections/continuous/schema?f=html)
supports explicit RFC 3339 timestamp intervals. Live behavior still
requires verification on the user's USGS connection.

Continuous queries now use UTC midnight on the first day through UTC
midnight on the day following the last day. The exact upper instant is
excluded locally (after source identity validation). Other out-of-window
observations still fail closed. Daily-statistic queries are unchanged.
New history manifests report raw instant counts and spans for each
requested day; these are not uptime or approved-only coverage.

## First: a controlled live probe

After running the offline tests, use the same known Faka-Union salinity
series and a single missing day, June 11. No key is printed or persisted.

```powershell
python -m unittest discover -s tests -v
python -c "from southfl.observations import usgs_observations; r,u=usgs_observations('USGS-255432081303900','00480','2026-06-11','2026-06-11','salinity',mode='continuous',series_id_filter='fdd8020bf80f435585a724c31e3cd3ac'); t=sorted(set(x['timestamp_utc'] for x in r)); print(len(t), t[:1], t[-1:])"
```

A typical 15-minute day has 96 instants from 00:00 to 23:45 UTC.
A smaller count may be a real observation gap; do not fabricate values.
Stop and investigate if the query fails or returns only midnight.

## Recover the four existing stations, preserving prior snapshots

The recovery tool verifies original plan/raw SHA-256, allowing a
reversible LF/CRLF reconstruction **only when the original recorded
digest matches exactly**, and records the verification method. It requires
a fresh unchanged source identity plan for execution. It re-queries each
original request's endpoint day, merges only new source instants, and
refuses changed overlapping values or source flags. Failures produce
an audit without a usable corrected history manifest. Use a reviewed
full redownload into a new directory if historical source records were
revised. A completed recovery is not a guarantee all days exist.

Start with Faka-Union:

```powershell
python scripts/recover_usgs_boundaries.py --history data/m10/history_01 --out data/m10/history_01_recovered
python scripts/reconcile_fcm_series.py --plan data/m10/history_01/history_plan_used.csv --out data/m10/identity_recovery_01 --probe-days 2 --min-delay 2 --execute
python scripts/recover_usgs_boundaries.py --history data/m10/history_01 --identity data/m10/identity_recovery_01 --out data/m10/history_01_recovered --max-requests 52 --execute
python scripts/build_fcm_panels.py --history data/m10/history_01_recovered --out data/m10/daily_01_recovered
```

Inspect boundary_recovery_audit.csv, recovery_manifest.json and
panel_readiness.csv. The expected targeted request counts are 52 for
Faka-Union, 36 for East River's original 120 days, and 104 for the
two M8 stations. For M8 use max-requests 104 explicitly. All are
series-window counts excluding pagination/retries/identity preflight.

For the older M8 pair use the same sequence with original history
data/m8/history_replication_v1 and separate M10 identity/history/daily
output directories. For East River, prefer the planned fresh synchronized
177-day batch_02 over repairing the obsolete 120-day window, unless a
like-for-like historical sensitivity comparison is needed. Never combine
the two East River windows as distinct stations.

## Resume M10

```powershell
python scripts/reconcile_fcm_series.py --plan data/m10/expansion_plan_v1/batch_02/history_plan.csv --out data/m10/identity_02 --probe-days 2 --min-delay 2 --execute
python scripts/fetch_fcm_history.py --plan data/m10/identity_02/history_plan.csv --out data/m10/history_02 --max-requests 80 --delay-seconds 2 --execute
python scripts/build_fcm_panels.py --history data/m10/history_02 --out data/m10/daily_02
```

Review all per-day counts, spans, true shared transitions and exact
source sensor metadata before proceeding to batches 03–06. Refit the
station experts and rerun M8/M9 evaluation into new directories only.
The original M7–M10 results remain historical snapshots. No regional
model is fitted by this correction. Connectivity and stage datums
remain unverified. Broader canonical serialization is deferred to avoid
changing hashes of older research artifacts.
