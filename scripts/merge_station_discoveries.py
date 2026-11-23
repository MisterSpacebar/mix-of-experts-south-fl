"""Merge old and new geographic discovery snapshots without losing stations.

Each station is keyed by (dataset_id, agency-qualified site_id). Duplicate
keys with differing coordinates are quarantined, never arbitrarily selected.
Regions are recomputed from current screening rectangles so the old inventory
acquires candidate region tags for newly added hydrological regions.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.audit import catalog_inventory, read_csv, validate_stations
from southfl.net import write_csv
from southfl.regions import regions_for

CONFLICT_COLUMNS = ["dataset_id", "site_id", "latitude_a", "longitude_a",
                    "latitude_b", "longitude_b", "reason"]


def merge_stations(previous, new, out):
    previous, new, out = (Path(x) for x in (previous, new, out))
    if out.resolve() in (previous.resolve(), new.resolve()):
        raise ValueError("out cannot overwrite an input directory")
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory is nonempty")
    # A merged inventory is only complete when both agency query snapshots
    # are complete. Do not silently promote partial tiled discovery.
    for source in (previous, new):
        manifest_path = source / "batch_manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"missing source discovery manifest: {manifest_path}")
        report = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (report.get("n_failed_queries") != 0 or
                report.get("n_coordinate_conflicts", 0) != 0):
            raise ValueError(f"source inventory is incomplete: {source}")
    original = read_csv(previous / "stations.csv")
    added = read_csv(new / "stations.csv")
    validate_stations(original)
    validate_stations(added)
    by_key, excluded, conflicts = {}, set(), []
    for row in original + added:
        key = row["dataset_id"], row["site_id"]
        if key in by_key:
            earlier = by_key[key]
            if (float(earlier["latitude"]), float(earlier["longitude"])) != (
                    float(row["latitude"]), float(row["longitude"])):
                excluded.add(key)
                conflicts.append(dict(dataset_id=key[0], site_id=key[1],
                                      latitude_a=earlier["latitude"],
                                      longitude_a=earlier["longitude"],
                                      latitude_b=row["latitude"], longitude_b=row["longitude"],
                                      reason="same_source_id_different_coordinates"))
        else:
            by_key[key] = row
    rows = []
    for key, row in sorted(by_key.items()):
        if key in excluded:
            continue
        # Regions are screening overlap only, not hydrological connectivity.
        row["regions"] = ";".join(regions_for(row["latitude"], row["longitude"]))
        rows.append(row)
    out.mkdir(parents=True, exist_ok=True)
    catalog_inventory(rows, out)
    write_csv(out / "station_coordinate_conflicts.csv", conflicts, CONFLICT_COLUMNS)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "previous": str(previous), "expanded": str(new),
        "original_site_count": len(original), "expanded_site_count": len(added),
        "combined_unique_sites": len(rows), "conflict_ids_quarantined": len(excluded),
        "source_query_failures": 0,
        "coverage_verified": False,
        "note": "Check each input discovery manifest for failed/partial queries. "
                "This merge only proves source metadata consistency.",
    }
    (out / "station_merge_manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--previous", type=Path,
                   default=Path("data/inventory/batch_v2"))
    p.add_argument("--expanded", type=Path,
                   default=Path("data/inventory/expanded_v1"))
    p.add_argument("--out", type=Path,
                   default=Path("data/inventory/combined_v3"))
    args = p.parse_args()
    report = merge_stations(args.previous, args.expanded, args.out)
    print(f"{report['combined_unique_sites']} unique station candidates")
    if report["conflict_ids_quarantined"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
