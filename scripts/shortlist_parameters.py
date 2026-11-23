"""Build a region-neutral, metadata-only shortlist for observation QA.

Reads consolidated Milestone 3 rows; does NOT infer coverage fractions,
daily measurements, survey completeness, or statistical model readiness.

python scripts/shortlist_parameters.py --parameters data/inventory/parameters_v2/parameter_periods.csv --stations data/inventory/batch_v2/stations.csv --out data/inventory/shortlist_v1
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv, validate_stations
from southfl.net import write_csv
from southfl.parameters import PRIORITY

COLUMNS = ["dataset_id", "site_id", "region", "concept", "priority",
           "n_source_series_or_slices", "n_distinct_parameters",
           "n_annual_report_years", "reported_result_count",
           "first_date_hint", "last_date_hint", "evidence",
           "next_step", "trainable", "caution"]


def build_shortlist(periods, stations, priority_max=2):
    by_site = {(r["dataset_id"], r["site_id"]): r for r in stations}
    groups = defaultdict(list)
    for record in periods:
        concept = record["concept"]
        if PRIORITY.get(concept, 99) > priority_max:
            continue
        key = (record["dataset_id"], record["site_id"])
        if key not in by_site:
            raise ValueError(f"parameter record absent from station inventory: {key}")
        site = by_site[key]
        regions = [r for r in (site.get("regions") or "").split(";") if r]
        for region in regions or ["unassigned"]:
            groups[key + (region, concept)].append(record)
    result = []
    for (dataset, site, region, concept), items in sorted(groups.items()):
        types = sorted({i["evidence"] for i in items})
        date_hints, years = [], set()
        n_reports = 0
        for item in items:
            if item["evidence"] == "time_series_first_last_metadata":
                date_hints.extend([v[:10] for v in (item["begin_utc"], item["end_utc"]) if v])
            elif item["evidence"] == "annual_result_and_activity_counts":
                if item["year"]:
                    years.add(item["year"])
                    date_hints.append(item["year"])
                if str(item["n_results"]).isdigit():
                    n_reports += int(item["n_results"])
            elif item["evidence"] == "historical_file_exists" and item["year"]:
                years.add(item["year"])
                date_hints.append(item["year"])
        evidence = ";".join(types)
        if "time_series_first_last_metadata" in types:
            next_step = "fetch_observations_and_check_coverage"
            caution = "First/last timestamps can span substantial gaps"
        elif "annual_result_and_activity_counts" in types:
            next_step = "sample_activity_date_and_method_audit"
            caution = "Reported result counts not independent dates or lab QA"
        elif "historical_file_exists" in types:
            next_step = "inspect_archive_fields_and_missing_values"
            caution = "File existence is not parameter-specific observations"
        else:
            next_step = "verify_product_observations"
            caution = "Station class is not a product-specific observation period"
        raw_parameters = set()
        for item in items:
            raw_parameters.add((item["parameter_code"], item["parameter_name"]))
        result.append(dict(
            dataset_id=dataset, site_id=site, region=region, concept=concept,
            priority=PRIORITY.get(concept, 99),
            n_source_series_or_slices=len({i["series_id"] for i in items}),
            n_distinct_parameters=len(raw_parameters),
            n_annual_report_years=len(years) if years else "",
            reported_result_count=n_reports if "annual_result_and_activity_counts" in types else "",
            first_date_hint=min(date_hints) if date_hints else "",
            last_date_hint=max(date_hints) if date_hints else "",
            evidence=evidence, next_step=next_step,
            trainable="NOT_DETERMINED",
            caution=caution + "; regional screening boxes may overlap",
        ))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parameters", type=Path, required=True)
    p.add_argument("--stations", type=Path, default=Path("data/inventory/batch_v2/stations.csv"))
    p.add_argument("--out", type=Path, default=Path("data/inventory/shortlist_v1"))
    p.add_argument("--priority-max", type=int, default=2)
    args = p.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        p.error("output directory is nonempty; choose another directory")
    station_rows = read_csv(args.stations)
    validate_stations(station_rows)
    output = build_shortlist(read_csv(args.parameters), station_rows, args.priority_max)
    write_csv(args.out / "site_parameter_candidates.csv", output, COLUMNS)
    print(f"{len(output)} site-parameter-region metadata candidates -> "
          f"{args.out / 'site_parameter_candidates.csv'}")
    print("Do not interpret these rows as independent stations or usable FCM training data.")


if __name__ == "__main__":
    main()
