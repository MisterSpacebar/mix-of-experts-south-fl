"""Reclassify a verified, merged metadata snapshot without new agency calls.

The old merged parameter_periods.csv is immutable. Creates a *new* snapshot
containing the corrected USGS hydraulic taxonomy, per-series vertical_datum
and an aggregated mapping audit. Recomputes regional concept counts from the
site inventory; does not estimate trainability, completeness or datum offsets.

Example:
python scripts/harmonize_parameter_inventory.py \
 --input data/inventory/parameters_combined_v4 \
 --stations data/inventory/combined_v3/stations.csv \
 --out data/inventory/parameters_harmonized_v1
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.discover_parameters import SUMMARY_COLUMNS, concept_summary
from southfl.audit import read_csv, validate_stations
from southfl.net import write_csv
from southfl.parameters import harmonize_period_record
from southfl.periods import PERIOD_COLUMNS

AUDIT_COLUMNS = ["dataset_id", "parameter_code", "raw_parameter_name",
                 "prior_concept", "new_concept", "prior_vertical_datum",
                 "new_vertical_datum", "n_series_rows", "n_distinct_stations",
                 "action"]


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for piece in iter(lambda: source.read(1024*1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def harmonize(source_dir, station_csv, out_dir):
    source_dir, station_csv, out_dir = map(Path, (source_dir, station_csv, out_dir))
    if source_dir.resolve() == out_dir.resolve():
        raise ValueError("new output must not replace the verified source snapshot")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError("output directory must be empty; preserve previous snapshots")

    source_manifest = json.loads(
        (source_dir/"parameter_manifest.json").read_text(encoding="utf-8"))
    if (source_manifest.get("status") != "complete"
            or source_manifest.get("n_failed_requests") != 0
            or source_manifest.get("n_conflicting_metadata_records") != 0):
        raise ValueError("input parameter inventory must be complete with zero conflicts")
    source_csv = source_dir/"parameter_periods.csv"
    original_rows = read_csv(source_csv)
    if len(original_rows) != source_manifest.get("n_parameter_periods"):
        raise ValueError("input row count differs from the manifest")

    stations = read_csv(station_csv)
    validate_stations(stations)
    station_keys = {(r["dataset_id"], r["site_id"]) for r in stations}
    if any((r["dataset_id"], r["site_id"]) not in station_keys
           for r in original_rows):
        raise ValueError("parameter metadata references unknown station IDs")

    fixed, counts, sites = [], Counter(), defaultdict(set)
    for row in original_rows:
        result = harmonize_period_record(row)
        fixed.append(result)
        if (row.get("concept") != result["concept"] or
                row.get("vertical_datum", "") != result["vertical_datum"]):
            key = (row["dataset_id"], row["parameter_code"],
                   row["parameter_name"], row["concept"],
                   result["concept"], row.get("vertical_datum", ""),
                   result["vertical_datum"])
            counts[key] += 1
            sites[key].add(row["site_id"])
    audit = [dict(
        dataset_id=k[0], parameter_code=k[1], raw_parameter_name=k[2],
        prior_concept=k[3], new_concept=k[4],
        prior_vertical_datum=k[5], new_vertical_datum=k[6],
        n_series_rows=count, n_distinct_stations=len(sites[k]),
        action="code_confirmed_concept_and_datum_enrichment",
    ) for k, count in sorted(counts.items())]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir/"parameter_periods.csv", fixed, PERIOD_COLUMNS)
    write_csv(out_dir/"concept_summary.csv", concept_summary(fixed, stations),
              SUMMARY_COLUMNS)
    write_csv(out_dir/"parameter_taxonomy_changes.csv", audit, AUDIT_COLUMNS)
    for file in ("parameter_metadata_conflicts.csv", "time_series_end_advances.csv"):
        if (source_dir/file).exists():
            shutil.copyfile(source_dir/file, out_dir/file)
    manifest = dict(source_manifest)
    manifest.update(
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        status="complete", n_parameter_periods=len(fixed),
        n_changed_series_rows=sum(counts.values()),
        n_distinct_mapping_changes=len(audit),
        source_snapshot=str(source_dir),
        source_csv_sha256=_sha256(source_csv),
        output_csv_sha256=_sha256(out_dir/"parameter_periods.csv"),
        source_station_inventory=str(station_csv),
        observation_coverage_verified=False,
        taxonomy_version="hydraulic_datum_v1",
        note="USGS concept taxonomy and code-defined NGVD29/NAVD88 field updated "
             "without changing observations or underlying source snapshots. "
             "Unit/datum transformations and FCM trainability remain unverified.",
    )
    (out_dir/"parameter_manifest.json").write_text(
        json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=Path(
        "data/inventory/parameters_combined_v4"))
    p.add_argument("--stations", type=Path, default=Path(
        "data/inventory/combined_v3/stations.csv"))
    p.add_argument("--out", type=Path, default=Path(
        "data/inventory/parameters_harmonized_v1"))
    a = p.parse_args()
    report = harmonize(a.input, a.stations, a.out)
    print(f"Harmonized {report['n_parameter_periods']} metadata rows")
    print(f"Reclassified or datum-enriched: {report['n_changed_series_rows']} series")
    print(f"Code-specific taxonomy changes: {report['n_distinct_mapping_changes']}")
    print("No agency requests, datum offsets or training-readiness claims.")


if __name__ == "__main__":
    main()
