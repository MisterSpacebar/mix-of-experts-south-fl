"""One-command M11 recruitment, acquisition, frozen replication and integration."""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from html import escape
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.history_selection import PLAN_COLS
from southfl.regional_pipeline import Stages,choose,request_count,sha,save,json_at,EXTRA_COLS
from southfl.m10_forcing import acquire
from scripts.discover_regions import batch as discover_stations
from scripts.discover_parameters import run as discover_periods
from scripts.reconcile_fcm_series import run as reconcile
from scripts.fetch_fcm_history import run as fetch
from scripts.build_fcm_panels import run as panels
from scripts.audit_m10_regional_cohort import run as audit
from scripts.train_m8_layers import run as layers
from scripts.train_m10_regional_fcm import run as regional,load_cohort
from scripts.run_m10_residual_forcing_mixture import run as combined
from scripts.build_m10_hierarchical_atlas import run as atlas,context
from southfl.regions import REGIONS

WEST=Path("data/m10/hierarchical_atlas_v1")
WEST_COHORT=Path("data/m10/cohort_expanded_v1/station_cohort.csv")
DEFAULT=dict(regions=["north_biscayne","central_south_biscayne"],start="2025-11-01",end="2026-10-31",
             weather_id="USW00012839",tide_id="8723214",per_region=6,max_concepts=4,
             min_sites=4,max_requests=1296,delay=2.0,identity_max_age_days=7)


def attempt_is_throttled(m):
    return any("429" in json.dumps(x) or "rate limit" in json.dumps(x).lower()
               for x in m.get("requests",[]))


def serial_bundle(bundle):
    return dict(cohort=str(bundle["cohort"]),base=str(bundle["base"]),layers=str(bundle["layers"]),
                combined=str(bundle["combined"]),forcing=str(bundle["forcing"]),
                local_only=bundle["local_only"],forcing_config=bundle["forcing_config"],
                cohort_config=dict(snapshots=[[str(p) for p in s] for s in bundle["cohort_config"]["snapshots"]],
                    coordinates=str(bundle["cohort_config"]["coordinates"]),min_sites=bundle["cohort_config"]["min_sites"]))


def deserialize_bundle(raw):
    b=dict(raw)
    for k in ("cohort","base","layers","combined","forcing"):
        b[k]=Path(b[k])
    c=dict(b["cohort_config"])
    c["snapshots"]=[tuple(map(Path,s)) for s in c["snapshots"]]
    c["coordinates"]=Path(c["coordinates"])
    b["cohort_config"]=c
    return b


def integration(out,bundles,findings):
    out.mkdir(parents=True,exist_ok=True)
    west=json_at(WEST/"manifest.json")
    from southfl.temporal_integrity import verify_historical_hash
    for name,h in west["outputs_sha256"].items():
        verify_historical_hash(WEST/name,h)
    roots=[("m10_west",WEST)]+[(k,Path(v["atlas"])) for k,v in bundles.items()]
    registry=[]; coverage=[]; metrics=[]; ids=set()
    for label,root in roots:
        for r in read_csv(root/"expert_registry.csv"):
            if r["expert_id"] in ids:
                raise ValueError("duplicate expert identity across regional bundles")
            ids.add(r["expert_id"]); registry.append(dict(bundle=label,**r))
        coverage.extend(dict(bundle=label,**r) for r in read_csv(root/"region_category_coverage.csv"))
        metrics.extend(dict(bundle=label,**r) for r in read_csv(root/"route_metrics.csv") if r.get("site_id")=="all_sites")
    for name,rows in (("expert_registry.csv",registry),("region_category_coverage.csv",coverage),("regional_policy_metrics.csv",metrics)):
        fields=list(dict.fromkeys(k for r in rows for k in r))
        write_csv(out/name,rows,fields)
    def link(p):
        return Path(os.path.relpath(p,out)).as_posix()
    html=["<!doctype html><html lang='en'><meta charset='utf-8'><title>South Florida research evidence</title>",
          "<style>body{font:15px system-ui;margin:32px;color:#18324b}td,th{padding:8px;border:1px solid #abc}table{border-collapse:collapse}</style>",
          "<h1>South Florida — multi-region research evidence</h1>",
          "<p>Independent regional bundles; no cross-region blending, overall ecosystem fit, or deployment.</p><ul>"]
    for label,root in roots:
        html.append(f'<li><a href="{escape(link(root/"atlas.html"),quote=True)}">{escape(label)}</a></li>')
    html+=["</ul><h2>Regional evidence (different sites and test periods)</h2><table><tr><th>Bundle</th><th>Concept</th><th>Policy</th><th>Scope</th><th>n</th><th>MAE</th><th>Persistence MAE</th></tr>"]
    for r in metrics:
        html.append("<tr>"+"".join("<td>"+escape(r[k])+"</td>" for k in ("bundle","concept","policy","scope","n","mae","persistence_mae"))+"</tr>")
    html+=["</table><p><a href='expert_registry.csv'>Registry</a> · <a href='region_category_coverage.csv'>Coverage by bundle</a></p></html>"]
    (out/"atlas.html").write_text("\n".join(html),encoding="utf-8")
    report=dict(bundles=bundles,findings=findings,n_registry_entries=len(registry),
                n_bundles=len(roots),overall_fcm_trained=False,cross_region_gate_trained=False,
                west_manifest_sha256=sha(WEST/"manifest.json"))
    save(out/"manifest.json",report)
    return report


def run(out,config,resume=False,inventory=None):
    out=Path(out)
    # Freeze source choices and protocol before any observation is fetched.
    config=dict(config)
    if inventory:
        config["inventory"]=[{"path":str(p),"sha256":sha(p)} for p in inventory]
    config["excluded_m10_sites"]=sorted(r["site_id"] for r in read_csv(WEST_COHORT))
    config["protocol"]="m11_frozen_m10_v1"
    st=Stages(out,config,resume)
    st.verify_all()
    if inventory:
        import shutil
        def copy_inventory(p):
            p.mkdir(parents=True)
            for src,name in zip(inventory,("stations.csv","parameter_periods.csv")):
                shutil.copyfile(src,p/name)
            return True
        source=st.run("inventory",copy_inventory)
        station_path,period_path=source/"stations.csv",source/"parameter_periods.csv"
        source_deps=["inventory"]
    else:
        d=st.run("discovery",lambda p:discover_stations(["usgs"],p,config["regions"]),
                 lambda m:m["n_failed_queries"]==0)
        station_path=d/"stations.csv"
        p=st.run("periods",lambda p:discover_periods(station_path,p,["usgs"],config["regions"]),
                 lambda m:m["n_failed_requests"]==0,dependencies=["discovery"])
        period_path=p/"parameter_periods.csv"; source_deps=["discovery","periods"]
    def plan_stage(p):
        p.mkdir(parents=True)
        tasks,shortlist=choose(read_csv(station_path),read_csv(period_path),config["regions"],config["start"],config["end"],
                               set(config["excluded_m10_sites"]),config["per_region"],config["max_concepts"])
        budget=request_count(tasks)
        write_csv(p/"history_plan.csv",tasks,PLAN_COLS+EXTRA_COLS)
        write_csv(p/"shortlist.csv",shortlist,["site_id","site_name","latitude","longitude","screening_regions","selected_region","near_bottom_metadata","concepts","status"])
        save(p/"manifest.json",dict(n_tasks=len(tasks),n_sites=len({r["site_id"] for r in tasks}),planned_series_windows=budget,
                                    inventory_sha256=sha(station_path),periods_sha256=sha(period_path)))
        if budget>config["max_requests"]:
            raise ValueError("planned series-window budget exceeded")
        return True
    plan=st.run("plan",plan_stage,dependencies=source_deps)
    tasks=read_csv(plan/"history_plan.csv")
    grouped=defaultdict(list)
    for t in tasks:
        grouped[t["site_id"]].append(t)
    snapshots=defaultdict(list); deps=defaultdict(list); findings=[]
    # Complete each independent site once; never repeat a successful identity or history stage.
    for site,group in sorted(grouped.items()):
        key=site.replace("-","_"); region=group[0]["region"]
        def site_plan(p):
            p.mkdir(parents=True)
            write_csv(p/"history_plan.csv",group,PLAN_COLS+EXTRA_COLS)
            return True
        sp=st.run(key+"_plan",site_plan,dependencies=["plan"])
        def identity(p):
            m=reconcile(sp/"history_plan.csv",p,execute=True,min_delay=config["delay"],max_tasks=4)
            rows=read_csv(p/"series_identity_audit.csv")
            if any("429" in r["error"] or "rate limit" in r["error"].lower() for r in rows):
                raise RuntimeError("USGS throttle; resume later")
            return m
        ip=st.run(key+"_identity",identity,dependencies=[key+"_plan"])
        im=json_at(ip/"identity_manifest.json")
        if im["n_failed_or_unattempted_tasks"]:
            findings.append(dict(site_id=site,region=region,status="identity_unresolved",path=str(ip)))
            continue
        # Expire pending acquisition preflights individually. Already acquired
        # snapshots keep their original historical identity certificate.
        hkey=key+"_history"
        if st.state["stages"].get(hkey,{}).get("status")!="complete":
            age=datetime.now(timezone.utc)-datetime.fromisoformat(im["created_at_utc"])
            if age>timedelta(days=config["identity_max_age_days"]):
                st.state["stages"][key+"_identity"]["status"]="expired"
                save(st.path,st.state)
                ip=st.run(key+"_identity",identity,dependencies=[key+"_plan"])
                im=json_at(ip/"identity_manifest.json")
                if im["n_failed_or_unattempted_tasks"]:
                    findings.append(dict(site_id=site,region=region,status="identity_unresolved_after_refresh",path=str(ip)))
                    continue
        def history(p):
            m=fetch(ip/"history_plan.csv",p,execute=True,max_tasks=4,
                    max_requests=request_count(group),delay_seconds=config["delay"],require_identity=True)
            if attempt_is_throttled(m):
                raise RuntimeError("USGS throttle; resume later")
            return m
        hp=st.run(hkey,history,dependencies=[key+"_identity"])
        hm=json_at(hp/"history_manifest.json")
        if hm["n_failed_tasks"]:
            findings.append(dict(site_id=site,region=region,status="history_incomplete",path=str(hp)))
            continue
        dp=st.run(key+"_daily",lambda p:panels(hp,p),dependencies=[hkey])
        snapshots[region].append((dp,hp,ip)); deps[region].append(key+"_daily")
        findings.append(dict(site_id=site,region=region,status="observed_snapshot",path=str(dp)))
    bundles={}; integrated_deps=[]
    fconfig={k:config[k] for k in ("start","end","weather_id","tide_id")}
    for region in config["regions"]:
        sn=snapshots[region]
        if not sn:
            findings.append(dict(region=region,status="no_verified_observed_snapshots"))
            continue
        cc=dict(snapshots=sn,coordinates=plan/"shortlist.csv",min_sites=config["min_sites"])
        cp=st.run(region+"_cohort",lambda p:audit(sn,p,assignments=cc["coordinates"],shortlist=cc["coordinates"],
                   region=region,start=config["start"],end=config["end"],min_sites=config["min_sites"],verify_raw=True,screen_insufficient=True),
                   dependencies=deps[region])
        cm=json_at(cp/"manifest.json")
        lp=st.run(region+"_layers",lambda p:layers([d for d,_,_ in sn],p),dependencies=[region+"_cohort"])
        ready=cm["temporal_metadata_screen_pass"]
        reason="" if ready else "metadata_or_temporal_screen_failed"
        if ready:
            try:
                load_cohort(cp,False,cc)
            except ValueError as exc:
                if "insufficient shared observed test dates" not in str(exc) and "insufficient local or donor split" not in str(exc):
                    raise
                ready=False; reason=str(exc)
        b=dict(cohort=cp,layers=lp,base=cp,combined=cp,forcing=cp,local_only=not ready,
               cohort_config=cc,forcing_config=fconfig)
        adeps=[region+"_layers"]
        if ready:
            fp=st.run("forcing",lambda p:acquire(p,fconfig))
            rp=st.run(region+"_regional",lambda p:regional(cp,p,config=cc),dependencies=[region+"_cohort"])
            mp=st.run(region+"_mixture",lambda p:combined(p,fp,cohort=cp,base=rp,config=cc,forcing_config=fconfig),
                      dependencies=[region+"_regional","forcing"])
            b.update(base=rp,combined=mp,forcing=fp); adeps.append(region+"_mixture")
        ap=st.run(region+"_atlas",lambda p:atlas(p,bundle=b),dependencies=adeps)
        bundles[region]=dict(atlas=str(ap),bundle=serial_bundle(b))
        integrated_deps.append(region+"_atlas")
        findings.append(dict(region=region,status="regional_replication_complete" if ready else "local_only",reason=reason,
                             n_observed_sites=cm["n_observed_sites"],n_regional_eligible=len(cm["eligible_sites"])))
    final=st.run("integration",lambda p:integration(p,bundles,findings),dependencies=integrated_deps)
    report=json_at(final/"manifest.json")
    # Root summary is derived from immutable stage checkpoints; safe to recreate.
    lines=["# M11 — Biscayne Bay independent regional replication","",
           f"Frozen observation window: {config['start']} to {config['end']}.",
           f"Planned {len(grouped)} stations, {len(tasks)} series, {request_count(tasks)} historical series-window requests.",
           f"Integrated {report['n_bundles']} bundles (including M10 west); {report['n_registry_entries']} registry entries.",
           "No deployment or learned cross-region coupling. Review incomplete sources and local-only scopes before interpreting results.",""]
    for f in findings:
        lines.append("- "+str(f.get("site_id",f["region"]))+" — "+f["status"]+((": "+f["reason"]) if f.get("reason") else ""))
    lines+=["",f"[Integrated evidence atlas]({Path(os.path.relpath(final/'atlas.html',out)).as_posix()})"]
    (out/"INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute",action="store_true")
    p.add_argument("--resume",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--stations",type=Path)
    p.add_argument("--periods",type=Path)
    p.add_argument("--query",nargs=3,metavar=("SITE","DATE","CONCEPT"))
    p.add_argument("--bundle",default="m10_west")
    p.add_argument("--policy",default="persistence")
    p.add_argument("--scope",default="unforced")
    a=p.parse_args()
    if a.query:
        if a.bundle=="m10_west":
            router,*_=context()
        else:
            state=json_at(a.out/"checkpoint.json")
            final=a.out/state["stages"]["integration"]["path"]
            b=deserialize_bundle(json_at(final/"manifest.json")["bundles"][a.bundle]["bundle"])
            router,*_=context(bundle=b)
        print(json.dumps(router.infer(*a.query,a.policy,a.scope),indent=2))
        return
    if bool(a.stations)!=bool(a.periods):
        p.error("provide both existing inventory files, or neither")
    if not a.execute:
        print(json.dumps(DEFAULT,indent=2))
        print("Dry run; no network or files. --execute enables bounded acquisition.")
        return
    run(a.out,DEFAULT,a.resume,(a.stations,a.periods) if a.stations else None)


if __name__=="__main__":
    main()
