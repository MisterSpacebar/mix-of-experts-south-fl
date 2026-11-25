"""Build candidate parameter-period inventory from the existing station discovery.

Inputs: the user's untracked data/inventory/batch_v2/stations.csv
Outputs: parameter_periods.csv, concept_summary.csv, conflicts.csv, manifest.json

No raw sensor measurements are downloaded. The script preserves partial work
on API failure and exits nonzero when the coverage inventory is incomplete.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv, validate_stations
from southfl.net import AcquisitionError, write_csv
from southfl.parameters import PRIORITY, harmonize_period_record
from southfl.periods import (PERIOD_COLUMNS, WQP_TYPES, coops_periods, ndbc_periods,
                             usgs_periods, wqp_periods)
from southfl.regions import REGIONS
from scripts.discover_regions import tiles_for

SUMMARY_COLUMNS = ["dataset_id", "concept", "region", "n_sites", "n_series",
                   "n_annual_summary_rows", "n_result_reports", "first_date_hint",
                   "last_date_hint", "evidence", "priority",
                   "readiness", "next_action"]
CONFLICT_COLUMNS = ["dataset_id", "site_id", "series_id", "year",
                    "first_value", "second_value", "reason"]


def unique_periods(rows):
    """Deduplicate overlapping regional queries without arbitrary overwrites."""
    seen, conflicts, excluded = {}, [], set()
    # Query URLs and region names are deliberately not part of identity.
    stable = lambda r: (r["dataset_id"], r["site_id"], r["series_id"], r["year"])
    compare = lambda r: tuple(r[c] for c in PERIOD_COLUMNS
                              if c not in ("source_url", "region_query"))
    for source_row in rows:
        row = harmonize_period_record(source_row)
        key = stable(row)
        if key in seen and compare(seen[key]) != compare(row):
            conflicts.append(dict(dataset_id=key[0], site_id=key[1],
                                  series_id=key[2], year=key[3],
                                  first_value=json.dumps(seen[key], sort_keys=True),
                                  second_value=json.dumps(row, sort_keys=True),
                                  reason="inconsistent_same_series_metadata"))
            excluded.add(key)
        elif key not in seen:
            seen[key] = row
    return [r for k, r in sorted(seen.items()) if k not in excluded], conflicts


def concept_summary(periods, station_rows):
    by_site = {(r["dataset_id"], r["site_id"]): r for r in station_rows}
    groups = defaultdict(list)
    for row in periods:
        match = by_site.get((row["dataset_id"], row["site_id"]), {})
        # A station can appear in more than one screening region.
        regions = [r for r in (match.get("regions") or "").split(";") if r]
        for region in regions or ["unassigned"]:
            groups[(row["dataset_id"], row["concept"], region)].append(row)
    output = []
    for (dataset, concept, region), recs in sorted(groups.items()):
        dates = []
        for r in recs:
            if r["evidence"] == "time_series_first_last_metadata":
                dates.extend([d[:10] for d in (r["begin_utc"], r["end_utc"]) if d])
            elif r["evidence"] in ("annual_result_and_activity_counts",
                                   "historical_file_exists") and r["year"].isdigit():
                dates.append(r["year"])
        first, last = (min(dates), max(dates)) if dates else ("", "")
        evidence = ";".join(sorted({r["evidence"] for r in recs}))
        activities = sum(int(r["n_results"]) for r in recs
                         if r["evidence"] == "annual_result_and_activity_counts"
                         and r["n_results"].isdigit())
        # No FCM is ready on metadata alone. Different evidence -> next step.
        next_action = ("download_and_QA_actual_observations" if dates else
                       "verify_per_product_observed_data_availability")
        output.append(dict(dataset_id=dataset, concept=concept, region=region,
                           n_sites=len({r["site_id"] for r in recs}),
                           n_series=len({(r["site_id"], r["series_id"]) for r in recs}),
                           n_annual_summary_rows=sum(r["evidence"] ==
                                   "annual_result_and_activity_counts" for r in recs),
                           n_result_reports=activities if activities else "",
                           first_date_hint=first, last_date_hint=last,
                           evidence=evidence, priority=PRIORITY.get(concept, 99),
                           readiness="metadata_only_not_trainable",
                           next_action=next_action))
    return output


def run(station_path, out, sources, regions, wqp_years="5", usgs_pages=60,
        overwrite=False, wqp_types=("Nutrient", "Physical"), tiles=1):
    if not (1 <= tiles <= 10):
        raise ValueError("tiles must be between 1 and 10")
    station_rows = read_csv(station_path)
    validate_stations(station_rows)
    out = Path(out)
    if out.exists() and any(out.iterdir()) and not overwrite:
        raise ValueError("output directory is not empty; choose a new path or --overwrite")
    out.mkdir(parents=True, exist_ok=True)
    station_ids = defaultdict(set)
    for r in station_rows:
        station_ids[r["dataset_id"]].add(r["site_id"])
    rows, attempts = [], []

    def attempt(source, region, subtype, fn, site_errors=None):
        label = f"{source}/{region}/{subtype}"
        print("Discovering", label, flush=True)
        try:
            result = fn()
            rows.extend(result)
            failed_sites = list(site_errors or [])
            status = "partial" if failed_sites else "success"
            attempts.append(dict(source=source, region=region, subtype=subtype,
                                 status=status, n_rows=len(result),
                                 n_failed_sites=len(failed_sites),
                                 site_errors=failed_sites,
                                 error=(f"{len(failed_sites)} station metadata requests failed"
                                        if failed_sites else "")))
            print(f"  {len(result)} candidate parameter-period records"
                  f" ({len(failed_sites)} station failures)", flush=True)
        except (AcquisitionError, ValueError, KeyError, TypeError) as exc:
            attempts.append(dict(source=source, region=region, subtype=subtype,
                                 status="failed", n_rows=0, n_failed_sites=0,
                                 site_errors=[], error=str(exc)))
            print(f"  FAILED: {exc}", flush=True)

    if "coops" in sources:
        coops_errors = []
        attempt("coops", "domain", "waterlevel_station", lambda:
                coops_periods(station_ids["noaa_coops"], errors=coops_errors),
                site_errors=coops_errors)
    if "ndbc" in sources:
        attempt("ndbc", "domain", "stdmet_archive", lambda:
                ndbc_periods(station_ids["noaa_ndbc"]))
    for region in regions:
        for i, bounds in enumerate(tiles_for(REGIONS[region], tiles)):
            query_region = f"{region}/tile_{i+1:02d}"
            if "usgs" in sources:
                attempt("usgs", query_region, "time_series_metadata",
                        lambda b=bounds, r=query_region:
                        usgs_periods(b, station_ids["usgs_water"], r,
                                     max_pages=usgs_pages))
            if "wqp" in sources:
                for typ in wqp_types:
                    attempt("wqp", query_region, typ,
                            lambda b=bounds, r=query_region, t=typ:
                            wqp_periods(b, station_ids["epa_wqp"], r, t, wqp_years))
    deduped, conflicts = unique_periods(rows)
    write_csv(out / "parameter_periods.csv", deduped, PERIOD_COLUMNS)
    write_csv(out / "concept_summary.csv",
              concept_summary(deduped, station_rows), SUMMARY_COLUMNS)
    write_csv(out / "parameter_metadata_conflicts.csv", conflicts, CONFLICT_COLUMNS)
    failures = sum(a["status"] != "success" for a in attempts)
    failed_station_requests = sum(a.get("n_failed_sites", 0) for a in attempts)
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "station_inventory": str(station_path),
        "n_stations_input": len(station_rows), "sources": sources,
        "regions": regions, "tiles_per_axis": tiles,
        "wqp_summary_years": wqp_years,
        "wqp_types": list(wqp_types),
        "n_raw_metadata_rows": len(rows), "n_parameter_periods": len(deduped),
        "n_conflicting_metadata_records": len(conflicts),
        "n_failed_requests": failures,
        "n_failed_station_requests": failed_station_requests,
        "attempts": attempts,
        "observations_downloaded": False, "observation_coverage_verified": False,
        "note": ("USGS first/last timestamps may span large gaps; WQP annual counts "
                 "are NOT sampling completeness; CO-OPS station dates and NDBC "
                 "archive names are not per-variable observations"),
    }
    (out / "parameter_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(deduped)} metadata records, {failures} failed/partial "
          f"requests ({failed_station_requests} station errors), "
          f"{len(conflicts)} conflicts in {out}")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", type=Path,
                        default=Path("data/inventory/batch_v2/stations.csv"))
    parser.add_argument("--out", type=Path,
                        default=Path("data/inventory/parameters_v1"))
    parser.add_argument("--sources", nargs="+", choices=["coops", "ndbc", "usgs", "wqp"],
                        default=["coops", "ndbc", "usgs", "wqp"])
    parser.add_argument("--regions", nargs="+", choices=sorted(REGIONS),
                        default=list(REGIONS))
    parser.add_argument("--wqp-years", choices=["1", "5", "all"], default="5")
    parser.add_argument("--wqp-types", nargs="+", choices=WQP_TYPES,
                        default=["Nutrient", "Physical"])
    parser.add_argument("--usgs-pages", type=int, default=60)
    parser.add_argument("--tiles", type=int, default=1,
                        help="tile each region into N-by-N USGS/WQP requests")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.usgs_pages < 1:
        parser.error("--usgs-pages must be >= 1")
    result = run(args.stations, args.out, args.sources, args.regions,
                 args.wqp_years, args.usgs_pages, args.overwrite,
                 args.wqp_types, args.tiles)
    if result["n_failed_requests"] or result["n_conflicting_metadata_records"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
