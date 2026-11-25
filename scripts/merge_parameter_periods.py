"""Merge completed parameter snapshots with auditable live-USGS end-time drift.

Identical series metadata from overlapping regions is deduplicated. A single,
strictly increasing end_utc is accepted ONLY for the same canonical USGS
time-series ID, with all other scientific metadata identical. No other field
may change; unknown or backward timestamps are quarantined.

The original source snapshots are never modified. The reconciliation ledger
retains both versions and source-query provenance.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.discover_parameters import SUMMARY_COLUMNS, CONFLICT_COLUMNS, concept_summary
from southfl.audit import read_csv, validate_stations
from southfl.net import write_csv
from southfl.parameters import harmonize_period_record
from southfl.periods import PERIOD_COLUMNS

RECONCILIATION_COLUMNS = [
    "dataset_id", "site_id", "series_id", "year",
    "previous_end_utc", "expanded_end_utc", "elapsed_hours",
    "previous_source_url", "expanded_source_url",
    "previous_region_query", "expanded_region_query",
    "previous_snapshot_at_utc", "expanded_snapshot_at_utc", "rule",
]
PROVENANCE_COLUMNS = {"source_url", "region_query"}
SCIENCE_COLUMNS = tuple(c for c in PERIOD_COLUMNS
                        if c not in PROVENANCE_COLUMNS)
NON_END_COLUMNS = tuple(c for c in SCIENCE_COLUMNS if c != "end_utc")


def _parse_aware(value):
    if not value or not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if instant.tzinfo is None or instant.utcoffset() is None:
        return None
    return instant.astimezone(timezone.utc)


def _key(record):
    return (record["dataset_id"], record["site_id"],
            record["series_id"], record["year"])


def _equivalent(a, b, columns=SCIENCE_COLUMNS):
    return all(a[c] == b[c] for c in columns)


def _time_drift_audit(previous, expanded, previous_at="", expanded_at=""):
    """Return audit record only for an unequivocal advancing live USGS series."""
    if not (_key(previous) == _key(expanded)
            and previous["dataset_id"] == "usgs_water"
            and previous["evidence"] == "time_series_first_last_metadata"
            and expanded["evidence"] == "time_series_first_last_metadata"
            and not previous["year"] and not expanded["year"]
            and _equivalent(previous, expanded, NON_END_COLUMNS)):
        return None
    old_end = _parse_aware(previous["end_utc"])
    new_end = _parse_aware(expanded["end_utc"])
    begin = _parse_aware(previous["begin_utc"])
    if not (old_end and new_end and begin and begin <= old_end < new_end):
        return None
    old_at = _parse_aware(previous_at)
    new_at = _parse_aware(expanded_at)
    if old_at and new_at and new_at < old_at:
        # Later source timestamps cannot be attributed to a newer snapshot
        # when the recorded acquisition order is reversed.
        return None
    if new_at and new_end > new_at:
        # Do not accept purported observations later than source retrieval.
        return None
    return {
        "dataset_id": previous["dataset_id"], "site_id": previous["site_id"],
        "series_id": previous["series_id"], "year": previous["year"],
        "previous_end_utc": previous["end_utc"],
        "expanded_end_utc": expanded["end_utc"],
        "elapsed_hours": f"{(new_end - old_end).total_seconds()/3600:.3f}",
        "previous_source_url": previous["source_url"],
        "expanded_source_url": expanded["source_url"],
        "previous_region_query": previous["region_query"],
        "expanded_region_query": expanded["region_query"],
        "previous_snapshot_at_utc": previous_at,
        "expanded_snapshot_at_utc": expanded_at,
        "rule": "usgs_identical_science_fields_strictly_advancing_end_utc",
    }


def reconcile_snapshots(previous_rows, expanded_rows,
                        previous_at="", expanded_at=""):
    """Return (selected, conflicts, reconciled_advances, identical_overlap_count).

    This is intentionally separate from discovery's strict unique_periods():
    changes within *one* acquisition snapshot still require quarantine.
    """
    selected, excluded, conflicts, advances = {}, set(), [], []
    exact_overlaps = 0

    for record in previous_rows:
        key = _key(record)
        if key in selected:
            raise ValueError(f"previous snapshot has duplicate canonical series key: {key}")
        selected[key] = record

    expanded_seen = set()
    for record in expanded_rows:
        key = _key(record)
        if key in expanded_seen:
            raise ValueError(f"expanded snapshot has duplicate canonical series key: {key}")
        expanded_seen.add(key)
        if key not in selected:
            selected[key] = record
            continue
        old = selected[key]
        if _equivalent(old, record):
            exact_overlaps += 1
            continue
        audit = _time_drift_audit(old, record, previous_at, expanded_at)
        if audit:
            advances.append(audit)
            selected[key] = record  # latest end; keep newest query provenance
            continue
        conflicts.append({
            "dataset_id": key[0], "site_id": key[1],
            "series_id": key[2], "year": key[3],
            "first_value": json.dumps(old, sort_keys=True),
            "second_value": json.dumps(record, sort_keys=True),
            "reason": "inconsistent_same_series_metadata_unresolved",
        })
        excluded.add(key)

    output = [r for key, r in sorted(selected.items()) if key not in excluded]
    return output, conflicts, advances, exact_overlaps


def _manifest_time(manifest):
    return manifest.get("retrieved_at_utc") or manifest.get("generated_at_utc") or ""


def combine(previous, expanded, stations, out):
    previous, expanded, stations, out = map(Path, (previous, expanded, stations, out))
    if out.resolve() in (previous.resolve(), expanded.resolve()):
        raise ValueError("output must not overwrite either source snapshot")
    if out.exists() and any(out.iterdir()):
        raise ValueError("destination nonempty: preserve historical outputs")
    manifests = []
    for location in (previous, expanded):
        manifest_path = location/"parameter_manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"missing parameter manifest: {location}")
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (m.get("n_failed_requests") != 0 or
                m.get("n_conflicting_metadata_records") != 0 or
                m.get("status") == "incomplete"):
            raise ValueError(f"incomplete parameter discovery: {location}")
        manifests.append(m)
    sites = read_csv(stations)
    validate_stations(sites)
    # Original local snapshots predate the vertical_datum column and used
    # 'water_level' for USGS 00065. Normalize BOTH inputs identically before
    # comparing science fields so the verified end-date drift policy remains
    # valid without requerying any agency or mutating source CSV files.
    old_rows = [harmonize_period_record(r) for r in
                read_csv(previous/"parameter_periods.csv")]
    new_rows = [harmonize_period_record(r) for r in
                read_csv(expanded/"parameter_periods.csv")]
    for rows, manifest, location in zip((old_rows, new_rows),
                                         manifests, (previous, expanded)):
        stated = manifest.get("n_parameter_periods")
        if stated is not None and int(stated) != len(rows):
            raise ValueError(f"parameter row count differs from manifest: {location}")
    joined, conflicts, advances, identical_overlaps = reconcile_snapshots(
        old_rows, new_rows, _manifest_time(manifests[0]), _manifest_time(manifests[1]))
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
    write_csv(out/"time_series_end_advances.csv", advances, RECONCILIATION_COLUMNS)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": [str(previous), str(expanded)],
        "source_snapshot_at_utc": [_manifest_time(m) for m in manifests],
        "stations": str(stations),
        "n_input_rows": len(old_rows) + len(new_rows),
        "n_parameter_periods": len(joined),
        "n_identical_overlaps_deduplicated": identical_overlaps,
        "n_reconciled_usgs_end_advances": len(advances),
        "n_conflicting_metadata_records": len(conflicts),
        "n_failed_requests": 0,
        "status": "incomplete" if conflicts else "complete",
        "observation_coverage_verified": False,
        "note": "Cross-snapshot reconciliation accepts ONLY strictly advancing "
                "USGS live time-series end_utc with all other scientific metadata "
                "unchanged; every advance is logged. This remains metadata only: "
                "first/last dates do not prove temporal completeness or model skill.",
    }
    (out/"parameter_manifest.json").write_text(
        json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--previous", type=Path,
                   default=Path("data/inventory/parameters_v2"))
    p.add_argument("--expanded", type=Path,
                   default=Path("data/inventory/parameters_expanded_v1"))
    p.add_argument("--stations", type=Path,
                   default=Path("data/inventory/combined_v3/stations.csv"))
    p.add_argument("--out", type=Path,
                   default=Path("data/inventory/parameters_combined_v4"))
    a = p.parse_args()
    report = combine(a.previous, a.expanded, a.stations, a.out)
    print(f"{report['n_parameter_periods']} combined parameter metadata records")
    print(f"{report['n_reconciled_usgs_end_advances']} audited USGS end-date advances")
    print(f"{report['n_conflicting_metadata_records']} unresolved discrepancies")
    if report["status"] != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
