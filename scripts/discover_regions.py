"""Batch station discovery by regional screening box.

Use NOAA sources by default; enable WQP and USGS explicitly. Results are
metadata candidates only, not verified variable coverage.

python scripts/discover_regions.py --sources coops ndbc
python scripts/discover_regions.py --sources coops ndbc usgs wqp
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Running this file directly from repository root must resolve the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from southfl.audit import catalog_inventory
from southfl.net import AcquisitionError
from southfl.regions import REGIONS
from southfl.sources import ADAPTERS


def batch(sources, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    all_rows = []
    attempts = []
    conflicts = []
    for source in sources:
        # NOAA metadata sources provide all stations in one response and are
        # filtered locally; the larger USGS/WQP sets require regional queries.
        boxes = [("domain", (-83.15, 24.35, -80.05, 26.02))] if source in (
            "coops", "ndbc") else list(REGIONS.items())
        for region, bounds in boxes:
            try:
                regional_conflicts = []
                if source == "usgs":
                    rows = ADAPTERS[source](bounds, conflict_sink=regional_conflicts)
                else:
                    rows = ADAPTERS[source](bounds)
                for item in regional_conflicts:
                    conflicts.append(dict(item, query_region=region))
                all_rows.extend(rows)
                attempts.append(dict(source=source, region=region,
                                     success=not regional_conflicts,
                                     partial=bool(regional_conflicts),
                                     n_conflicts=len(regional_conflicts),
                                     n_stations=len(rows),
                                     error=("quarantined conflicting USGS coordinates"
                                            if regional_conflicts else "")))
                print(f"{source:6s} {region:28s} {len(rows)} stations", flush=True)
            except (AcquisitionError, ValueError, KeyError, TypeError) as exc:
                attempts.append(dict(source=source, region=region, success=False,
                                     n_stations=0, error=str(exc)))
                print(f"{source:6s} {region:28s} FAILED: {exc}", flush=True)
    # Overlapping discovery boxes can contain the same station. Conflicts
    # encountered between regions are quarantined and audited just like
    # within a single paginated response.
    by_key = {}
    bad = set()
    for row in all_rows:
        key = (row["dataset_id"], row["site_id"])
        if key in by_key and (row["latitude"], row["longitude"]) != (
                by_key[key]["latitude"], by_key[key]["longitude"]):
            old = by_key[key]
            conflicts.append(dict(dataset_id=key[0], site_id=key[1],
                                  latitude_a=old["latitude"], longitude_a=old["longitude"],
                                  latitude_b=row["latitude"], longitude_b=row["longitude"],
                                  source_a=old["source_url"], source_b=row["source_url"],
                                  reason="different_coordinates_across_region_queries",
                                  query_region="multiple_regions"))
            bad.add(key)
        if key not in bad:
            by_key[key] = row
    for item in conflicts:
        bad.add((item["dataset_id"], item["site_id"]))
    selected = sorted((r for key, r in by_key.items() if key not in bad),
                      key=lambda r: (r["dataset_id"], r["site_id"]))
    catalog_inventory(selected, out)
    from southfl.net import write_csv
    write_csv(out / "coordinate_conflicts.csv", conflicts, [
        "dataset_id", "site_id", "latitude_a", "longitude_a",
        "latitude_b", "longitude_b", "source_a", "source_b", "reason",
        "query_region"])
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources, "attempts": attempts,
        "n_unique_stations": len(selected),
        "n_quarantined_site_ids": len(bad),
        "n_coordinate_conflicts": len(conflicts),
        "n_failed_queries": sum(not x["success"] for x in attempts),
        "coverage_verified": False,
        "note": "Metadata discovery only; conflicted IDs quarantined. Missing results do not prove no monitoring.",
    }
    (out / "batch_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", choices=sorted(ADAPTERS),
                        default=["coops", "ndbc"])
    parser.add_argument("--out", type=Path, default=Path("data/inventory/batch"))
    args = parser.parse_args()
    result = batch(args.sources, args.out)
    print(f"Unique station candidates: {result['n_unique_stations']}")
    print(f"Failed discovery queries: {result['n_failed_queries']}")
    if result["n_failed_queries"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
