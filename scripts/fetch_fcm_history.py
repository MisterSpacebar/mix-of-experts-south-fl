"""Download real longer-history USGS series chosen for FCM candidates.

Dry-run by default; --execute required. One failed series leaves its entire
panel incomplete (reported), never silently fills missing measurements.
"""
import argparse,hashlib,json,sys,time
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.historical import fetch_series,windows
from southfl.net import AcquisitionError,write_csv
from southfl.observations import COLS
from southfl.history_selection import PLAN_COLS


def run(plan_path,out,execute=False,max_tasks=32,max_requests=200,
        delay_seconds=1.0,require_identity=False):
    plan_path,out=Path(plan_path),Path(out)
    tasks=read_csv(plan_path)
    if not 0<=delay_seconds<=30:
        raise ValueError("delay_seconds must be 0..30")
    if not tasks or len(tasks)>max_tasks or max_tasks>60:
        raise ValueError("empty or oversized history plan")
    if any(not set(PLAN_COLS).issubset(t) for t in tasks):
        raise ValueError("history plan missing required columns")
    identities=[(t["panel_id"],t["site_id"],t["series_id"]) for t in tasks]
    if len(set(identities))!=len(identities):
        raise ValueError("duplicate panel/series in plan")
    panels=defaultdict(set)
    total_requests=0
    for t in tasks:
        if t["dataset_id"]!="usgs_water" or t["mode"]!="continuous":
            raise ValueError("unsupported source/mode in history plan")
        panels[t["panel_id"]].add(t["site_id"])
        total_requests+=len(list(windows(t["start_date"],t["end_date"])))
    if any(len(v)!=1 for v in panels.values()):
        raise ValueError("one FCM panel cannot silently pool multiple sites")
    if total_requests>max_requests:
        raise ValueError(f"planned {total_requests} agency calls exceeds cap {max_requests}")
    if not execute:
        print(f"DRY RUN: {len(tasks)} series, {len(panels)} panels, "
              f"up to {total_requests} bounded USGS requests; add --execute")
        return {"status":"dry_run","n_tasks":len(tasks),"n_requests":total_requests}
    if require_identity:
        certified=plan_path.parent/"identity_manifest.json"
        if not certified.exists():
            raise ValueError("live history download requires verified series plan "
                             "from scripts/reconcile_fcm_series.py")
        details=json.loads(certified.read_text(encoding="utf-8"))
        if (details.get("verified_plan_sha256") !=
            hashlib.sha256(plan_path.read_bytes()).hexdigest() or
            details.get("n_verified_complete_panels",0)<1):
            raise ValueError("source identity preflight hash/coverage mismatch")
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory not empty")
    out.mkdir(parents=True,exist_ok=True)
    all_rows,results=[],[]
    stop_due_to_limit=False
    for idx,t in enumerate(tasks,1):
        if stop_due_to_limit:
            results.append(dict(panel_id=t["panel_id"],site_id=t["site_id"],
                concept=t["concept"],series_id=t["series_id"],
                status="not_attempted_due_to_rate_limit",n_records=0,
                n_other_source_series_records=0,
                n_identical_duplicates_removed=0,query_urls=[],
                error="earlier 429; remaining requests intentionally skipped"))
            continue
        if idx>1 and delay_seconds:
            time.sleep(delay_seconds)
        print(f"[{idx}/{len(tasks)}] {t['site_id']} {t['concept']} "
              f"({t['series_id']})",flush=True)
        try:
            records,urls,other,dups=fetch_series(t,request_pause_s=delay_seconds)
            all_rows.extend(records)
            results.append(dict(panel_id=t["panel_id"],site_id=t["site_id"],
                                concept=t["concept"],series_id=t["series_id"],
                                status="success",n_records=len(records),
                                n_other_source_series_records=other,
                                n_identical_duplicates_removed=dups,
                                query_urls=urls,error=""))
        except (AcquisitionError,ValueError,KeyError,TypeError) as exc:
            results.append(dict(panel_id=t["panel_id"],site_id=t["site_id"],
                                concept=t["concept"],series_id=t["series_id"],
                                status="failed",n_records=0,
                                n_other_source_series_records=0,
                                n_identical_duplicates_removed=0,
                                query_urls=[],error=str(exc)))
            if "429" in str(exc) or "rate limit" in str(exc).lower():
                stop_due_to_limit=True
    write_csv(out/"observations.csv",all_rows,COLS)
    write_csv(out/"history_plan_used.csv",tasks,PLAN_COLS)
    failure_panels={x["panel_id"] for x in results if x["status"]!="success"}
    report={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "input_plan":str(plan_path),
        "plan_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "observations_sha256":hashlib.sha256((out/"observations.csv").read_bytes()).hexdigest(),
        "n_tasks":len(tasks),"n_failed_tasks":sum(x["status"]!="success" for x in results),
        "identity_preflight_required":require_identity,
        "delay_seconds_between_requests":delay_seconds,
        "n_panels":len(panels),"incomplete_panels":sorted(failure_panels),
        "n_observations":len(all_rows),
        "by_concept":dict(Counter(x["concept"] for x in all_rows)),
        "requests":results,
        "observation_coverage_verified":False,
        "trained_models":0,
        "note":"Selected source time_series_id only. Empty complete requests are "
               "distinct from API errors. No interpolation or training claim.",
    }
    (out/"history_manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"{report['n_observations']} rows, {report['n_failed_tasks']} failed tasks; "
          f"{len(failure_panels)} incomplete panels")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path,default=Path("data/m7/history_plan_v1/history_plan.csv"))
    p.add_argument("--out",type=Path,default=Path("data/m7/history_run_v1"))
    p.add_argument("--execute",action="store_true")
    p.add_argument("--max-tasks",type=int,default=32)
    p.add_argument("--max-requests",type=int,default=200)
    p.add_argument("--delay-seconds",type=float,default=1.0)
    p.add_argument("--allow-unverified-plan",action="store_true",
                   help="advanced override; bypasses preflight protection")
    a=p.parse_args()
    report=run(a.plan,a.out,a.execute,a.max_tasks,a.max_requests,
               delay_seconds=a.delay_seconds,
               require_identity=a.execute and not a.allow_unverified_plan)
    if report.get("n_failed_tasks",0):
        raise SystemExit(2)


if __name__=="__main__":
    main()
