"""Combine completed old and expanded parameter-metadata snapshots.

Source series from overlapping boxes are deduplicated by their native series
identity; discrepant metadata are quarantined, never overwritten.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.discover_parameters import (SUMMARY_COLUMNS, CONFLICT_COLUMNS,
                                         concept_summary, unique_periods)
from southfl.audit import read_csv, validate_stations
from southfl.net import write_csv
from southfl.periods import PERIOD_COLUMNS


def combine(previous, expanded, stations, out):
    previous, expanded, stations, out = map(Path, (previous, expanded, stations, out))
    if out.exists() and any(out.iterdir()):
        raise ValueError("destination nonempty: preserve historical outputs")
    manifests = []
    for location in (previous, expanded):
        manifest_path = location/"parameter_manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"missing parameter manifest: {location}")
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if m.get("n_failed_requests") != 0 or m.get("n_conflicting_metadata_records") != 0:
            raise ValueError(f"incomplete parameter discovery: {location}")
        manifests.append(m)
    sites = read_csv(stations)
    validate_stations(sites)
    raw_rows = (read_csv(previous/"parameter_periods.csv") +
                read_csv(expanded/"parameter_periods.csv"))
    joined, conflicts = unique_periods(raw_rows)
    site_keys = {(x["dataset_id"], x["site_id"]) for x in sites}
    foreign = {(r["dataset_id"], r["site_id"]) for r in joined} - site_keys
    if foreign:
        raise ValueError(f"parameter records missing from merged station inventory: "
                         f"{len(foreign)} station IDs")
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out/"parameter_periods.csv", joined, PERIOD_COLUMNS)
    write_csv(out/"concept_summary.csv", concept_summary(joined, sites),
              SUMMARY_COLUMNS)
    write_csv(out/"parameter_metadata_conflicts.csv", conflicts, CONFLICT_COLUMNS)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": [str(previous), str(expanded)],
        "stations": str(stations), "n_input_rows": len(raw_rows),
        "n_parameter_periods": len(joined),
        "n_conflicting_metadata_records": len(conflicts),
        "n_failed_requests": 0, "status": "incomplete" if conflicts else "complete",
        "observation_coverage_verified": False,
        "note": "Combines only metadata: station date range and annual result "
                "counts do not establish observation completeness or model skill.",
    }
    (out/"parameter_manifest.json").write_text(
        json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--previous", type=Path, default=Path("data/inventory/parameters_v2"))
    p.add_argument("--expanded", type=Path,
                   default=Path("data/inventory/parameters_expanded_v1"))
    p.add_argument("--stations", type=Path,
                   default=Path("data/inventory/combined_v3/stations.csv"))
    p.add_argument("--out", type=Path,
                   default=Path("data/inventory/parameters_combined_v3"))
    a = p.parse_args()
    report = combine(a.previous, a.expanded, a.stations, a.out)
    print(f"{report['n_parameter_periods']} combined parameter metadata records")
    if report["status"] != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
