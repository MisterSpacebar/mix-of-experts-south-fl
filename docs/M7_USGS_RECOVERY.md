# Milestone 7 recovery — USGS time-series identity and API throttling

The first real historical pilot on the previously merged Milestone 7 pipeline
was **blocked before FCM fitting**, appropriately:

- A 16,398-observation cross-agency pilot was previously downloaded, but
  same-site cross-concept overlap was zero among its 55 source-series groups.
- The later 120-day USGS history plan selected 3 same-site panels (12 series).
- Nine series received real continuous site+parameter data but none matched
  the selected metadata-derived time-series ID. Three other series returned
  USGS `OVER_RATE_LIMIT` / HTTP 429.
- Therefore no complete daily panels or FCM training occurred. This is a
  **source integration problem**, not demonstrated model failure or lack of
  multivariate signal.

## Upstream schema detail (critical)

USGS's official modern OGC documentation says the time-series metadata
**`id`** field is the same series identifier as continuous observation
**`time_series_id`**. Our earlier metadata adapter incorrectly preferred
the GeoJSON **feature-level** `id` when the nested series property lacked
`time_series_id`, without checking nested `properties.id`. Those IDs may
not be interchangeable. This release changes source discovery to prioritize
`properties.id`; mismatching simultaneously declared series properties
fail rather than being guessed. This *likely* explains the user-observed
series mismatch; verify on the affected sites with the short preflight.
We have not proved on the user's live data that it is the only cause.

`scripts/reconcile_fcm_series.py` now resolves a selected series from:
1. A small live USGS metadata query **filtered to exact site and parameter**.
2. Original station, raw parameter, concept, unit, vertical datum and any
   available statistic and sublocation requirements.
3. A **1–3-day actual observation probe** for the requested historical
   interval, checking which source-series IDs really occur in the readings.
4. The original ID, if corroborated by both metadata and observations; or
   exactly ONE compatible alternate ID corroborated by both.
5. If two compatible IDs have observed values and the original is not one of
   them: refuse and record an ambiguous identity, **no arbitrary replacement**.

The resulting `series_identity_audit.csv` includes old/new series IDs,
available metadata candidates, observed probe IDs and counts, parameters,
units, datum, statistic/sublocation, source URL and failure reasons.
`identity_manifest.json` includes a SHA-256 of the complete-panel plan,
and every incomplete panel is excluded. No source snapshots are overwritten.

## Free USGS API key

Register at https://api.waterdata.usgs.gov/signup/ — the underlying service
uses api.data.gov keys. The credential is sent to your email; no approval
is required. The key increases your hourly limits but does not remove them.

On Windows PowerShell, set it in the *current terminal only*:

```powershell
$env:USGS_API_KEY = Read-Host "Enter your USGS API key"
```

**Keep it secret**: do not paste it in ChatGPT, publish it on GitHub,
commit it in any CSV/JSON, or include it in URL query parameters.
The updated shared network utility reads `USGS_API_KEY` from the process
environment and sends it **only** to `api.waterdata.usgs.gov` in the
`X-Api-Key` header. It prevents cross-host redirects for key-bearing USGS
requests, never logs the value, retries HTTP 429 at most twice with a
bounded `Retry-After`, and then stops. Other agencies receive no key.

Official USGS links:
- https://api.waterdata.usgs.gov/docs/ogcapi/keys/
- https://api.waterdata.usgs.gov/docs/ogcapi/migration/
- https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/schema?f=html

## Recommended limited recovery — one panel first

Run from the repository root. Do NOT overwrite or delete
`data/m7/history_run_v1` or the harmonized metadata inventory.

```powershell
git fetch origin
git switch fix/usgs-series-identity-auth-preflight
python -m unittest discover -s tests -v

# First run requires no agency calls and creates no output files.
python scripts/reconcile_fcm_series.py --plan data/m7/history_plan_v1/history_plan.csv --panel panel_01 --out data/m7/identity_probe_01

# After USGS key is set; two short calls per concept, not 120-day histories.
python scripts/reconcile_fcm_series.py --plan data/m7/history_plan_v1/history_plan.csv --panel panel_01 --probe-days 2 --min-delay 2 --out data/m7/identity_probe_01 --execute

# Review series_identity_audit.csv and identity_manifest.json FIRST.
# Download history using only the fully verified, source-matched plan.
python scripts/fetch_fcm_history.py --plan data/m7/identity_probe_01/history_plan.csv --out data/m7/history_verified_01

python scripts/fetch_fcm_history.py --plan data/m7/identity_probe_01/history_plan.csv --out data/m7/history_verified_01 --delay-seconds 2 --execute

python scripts/build_fcm_panels.py --history data/m7/history_verified_01 --out data/m7/daily_panels_verified_01
python scripts/preview_fcm.py --panels data/m7/daily_panels_verified_01 --out data/m7/fcm_preview_verified_01
```

Replace `panel_01` above with an **exact panel_id from the local plan**
(e.g., `panel_01_USGS_...`). It is not necessarily the literal `panel_01`.

When the single-panel preflight succeeds, test all planned panels in new
directories by *omitting* `--panel`, then download only the verified plan.

No key? You may run the identity preflight on anonymous allowance, but if it
gets 429, stop, register a key, and resume in a NEW snapshot after the limit
resets. The history downloader now requests exact `time_series_id` instead
of retrieving and discarding all other series IDs, sleeps a configurable
interval between chunks/tasks, and stops at the first 429, retaining the
successful partial source rows and a manifest. A failed panel is excluded
from modeling.

For advanced recovery only, the downloader has
`--allow-unverified-plan`; this bypasses the identity-manifest check but
**does not** bypass strict source-series matching. Do not use it for the
first real FCM preview.

## Acceptance criteria

- Live metadata `properties.id` matches USGS observation `time_series_id`
  (or an unambiguous alternative is explicitly traced in the audit).
- No unverified station/parameter, unit/datum or ambiguous source series is
  admitted into the verified history plan.
- Explicit USGS key in header is accepted without leaking into CSV/JSON.
- Small queries work without 429; the longer download completes within
  documented rate limits or stops with a precise reason.
- 120-day daily panels contain actual, consecutive, jointly observed days.
- **Only then** evaluate FCM performance on chronological held-out data.

No historical data were regenerated as part of this PR. The previous zero-model
result is preserved as a meaningful integration diagnostic.
