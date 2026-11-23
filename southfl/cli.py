"""Run metadata discovery and observed-only coverage reports.

python -m southfl discover --sources coops ndbc --out data/inventory
python -m southfl coverage --observations data/processed/observations.csv
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from .audit import (AUDIT_COLUMNS, audit_observations, catalog_inventory,
                    read_csv)
from .net import AcquisitionError, write_csv
from .regions import DOMAIN, parse_bbox
from .sources import ADAPTERS


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover", help="retrieve station metadata (network required)")
    d.add_argument("--sources", nargs="+", choices=sorted(ADAPTERS), default=["coops", "ndbc"])
    d.add_argument("--bbox", type=parse_bbox, default=DOMAIN)
    d.add_argument("--out", type=Path, default=Path("data/inventory"))
    c = sub.add_parser("coverage", help="summarize observed-record counts; no imputation")
    c.add_argument("--observations", type=Path, required=True)
    c.add_argument("--out", type=Path, default=Path("data/inventory/station_coverage.csv"))
    args = p.parse_args(argv)
    if args.command == "coverage":
        rows = audit_observations(read_csv(args.observations))
        write_csv(args.out, rows, AUDIT_COLUMNS)
        print(f"Audited {len(rows)} site-variable-year combinations -> {args.out}")
        return
    rows, failures = [], {}
    for source in args.sources:
        print(f"Discovering {source} ...", flush=True)
        try:
            candidates = ADAPTERS[source](args.bbox)
            print(f"  {len(candidates)} locations", flush=True)
            rows.extend(candidates)
        except (AcquisitionError, ValueError, KeyError, TypeError) as exc:
            failures[source] = str(exc)
            print(f"  FAILED: {exc}", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    catalog_inventory(rows, args.out)
    status = dict(started_at_utc=datetime.now(timezone.utc).isoformat(),
                  requested_sources=args.sources, completed_sources=[
                      s for s in args.sources if s not in failures],
                  failures=failures, station_count=len(rows),
                  coverage_verified=False,
                  note="locations only; no per-variable data availability confirmed")
    (args.out / "discovery_manifest.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} locations; {len(failures)} failed sources")
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
