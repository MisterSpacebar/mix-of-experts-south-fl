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
    for source in sources:
        # NOAA metadata sources provide all stations in one response and are
        # filtered locally; the larger USGS/WQP sets require regional queries.
        boxes = [("domain", (-83.15, 24.35, -80.05, 26.02))] if source in (
            "coops", "ndbc") else list(REGIONS.items())
        for region, bounds in boxes:
            try:
                rows = ADAPTERS[source](bounds)
                all_rows.extend(rows)
                attempts.append(dict(source=source, region=region, success=True,
                                     n_stations=len(rows), error=""))
                print(f"{source:6s} {region:28s} {len(rows)} stations", flush=True)
            except (AcquisitionError, ValueError, KeyError, TypeError) as exc:
                attempts.append(dict(source=source, region=region, success=False,
                                     n_stations=0, error=str(exc)))
                print(f"{source:6s} {region:28s} FAILED: {exc}", flush=True)
    # An agency station may appear in multiple overlapping discovery boxes.
    # Preserve source IDs; a conflicting-coordinate entry is flagged and fails.
    by_key = {}
    for row in all_rows:
        key = (row["dataset_id"], row["site_id"])
        if key in by_key and (row["latitude"], row["longitude"]) != (
                by_key[key]["latitude"], by_key[key]["longitude"]):
            raise RuntimeError(f"conflicting site coordinates: {key}")
        by_key[key] = row
    catalog_inventory(sorted(by_key.values(), key=lambda r: (
        r["dataset_id"], r["site_id"])), out)
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources, "attempts": attempts,
        "n_unique_stations": len(by_key),
        "n_failed_queries": sum(not x["success"] for x in attempts),
        "coverage_verified": False,
        "note": "Metadata discovery only. Missing results do not prove no monitoring.",
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
