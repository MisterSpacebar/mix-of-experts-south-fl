# Station discovery and coverage audit — milestone 2

## What the code actually accomplishes

The adapters produce **station metadata candidates**, not confirmed sensor or
laboratory observations. Each API is called only when the discover command runs,
and failures are written to a manifest with a nonzero exit code. The geographic
rectangles overlap by design; they are discovery windows and **not** watershed,
marine management or ocean-current boundaries.

Four agency entry points are provided:

| Flag | Endpoint | Data returned | Limits |
|---|---|---|---|
| `coops` | NOAA CO-OPS MDAPI stations with type=waterlevels | Station ID, name and coordinates | Product availability per station not yet verified |
| `ndbc` | NOAA NDBC active stations XML | Active-site metadata | Historical/decommissioned sites excluded |
| `usgs` | USGS Water Data OGC monitoring-locations items | Monitoring site points, names and IDs | Paginated; broad requests can exceed cap and fail |
| `wqp` | Water Quality Portal station search CSV | Monitoring locations from contributing organizations | Can be large; inherited duplicates; query may need smaller boxes |

SFWMD's DBHYDRO API requires issued credentials for external access (see its
official API guide). WIN, FIU, CREMP, FIM, and county GIS remain pending
source-specific export/API adapter verification. Their catalog registry entries
are not falsely marked as successfully accessed.

## Run discovery

Clone the feature branch, then:

```bash
python scripts/catalog.py
python -m unittest discover -s tests -v
python -m southfl discover --sources coops ndbc --out data/inventory
python -m southfl discover --sources usgs --bbox=-80.55,25.3,-80.05,25.95 --out data/inventory/usgs_biscayne
python -m southfl discover --sources wqp --bbox=-80.55,25.3,-80.05,25.95 --out data/inventory/wqp_biscayne
```

Run USGS and WQP **separately by region** instead of performing one broad
query: returned pages can be large. Never equate an empty returned result to
absence of monitoring if an API request failed. Avoid rerunning the same output
directory when preserving per-source snapshots; the tool rewrites files.

Outputs:
- `stations.csv` — WGS84 point metadata and overlapping candidate regions.
- `station_counts_by_region.csv` — discovery counts; may count one station
  in several regions.
- `co_location_candidates.csv` — cross-source stations within 75 meters,
  flagged for manual review. **Not evidence that observations are duplicates.**
- `discovery_manifest.json` — sources completed, failed, and time requested.

## Run observation coverage audit

Once *observed* measurement records have been downloaded and normalized to CSV
with `dataset_id,site_id,variable,timestamp_utc,value` fields, run:

```bash
python -m southfl coverage --observations data/processed/observations.csv --out data/inventory/station_coverage.csv
```

The output counts observed records and distinct days by site, variable and
year. It deliberately leaves `coverage_fraction` blank and marks
`schedule_unknown`. A scientifically defensible percent coverage requires
deployment dates, the expected sampling schedule, and event/QA masks.
**Do not interpret a sampling-location row as evidence that a specific
chemical analyte was measured there.**

## Next acquisition tranche

1. Fetch and verify station parameter inventories and product periods.
2. Develop record-level exports for CO-OPS, USGS continuous records and EPA WQP,
   then DBHYDRO after credential provisioning (or manual export).
3. Keep original sampling depth, time, units, qualifiers and result IDs.
4. Reconcile WIN/WQP duplicates using actual sample/activity IDs, rather
   than coordinate-only matches.
5. Add GIS region polygons and true hydrological connectivity separately
   from rectangular discovery windows.

### Security and reproducibility

Do not commit access tokens, downloaded records, agency credentials or
individual source exports. The code uses standard-library HTTPS requests and
limits response size. API requests may change or be rate-limited over time.
The offline test suite uses mocked responses; a passing test does not establish
that a live government API is reachable.
