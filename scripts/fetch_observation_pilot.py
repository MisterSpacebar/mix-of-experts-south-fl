"""Download a small explicit observation pilot selected from source metadata.

No calls are made unless --execute is supplied; all inputs/outputs are local
and untracked. Preserve failed requests and empty results as distinct statuses.

python scripts/fetch_observation_pilot.py \
 --plan data/pilot/plans/first/pilot_plan.csv --out data/pilot/runs/first --execute
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.coverage import COVERAGE_COLUMNS, coverage
from southfl.net import AcquisitionError, write_csv
from southfl.parameters import USGS_PARAMETERS, usgs_concept
from southfl.observations import (COLS, coops_observations, usgs_observations,
                                   wqp_observations)

REQUESTED = ["dataset_id", "site_id", "concept", "start_date", "end_date",
             "parameter_code", "parameter_name", "usgs_mode"]


def validate_tasks(tasks, limit):
    if len(tasks) > limit or limit < 1 or limit > 50:
        raise ValueError("pilot exceeds --max-tasks cap (maximum 50)")
    allowed = {"usgs_water", "epa_wqp", "noaa_coops"}
    seen = set()
    for t in tasks:
        if not set(REQUESTED).issubset(t):
            raise ValueError("pilot plan missing required columns")
        if t["dataset_id"] not in allowed or not t["site_id"] or not t["concept"]:
            raise ValueError("invalid dataset/site/concept in plan")
        if not t["start_date"] or not t["end_date"]:
            raise ValueError("plan needs explicit ISO date bounds")
        start = date.fromisoformat(t["start_date"])
        end = date.fromisoformat(t["end_date"])
        if end < start:
            raise ValueError("end date precedes start date")
        days = (end - start).days + 1
        dataset = t["dataset_id"]
        if dataset == "usgs_water":
            code = t["parameter_code"]
            if code in USGS_PARAMETERS and t["concept"] != usgs_concept(code):
                raise ValueError("USGS plan uses legacy concept for " + code +
                                 "; regenerate from harmonized metadata")
        if ((dataset == "noaa_coops" and days > 28) or
            (dataset == "epa_wqp" and days > 366) or
            (dataset == "usgs_water" and days > (
                45 if t["usgs_mode"] == "daily" else 21))):
            raise ValueError(f"task window is too long for {dataset}")
        key = (dataset, t["site_id"], t["concept"])
        if key in seen:
            raise ValueError(f"duplicate task for station/concept: {key}")
        seen.add(key)
    return len(tasks)


def fetch_task(t):
    dataset = t["dataset_id"]
    site = t["site_id"]
    start, end = t["start_date"], t["end_date"]
    if dataset == "usgs_water":
        return usgs_observations(
            site, t["parameter_code"], start, end, t["concept"],
            mode=t["usgs_mode"])
    if dataset == "epa_wqp":
        return wqp_observations(
            site, t["parameter_name"], start, end, t["concept"])
    if dataset == "noaa_coops":
        return coops_observations(site, start, end)
    raise ValueError(f"unsupported source: {dataset}")


def run(plan_file, out, execute=False, max_tasks=25):
    tasks = read_csv(plan_file)
    validate_tasks(tasks, max_tasks)
    if not execute:
        print(f"DRY RUN: {len(tasks)} tasks. Add --execute to query government APIs.")
        return {"status": "dry_run", "n_tasks": len(tasks)}
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory is not empty; preserve earlier export")
    out.mkdir(parents=True, exist_ok=True)
    all_rows, requests = [], []
    for i, t in enumerate(tasks, start=1):
        print(f"[{i}/{len(tasks)}] {t['dataset_id']} {t['site_id']} "
              f"{t['concept']} {t['start_date']}..{t['end_date']}", flush=True)
        try:
            result, urls = fetch_task(t)
            all_rows.extend(result)
            requests.append(dict(
                task=i, dataset_id=t["dataset_id"], site_id=t["site_id"],
                concept=t["concept"], status="success",
                n_records=len(result), query_urls=urls, error=""))
        except (AcquisitionError, ValueError, KeyError, TypeError) as exc:
            requests.append(dict(
                task=i, dataset_id=t["dataset_id"], site_id=t["site_id"],
                concept=t["concept"], status="failed",
                n_records=0, query_urls=[], error=str(exc)))
    write_csv(out/"observations.csv", all_rows, COLS)
    write_csv(out/"sample_coverage.csv", coverage(all_rows, tasks),
              COVERAGE_COLUMNS)
    digest = hashlib.sha256((out/"observations.csv").read_bytes()).hexdigest()
    failures = sum(r["status"] == "failed" for r in requests)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_file": str(plan_file), "plan_sha256": hashlib.sha256(
            Path(plan_file).read_bytes()).hexdigest(),
        "output_sha256": digest, "n_tasks": len(tasks),
        "n_failed_tasks": failures, "n_observations": len(all_rows),
        "by_dataset": dict(Counter(r["dataset_id"] for r in all_rows)),
        "requests": requests, "observation_coverage_verified": False,
        "note": "Observed records only. Local sample dates (WQP) are not "
                "UTC timestamps. Actual sample-date counts are not sensor uptime "
                "or proof of independent biological events.",
    }
    (out/"ingestion_manifest.json").write_text(
        json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"Saved {len(all_rows)} observations; {failures} failed tasks -> {out}")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("data/pilot/runs/first"))
    p.add_argument("--execute", action="store_true",
                   help="required to make live agency requests")
    p.add_argument("--max-tasks", type=int, default=25)
    a = p.parse_args()
    manifest = run(a.plan, a.out, a.execute, a.max_tasks)
    if manifest.get("n_failed_tasks", 0):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
