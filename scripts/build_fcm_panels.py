"""Build observed-only daily FCM inputs from opt-in historical downloads.

No imputation, cross-site aggregation, or model training. Panels with any
failed source-series tasks are excluded (not silently treated as complete).
"""
import argparse,csv,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.panels import PANEL_SUMMARY_COLS,build_daily_panels


def run(history_dir,out,min_samples=8,min_span_hours=8,approved_only=False):
    history_dir,out=Path(history_dir),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new output directory required")
    manifest=json.loads((history_dir/"history_manifest.json").read_text(encoding="utf-8"))
    plan=read_csv(history_dir/"history_plan_used.csv")
    observations_path=history_dir/"observations.csv"
    if hashlib.sha256(observations_path.read_bytes()).hexdigest()!=manifest["observations_sha256"]:
        raise ValueError("raw observed data hash differs from ingestion manifest")
    failed=set(manifest.get("incomplete_panels",[]))
    allowed=[t for t in plan if t["panel_id"] not in failed]
    selected={(x["site_id"],x["series_id"]) for x in allowed}
    rows=[x for x in read_csv(observations_path)
          if (x["site_id"],x["series_id"]) in selected]
    panels,results=build_daily_panels(rows,allowed,min_samples,min_span_hours,approved_only)
    out.mkdir(parents=True,exist_ok=True)
    for pid,(concepts,daily) in panels.items():
        # pid comes from deterministic planner; reject path manipulations.
        if "/" in pid or "\\" in pid or ".." in pid:
            raise ValueError("unsafe panel identifier")
        write_csv(out/(pid+".csv"),daily,
                  ["date","site_id","panel_id"]+concepts+
                  ["n_"+c for c in concepts])
    for pid in sorted(failed):
        results.append(dict(panel_id=pid,region="",site_id="",concepts="",
            concept_units="",concept_datums="",source_series_ids="",
            n_requested_days="",n_complete_days=0,n_consecutive_daily_pairs=0,
            n_dropped_partial_days="",n_excluded_source_values="",
            first_complete_day="",last_complete_day="",status="blocked_failed_download",
            reason="one or more source-series tasks incomplete"))
    write_csv(out/"panel_readiness.csv",sorted(results,key=lambda r:r["panel_id"]),
              PANEL_SUMMARY_COLS)
    report={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "history_manifest_source":str(history_dir/"history_manifest.json"),
        "observations_sha256":manifest["observations_sha256"],
        "min_samples_per_source_day":min_samples,
        "min_utc_day_span_hours":min_span_hours,
        "approved_only":approved_only,
        "n_panels":len(panels),"n_candidate_panels":sum(
            x["status"]=="candidate_for_held_out_evaluation" for x in results),
        "incomplete_panels":sorted(failed),
        "note":"Daily arithmetic means from available within-day instants only, "
               "not instrument uptime-adjusted or gap-filled. "
               "A panel candidate still requires chronological validation.",
    }
    (out/"panels_manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"{report['n_panels']} panels, {report['n_candidate_panels']} temporal candidates; "
          f"{len(failed)} blocked by failed downloads")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--history",type=Path,default=Path("data/m7/history_run_v1"))
    p.add_argument("--out",type=Path,default=Path("data/m7/daily_panels_v1"))
    p.add_argument("--min-samples",type=int,default=8)
    p.add_argument("--min-span-hours",type=float,default=8)
    p.add_argument("--approved-only",action="store_true")
    a=p.parse_args()
    run(a.history,a.out,a.min_samples,a.min_span_hours,a.approved_only)


if __name__=="__main__":
    main()
