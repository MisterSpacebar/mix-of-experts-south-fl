"""Plan longer, same-site multivariate USGS source retrievals (offline).

Uses the verified 131,797-record harmonized metadata and 59,222-site snapshot.
No agency requests occur. Each panel is a group of measured concepts from
ONE canonical USGS site, avoiding unverified spatially pooled data.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv,validate_stations
from southfl.net import write_csv
from southfl.history_selection import PLAN_COLS,select_panels


def run(periods,stations,end,days,out,max_panels=3,max_concepts=4,
        sites=None,exclude_sites=None,max_per_region=None):
    periods,stations,out=Path(periods),Path(stations),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory must be new/empty")
    station_rows=read_csv(stations)
    validate_stations(station_rows)
    plan=select_panels(read_csv(periods),station_rows,end,days,
                       max_panels,max_concepts,
                       site_filter=set(sites) if sites else None,
                       exclude_sites=set(exclude_sites or ()),
                       max_per_region=max_per_region)
    if not plan:
        raise ValueError("no eligible same-site multivariate metadata candidates; "
                         "no panel or model fabricated")
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"history_plan.csv",plan,PLAN_COLS)
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "period_source":str(periods),
        "period_sha256":hashlib.sha256(periods.read_bytes()).hexdigest(),
        "station_source":str(stations),
        "n_panels":len({r["panel_id"] for r in plan}),
        "n_series_tasks":len(plan),
        "regions":dict(Counter(r["region"] for r in plan)),
        "end":end,"days":days,"source":"USGS continuous",
        "excluded_site_ids":sorted(set(exclude_sites or ())),
        "max_panels_per_screening_region":max_per_region,
        "observations_downloaded":False,"trainable":False,
        "note":"First/last metadata only; actual temporal overlap must be verified. "
               "No cross-site merges, interpolation, or causal claims.",
    }
    (out/"history_plan_manifest.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"{report['n_panels']} candidate panels, "
          f"{report['n_series_tasks']} series -> {out}")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--periods",type=Path,default=Path(
        "data/inventory/parameters_harmonized_v1/parameter_periods.csv"))
    p.add_argument("--stations",type=Path,default=Path(
        "data/inventory/combined_v3/stations.csv"))
    p.add_argument("--end",default="2026-10-31",help="fixed UTC date cutoff")
    p.add_argument("--days",type=int,default=120)
    p.add_argument("--max-panels",type=int,default=3)
    p.add_argument("--max-concepts",type=int,default=4)
    p.add_argument("--site",action="append",help="optional canonical USGS ID; repeatable")
    p.add_argument("--exclude-site",action="append",default=[],
                   help="skip already-evaluated stations BEFORE ranking candidates")
    p.add_argument("--max-per-region",type=int,default=None,
                   help="optional cap on selected stations per screened region")
    p.add_argument("--out",type=Path,default=Path("data/m7/history_plan_v1"))
    a=p.parse_args()
    run(a.periods,a.stations,a.end,a.days,a.out,
        a.max_panels,a.max_concepts,a.site,a.exclude_site,
        a.max_per_region)


if __name__=="__main__":
    main()
