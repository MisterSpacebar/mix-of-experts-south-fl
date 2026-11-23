"""Plan bounded observations from verified source metadata, without downloads.

Example:
python scripts/plan_observation_pilot.py --end 2026-10-31 \
 --periods data/inventory/parameters_v2/parameter_periods.csv \
 --stations data/inventory/batch_v2/stations.csv \
 --out data/pilot/plans/first
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv, validate_stations
from southfl.net import write_csv
from southfl.selection import PLAN_COLUMNS, plan


def run(periods, stations, out, end, max_total=18, per_region=3,
        per_source=7, usgs_mode="continuous", days_usgs=14,
        days_wqp=365, days_coops=14):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory is not empty; preserve previous plan")
    sources = read_csv(periods)
    locations = read_csv(stations)
    validate_stations(locations)
    selected = plan(sources, locations, end, max_total, per_region,
                    per_source, usgs_mode, days_usgs, days_wqp, days_coops)
    if not selected:
        raise ValueError("no candidates; inspect period metadata or adjust dates")
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out/"pilot_plan.csv", selected, PLAN_COLUMNS)
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_periods": str(periods), "input_stations": str(stations),
        "requested_end_date": end, "n_selected": len(selected),
        "sites": len({(c["dataset_id"], c["site_id"]) for c in selected}),
        "by_dataset": dict(sorted(Counter(c["dataset_id"] for c in selected).items())),
        "by_region": dict(sorted(Counter(c["region"] for c in selected).items())),
        "observations_downloaded": False, "trainable": False,
        "limits": dict(max_total=max_total, per_region=per_region,
                       per_source=per_source, usgs_mode=usgs_mode,
                       days_usgs=days_usgs, days_wqp=days_wqp,
                       days_coops=days_coops),
        "note": "Selection balances candidate regions using source metadata only; "
                "it does not establish actual station record continuity or independence.",
    }
    (out/"plan_manifest.json").write_text(
        json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
    print(f"Planned {len(selected)} bounded site-parameter downloads -> {out}")
    print("Sources:", metadata["by_dataset"])
    return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--periods", type=Path, default=Path(
        "data/inventory/parameters_v2/parameter_periods.csv"))
    p.add_argument("--stations", type=Path, default=Path(
        "data/inventory/batch_v2/stations.csv"))
    p.add_argument("--out", type=Path, default=Path("data/pilot/plans/first"))
    p.add_argument("--end", required=True, help="ISO date YYYY-MM-DD (explicit historical cutoff)")
    p.add_argument("--max-total", type=int, default=18)
    p.add_argument("--per-region", type=int, default=3)
    p.add_argument("--per-source", type=int, default=7)
    p.add_argument("--usgs-mode", choices=["continuous", "daily"], default="continuous")
    p.add_argument("--days-usgs", type=int, default=14)
    p.add_argument("--days-wqp", type=int, default=365)
    p.add_argument("--days-coops", type=int, default=14)
    a = p.parse_args()
    run(a.periods, a.stations, a.out, a.end, a.max_total, a.per_region,
        a.per_source, a.usgs_mode, a.days_usgs, a.days_wqp, a.days_coops)


if __name__ == "__main__":
    main()
