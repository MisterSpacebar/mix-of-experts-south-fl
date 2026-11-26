"""Milestone 8: split metadata-only USGS history plan into safe whole-panel batches.

This is OFFLINE and does not certify series identities or download data.
Each resulting history_plan.csv MUST pass reconcile_fcm_series.py --execute
before it is used with fetch_fcm_history.py --execute. The batches do
not merge stations or alter date windows.
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.history_selection import PLAN_COLS
from southfl.historical import windows
from southfl.net import write_csv

BATCH_COLS=["batch_id","panel_id","site_id","region","n_series",
            "n_expected_requests","status"]


def run(plan,out,max_requests=80,max_batches=8,exclude_sites=()):
    plan,out=Path(plan),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory must be new/empty")
    if not 1<=max_requests<=200 or not 1<=max_batches<=12:
        raise ValueError("batch limits must be bounded")
    rows=read_csv(plan)
    if not rows or any(not set(PLAN_COLS).issubset(row) for row in rows):
        raise ValueError("invalid or empty candidate history plan")
    groups=defaultdict(list)
    for row in rows:
        if row["dataset_id"]!="usgs_water" or row["mode"]!="continuous":
            raise ValueError("only continuous USGS source plans supported")
        groups[row["panel_id"]].append(row)
    excluded=set(exclude_sites)
    batches=[]
    selected=[]
    for pid,tasks in sorted(groups.items()):
        sites={t["site_id"] for t in tasks}
        if len(sites)!=1:
            raise ValueError("panel spans multiple stations")
        site=next(iter(sites))
        if site in excluded:
            continue
        identities={(t["concept"],t["series_id"]) for t in tasks}
        if len(identities)!=len(tasks):
            raise ValueError("duplicate source concept/time series in history plan")
        calls=sum(len(list(windows(t["start_date"],t["end_date"])))
                  for t in tasks)
        if calls>max_requests:
            raise ValueError(f"{pid}: needs {calls} calls, above single-batch limit "
                             f"{max_requests}. Choose fewer concepts/days or increase cap.")
        if not batches or batches[-1]["calls"]+calls>max_requests:
            batches.append({"calls":0,"tasks":[],"panels":[]})
        group=batches[-1]
        group["calls"]+=calls
        group["tasks"].extend(tasks)
        group["panels"].append((pid,site,tasks[0]["region"],len(tasks),calls))
        selected.extend(tasks)
    if not batches:
        raise ValueError("no panels remain after exclusions")
    if len(batches)>max_batches:
        raise ValueError(f"planning requires {len(batches)} bounded batches > "
                         f"{max_batches}; reduce --max-panels")
    out.mkdir(parents=True,exist_ok=True)
    index=[]
    for number,group in enumerate(batches,1):
        bid=f"batch_{number:02d}"
        dest=out/bid
        write_csv(dest/"history_plan.csv",group["tasks"],PLAN_COLS)
        index.extend(dict(batch_id=bid,panel_id=pid,site_id=site,region=region,
                          n_series=nseries,n_expected_requests=calls,
                          status="candidate_metadata_only_identity_not_verified")
                     for pid,site,region,nseries,calls in group["panels"])
        details={
            "batch_id":bid,
            "original_plan_sha256":hashlib.sha256(plan.read_bytes()).hexdigest(),
            "candidate_batch_plan_sha256":hashlib.sha256(
                (dest/"history_plan.csv").read_bytes()).hexdigest(),
            "n_planned_source_series":len(group["tasks"]),
            "n_planned_panels":len(group["panels"]),
            "max_expected_requests":group["calls"],
            "identity_verified":False,
            "downloaded":False,
            "warning":"Metadata-only candidate series: perform short live "
                      "identity preflight and check approval before any download.",
        }
        (dest/"batch_manifest.json").write_text(json.dumps(details,indent=2)+"\n",
                                                 encoding="utf-8")
    write_csv(out/"batch_index.csv",index,BATCH_COLS)
    lines=[
        "# Milestone 8 — bounded history acquisition batch index","",
        f"Input metadata plan: `{plan}`.",
        f"Panels selected: {len({r['panel_id'] for r in index})}. "
        f"Batches: {len(batches)}.",
        "No network request has been made. Candidate IDs may be stale.","",
        "For EACH batch, first run `scripts/reconcile_fcm_series.py --execute` "
        "on its `history_plan.csv`, then review the verified ID ledger. "
        "Only then execute `scripts/fetch_fcm_history.py` with the "
        "**verified** history plan, never the candidate batch plan.","",
    ]
    for batch in batches:
        i=batches.index(batch)+1
        bid=f"batch_{i:02d}"
        lines.append(f"- [{bid}](./{bid}/batch_manifest.json): "
                     f"{len(batch['panels'])} station panels, "
                     f"{len(batch['tasks'])} series, up to {batch['calls']} API calls")
    (out/"BATCHES.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    result={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_plan":str(plan),
        "source_plan_sha256":hashlib.sha256(plan.read_bytes()).hexdigest(),
        "excluded_sites":sorted(excluded),
        "n_batches":len(batches),
        "n_planned_panels":len({r["panel_id"] for r in index}),
        "n_selected_series":len(selected),
        "n_expected_requests":sum(x["calls"] for x in batches),
        "status":"metadata_only_awaiting_identity_verification",
    }
    (out/"manifest.json").write_text(json.dumps(result,indent=2)+"\n",
                                     encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-requests",type=int,default=80)
    p.add_argument("--max-batches",type=int,default=8)
    p.add_argument("--exclude-site",action="append",default=[])
    a=p.parse_args()
    result=run(a.plan,a.out,a.max_requests,a.max_batches,a.exclude_site)
    print(f"{result['n_batches']} bounded batches; "
          f"{result['n_planned_panels']} panels; "
          f"{result['n_expected_requests']} candidate requests; NO downloads")


if __name__=="__main__":
    main()
