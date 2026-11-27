# M11 — Biscayne Bay in one resumable run

The default frozen protocol recruits up to six new independent USGS sites
per north and central/south discovery rectangle, with salinity and water
temperature mandatory. Existing M10 station identities are excluded for
independent geographic replication. Metadata periods must cover 2025-11-01
through 2026-10-31; instantaneous series and matching core units are required.
Near Bottom is preferred in recruitment and required for regional pooling.
Up to two extra concepts support station-local FCMs. Geometry is a discovery
screen only. No claim of 12 available sites or trainable regional cohorts.

## Run

```powershell
python -m unittest discover -s tests -v
python scripts/run_m11_biscayne.py --execute --resume --out data/m11/biscayne_v1
Get-Content data/m11/biscayne_v1/INDEX.md
```

Use the same command to resume. With no explicit inventory, discover USGS
station and time-series metadata once; if you already have suitable local
inventory files, add both `--stations PATH --periods PATH` on the first
and every subsequent run. The inventory is hashed and the protocol frozen.
The planned history request cap is 1,296 series-window requests (not
including pagination, retries, preflight or discovery), with 2-second
pacing. Use your local USGS API key. No secret is stored. No commands are
run without --execute (apart from explicit archive-only query).

Each site receives exactly one identity plan and one history stage, even
if it overlaps both rectangles. Completed stages are hashed and reused.
Failed or interrupted attempts retain their files; throttles stop the run.
A pending identity older than seven days is refreshed only for that site.
A non-throttle unresolved identity or incomplete history is recorded and
excluded rather than silently substituted. This first implementation
checkpoints at the **station/stage** level, not individual HTTP pages or
series windows; retrying a failed history stage can repeat its successful
series. To reconsider excluded stations or forcing snapshots, use a new
output root and reviewed configuration. Metadata periods do not certify
observed coverage; all actual observations go through the corrected
UTC half-open downloader and observed-only panel QA.

Regional eligibility retains M10 sensor/units and temporal checks and
requires at least four compatible stations. Fixed 60/20/20 calendar
splits; common observed target dates (>=15) for matched test evaluation.
Insufficient contiguous block support yields a point estimate without
an interval, not an artificial interpolated block. No test errors select
stations, hyperparameters or weights. Local scopes remain available when
regional readiness fails. The existing M10 station and regional training
code is reused unchanged in method. M11 is a retrospective independent
geographic replication, not prospective confirmation.

Forcing: [Miami International Airport USW00012839](https://www.ncei.noaa.gov/cdo-web/datasets/GHCND/stations/GHCND%3AUSW00012839/detail)
and [Virginia Key 8723214](https://tidesandcurrents.noaa.gov/stationhome.html?id=8723214).
The same QA and lag conventions as M10 apply; archive publication latency
is unverified. Shared forcing is acquired once only if a regional cohort
is ready. Partial forcing coverage uses existing unforced fallbacks.

The integrated atlas combines the immutable M10 registry and new regional
bundles, retaining separate metrics and distinct test populations. It
does not learn cross-region weights. The root INDEX links to the atlas.
For archive-only inference, use e.g. `--query SITE DATE CONCEPT --bundle
north_biscayne --policy adapted --scope weather_water_level` with the
same --out root. Default bundle m10_west; explicit region selection.
No unknown-site prediction or deployed model.

Before pushing, inspect raw CSV sizes and failed attempts. The output
tree can be large; GitHub limits individual files to 100 MiB. Do not
commit API keys or private data. If archiving raw separately, preserve
the exact directory layout and bytes for future checkpoint verification.
