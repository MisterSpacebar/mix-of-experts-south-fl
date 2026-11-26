"""Verify source time-series IDs before historical FCM downloads.

Dry-run (no network) by default. With --execute, use a targeted live USGS
metadata query and a short observed probe for each series. Write a NEW
immutable plan containing only wholly verified site-level panels. A series
ID may change ONLY when one candidate from source metadata is unambiguously
matched in actual observations with identical site/parameter/unit/datum.

No raw API keys are ever stored.
"""
import argparse,hashlib,json,os,sys,time
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import AcquisitionError,write_csv
from southfl.history_selection import PLAN_COLS
from southfl.usgs_reconcile import AUDIT_COLUMNS,resolve_one

def run(source,out,execute=False,panel_ids=None,probe_days=2,
        min_delay=1.0,max_tasks=24):
    source,out=Path(source),Path(out)
    original=read_csv(source)
    if not original or any(not set(PLAN_COLS).issubset(t) for t in original):
        raise ValueError("original history plan lacks required columns")
    selected=[t for t in original if not panel_ids or t["panel_id"] in panel_ids]
    if not selected or len(selected)>max_tasks or max_tasks>60:
        raise ValueError("empty or oversized selected identity preflight")
    if min_delay<0 or min_delay>30:
        raise ValueError("--min-delay must be 0..30 seconds")
    panels=defaultdict(list)
    for t in selected:
        panels[t["panel_id"]].append(t)
    if any(len({t["site_id"] for t in group})!=1 for group in panels.values()):
        raise ValueError("one FCM panel must have exactly one station")
    if not execute:
        print(f"DRY RUN: {len(selected)} series in {len(panels)} panels, "
              f"up to {2*len(selected)} small USGS requests; add --execute")
        return {"status":"dry_run","tasks":len(selected)}
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory must be new/empty")
    out.mkdir(parents=True,exist_ok=True)
    result,audit=[],[]
    for i,t in enumerate(selected,1):
        if i>1 and min_delay:
            time.sleep(min_delay)
        print(f"[{i}/{len(selected)}] source ID preflight: "
              f"{t['site_id']} {t['parameter_code']}",flush=True)
        try:
            corrected,entry=resolve_one(t,probe_days=probe_days)
            result.append(corrected)
            audit.append(entry)
            print(f"  {entry['status']}: {entry['decision']}",flush=True)
        except (AcquisitionError,ValueError,KeyError,TypeError) as exc:
            audit.append(dict(panel_id=t["panel_id"],site_id=t["site_id"],
                parameter_code=t["parameter_code"],concept=t["concept"],
                old_series_id=t["series_id"],resolved_series_id="",
                status="failed",decision="no_substitution",error=str(exc)))
            print(f"  FAILED: {exc}",flush=True)
            # Key/rate throttle: stop immediately, do not hammer remaining
            # tasks. Record unattempted series explicitly.
            if "429" in str(exc) or "rate limit" in str(exc).lower():
                for waiting in selected[i:]:
                    audit.append(dict(panel_id=waiting["panel_id"],
                        site_id=waiting["site_id"],
                        parameter_code=waiting["parameter_code"],
                        concept=waiting["concept"],
                        old_series_id=waiting["series_id"],resolved_series_id="",
                        status="not_attempted_due_to_rate_limit",
                        decision="no_substitution",error="prior USGS throttle"))
                break
    failures={r["panel_id"] for r in audit if r["status"]!="verified"}
    approved=[t for t in result if t["panel_id"] not in failures]
    write_csv(out/"history_plan.csv",approved,PLAN_COLS)
    write_csv(out/"series_identity_audit.csv",audit,AUDIT_COLUMNS)
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "input_plan":str(source),
        "input_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "usgs_key_configured":bool(os.environ.get("USGS_API_KEY")),
        "n_input_tasks":len(selected),"n_verified_tasks":sum(
            r["status"]=="verified" for r in audit),
        "n_changed_series_ids":sum(r.get("status")=="verified" and
            r["old_series_id"]!=r["resolved_series_id"] for r in audit),
        "n_failed_or_unattempted_tasks":sum(r["status"]!="verified" for r in audit),
        "n_verified_complete_panels":len({x["panel_id"] for x in approved}),
        "failed_or_incomplete_panels":sorted(failures),
        "source_identity_verified":True,
        "observation_coverage_verified":False,
        "note":"Only complete panels enter the revised history plan; "
               "each new ID must be supported by current USGS time-series metadata "
               "and exact source ID in short observed probe. "
               "No approval inferred for source timestamps or FCM training.",
    }
    (out/"identity_manifest.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"{report['n_verified_complete_panels']} complete panels, "
          f"{report['n_changed_series_ids']} ID corrections, "
          f"{report['n_failed_or_unattempted_tasks']} unresolved tasks")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path,default=Path(
        "data/m7/history_plan_v1/history_plan.csv"))
    p.add_argument("--out",type=Path,default=Path("data/m7/history_identity_v1"))
    p.add_argument("--panel",action="append",help="verify only one panel ID; repeatable")
    p.add_argument("--probe-days",type=int,default=2)
    p.add_argument("--min-delay",type=float,default=1.0)
    p.add_argument("--max-tasks",type=int,default=24)
    p.add_argument("--execute",action="store_true")
    a=p.parse_args()
    report=run(a.plan,a.out,a.execute,set(a.panel) if a.panel else None,
               a.probe_days,a.min_delay,a.max_tasks)
    if report.get("n_failed_or_unattempted_tasks",0) or (
            a.execute and not report.get("n_verified_complete_panels")):
        raise SystemExit(2)

if __name__=="__main__":
    main()
