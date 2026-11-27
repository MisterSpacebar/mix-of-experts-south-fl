"""Build the M10.4 research registry, route replay and cross-axis evidence atlas."""
import argparse
import json
import sys
from collections import Counter,defaultdict
from datetime import date,timedelta
from html import escape
from math import isclose
from pathlib import Path
from statistics import mean

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.temporal_integrity import verify_historical_hash
from southfl.m10_forcing import load as load_forcing, FEATURES,sha
from southfl.hierarchical_experts import ResearchRouter,validate_station_model,validate_fold
from southfl.m9_atlas import validate_trained_edges
from southfl.regions import REGIONS,regions_for
from visuals.hierarchy import classify,CATEGORIES
from scripts.train_m10_regional_fcm import COHORT,load_cohort,normalize
from scripts.run_m10_residual_forcing_mixture import BASE,verify_original

ROOT=Path("data/m10")
LAYERS=ROOT/"layers_expanded_v1"
COMBINED=ROOT/"residual_forcing_mixture_v1"
FORCING=ROOT/"forcing_v1"
POLICIES=("zero_shot","adapted")
SCOPES=("unforced",*FEATURES)


def json_at(p):
    return json.loads(p.read_text(encoding="utf-8"))


def safe_under(root,relative):
    p=(root/normalize(relative)).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError("unsafe expert artifact path")
    return root/normalize(relative)


def map_field(text):
    return dict(x.split("=",1) for x in text.split(";") if x)


def close(a,b):
    return isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-8)


def context(verify_raw=False,bundle=None):
    COHORT,BASE,LAYERS,COMBINED,FORCING=(globals()[k] for k in ('COHORT','BASE','LAYERS','COMBINED','FORCING')) if bundle is None else (bundle[k] for k in ('cohort','base','layers','combined','forcing'))
    config=None if bundle is None else bundle['cohort_config']
    forcing_config=None if bundle is None else bundle['forcing_config']
    local_only=bundle is not None and bundle.get("local_only",False)
    if local_only:
        from scripts.audit_m10_regional_cohort import load_snapshot
        cm=json_at(COHORT/"manifest.json")
        lineage={}
        for daily,history,identity in config["snapshots"]:
            _,audit=load_snapshot(daily,history,identity,verify_raw)
            lineage[str(daily)]=audit
        folds,forcing,fm={}, {}, {}
        manifest={"n_prediction_rows":0,"n_reference_targets":0}
    else:
        cm,splits,lineage=load_cohort(COHORT,verify_raw,config)
        verify_original(splits,BASE)
        manifest=json_at(COMBINED/"manifest.json")
        if (manifest["sites"]!=sorted(splits) or manifest["deployed_model_trained"] is not False or
            manifest["model_selection_on_test"] is not False or
            manifest["regional_transport_model_trained"] is not False):
            raise ValueError("unexpected combined experiment scope")
        for p,key in ((COHORT/"manifest.json","cohort_manifest_sha256"),
                      (BASE/"manifest.json","original_manifest_sha256"),
                      (FORCING/"manifest.json","forcing_manifest_sha256")):
            verify_historical_hash(p,manifest[key])
        for f,h in manifest["outputs_sha256"].items():
            verify_historical_hash(safe_under(COMBINED,f),h)
        forcing,fm=load_forcing(FORCING,forcing_config)
        folds=json_at(COMBINED/"fold_models.json")
        if set(folds)!=set(splits):
            raise ValueError("missing or unexpected heldout fold")
        for site,fold in folds.items():
            validate_fold(site,fold,sorted(splits),cm["train_target_date_end"],cm["validation_target_date_end"])
    registry={}; models={}; stations={}; source_hashes={}
    def track(p):
        source_hashes[str(p)]=sha(p)
    tracked=[COHORT/"station_cohort.csv",LAYERS/"manifest.json",LAYERS/"model_registry.csv"]
    if not local_only:
        tracked.extend([COMBINED/"manifest.json",FORCING/"manifest.json",BASE/"manifest.json"])
    for p in tracked:
        track(p)
    for r in read_csv(COHORT/"station_cohort.csv"):
        site=r["site_id"]; path=normalize(r["daily_path"])
        if site in stations:
            raise ValueError("duplicate station")
        verify_historical_hash(path,r["daily_sha256"])
        ready=[p for p in read_csv(path.parent/"panel_readiness.csv") if p["site_id"]==site]
        if len(ready)!=1 or ready[0]["panel_id"]!=r["panel_id"]:
            raise ValueError("ambiguous station panel")
        units=map_field(ready[0]["concept_units"]); datums=map_field(ready[0]["concept_datums"])
        states={}
        for row in read_csv(path):
            if row["site_id"]!=site or row["date"] in states:
                raise ValueError("invalid station state identity")
            states[row["date"]]={c:float(row[c]) for c in units}
        # Archive scope fixed from panel dates; no target existence test in inference.
        allowed=set()
        if states:
            left=date.fromisoformat(min(states))+timedelta(days=1)
            right=date.fromisoformat(max(states))
            while left<=right:
                allowed.add(left.isoformat()); left+=timedelta(days=1)
        stations[site]=dict(r,units=units,datums=datums,states=states,allowed_dates=allowed,
                            geographic_screens=regions_for(float(r["latitude"]),float(r["longitude"])))
        track(path); track(path.parent/"panel_readiness.csv")
    def add(e):
        if e["expert_id"] in registry:
            raise ValueError("duplicate expert ID")
        registry[e["expert_id"]]=e
    layer_rows=read_csv(LAYERS/"model_registry.csv")
    entries=[]
    for r in layer_rows:
        site=r["site_id"]; s=stations[site]
        cs=r["concepts"].split(";")
        if (r["panel_id"]!=s["panel_id"] or r["region"]!=s["primary_region"] or
            not set(cs)<=set(s["units"])):
            raise ValueError("layer registry contradicts station")
        verify_historical_hash(normalize(s["daily_path"]),r["panel_sha256"])
        trained=r["status"] in ("trained_station_expert","trained_within_station_prototype")
        e=dict(expert_id="station:"+site+":"+r["level"]+":"+r["category"]+":"+r["subcategory"],
               site_id=site,region=r["region"],kind="station_fcm" if trained else "unfitted_candidate",
               level=r["level"],category=r["category"],subcategory=r["subcategory"],concepts=cs,
               units={c:s["units"][c] for c in cs},status=r["status"],
               reason=r["reason"],source=r["model_directory"],source_root=str(LAYERS),alias_of="",
               fit_sites=[site] if trained else [],required_forcing=[],train_end="",validation_end="",
               test_start="",test_end="",deployable=False)
        if trained:
            root=safe_under(LAYERS,r["model_directory"])
            model=json_at(root/"fcm_model.json")
            validate_station_model(model,cs)
            validate_trained_edges(model,read_csv(root/"edge_weights.csv"))
            for name in ("fcm_model.json","edge_weights.csv","heldout_predictions.csv","heldout_metrics.csv"):
                track(root/name)
            e.update(train_end=model["train_end"],validation_end=model["validation_end"],
                     test_start=model["test_start"],test_end=model["test_end"],
                     artifact_sha256=sha(root/"fcm_model.json"))
            models[e["expert_id"]]=model
        entries.append((r,e)); add(e)
    dirs={r["model_directory"]:e for r,e in entries if r["model_directory"]}
    for r,e in entries:
        if r["same_concept_set_as"]:
            canonical=dirs[r["same_concept_set_as"]]
            if canonical["site_id"]!=e["site_id"] or set(canonical["concepts"])!=set(e["concepts"]):
                raise ValueError("invalid duplicate concept-scope alias")
            e["alias_of"]=canonical["expert_id"]
    for site,s in stations.items():
        add(dict(expert_id="persistence:"+site,site_id=site,region=s["primary_region"],
                 kind="persistence",level="baseline",category="",subcategory="",
                 concepts=list(s["units"]),units=s["units"],status="observed_state_baseline",
                 fit_sites=[],required_forcing=[],source=s["daily_path"],alias_of="",deployable=False))
    # One registry record per residual component and fixed mixture policy.
    # Site is the fold target, not a regional training site identifier.
    for site,f in folds.items():
        for scope in SCOPES:
            detail=f["forcing"].get(scope,{})
            if scope=="unforced":
                components={"regional":f["residual_regional"],"local":f["residual_local"]}
            else:
                components={k:detail[v] for k,v in (("regional","forced"),("local","local_forced")) if v in detail}
            for name,m in components.items():
                add(dict(expert_id=f"residual:{site}:{name}:{scope}",site_id=site,
                         region=cm["region_screen"],kind="residual_component",
                         level="regional" if name=="regional" else "local_adaptation",
                         category="water_quality",subcategory="",concepts=cm["concepts"],
                         units={"salinity":"ppt","water_temperature":"degC"},
                         status="retrospective_fold_fit",fit_sites=m["fit_sites"],
                         source_selector=([site,"residual_"+name] if scope=="unforced" else
                                          [site,"forcing",scope,"forced" if name=="regional" else "local_forced"]),
                         required_forcing=list(FEATURES.get(scope,())),source=str(COMBINED/"fold_models.json"),artifact_sha256=sha(COMBINED/"fold_models.json"),
                         alias_of="",train_end=m["train_end"],validation_end=m["validation_end"],
                         test_start=(date.fromisoformat(cm["validation_target_date_end"])+timedelta(days=1)).isoformat(),
                         test_end=cm["end"],deployable=False))
            for policy in POLICIES:
                fitted=scope=="unforced" or ("regional" in components and
                       (policy=="zero_shot" or "local" in components))
                add(dict(expert_id=f"mixture:{site}:{policy}:{scope}",site_id=site,
                         region=cm["region_screen"],kind="mixture",level="regional_policy",
                         category="water_quality",subcategory="",concepts=cm["concepts"],
                         units={"salinity":"ppt","water_temperature":"degC"},
                         status="retrospective_policy" if fitted else "fallback_only",
                         source_selector=([site,policy+"_gate"] if scope=="unforced" else
                                          [site,"forcing",scope,policy+"_gate"]),
                         fit_sites=[],gate_validation_sites=f["gate_validation_sites"][policy],
                         required_forcing=list(FEATURES.get(scope,())),source=str(COMBINED/"fold_models.json"),artifact_sha256=sha(COMBINED/"fold_models.json"),
                         alias_of="",validation_end=cm["validation_target_date_end"],deployable=False))
    router=ResearchRouter(stations,registry,models,folds,forcing,cm)
    return router,entries,manifest,fm,source_hashes,lineage


def replay(router,entries,manifest,bundle=None):
    COMBINED,LAYERS=(globals()[k] for k in ('COMBINED','LAYERS')) if bundle is None else (bundle[k] for k in ('combined','layers'))
    # Station experts have their OWN original chronological test windows.
    # Never compare their errors to regional models on unmatched dates.
    rows=[]; expected={}
    for r in ([] if bundle is not None and bundle.get("local_only",False) else read_csv(COMBINED/"predictions.csv")):
        k=(r["site_id"],r["date"],r["concept"],r["model"])
        if k in expected:
            raise ValueError("duplicate combined prediction")
        expected[k]=r
    if len(expected)!=manifest["n_prediction_rows"]:
        raise ValueError("combined prediction count mismatch")
    station_edges=[]; residual_edges=[]; weights=[]
    for src,e in entries:
        if e["kind"]!="station_fcm":
            continue
        site=e["site_id"]; m=router.models[e["expert_id"]]
        root=safe_under(LAYERS,e["source"])
        seen=set()
        for r in read_csv(root/"heldout_predictions.csv"):
            k=r["date"],r["concept"]
            if k in seen:
                raise ValueError("duplicate station prediction")
            seen.add(k)
            out=router.infer(site,r["date"],r["concept"],"expert",expert_id=e["expert_id"])
            actual=router.stations[site]["states"][r["date"]][r["concept"]]
            if out["selected_expert"]!=e["expert_id"] or not close(out["prediction"],r["fcm"]) or not close(actual,r["actual"]):
                raise ValueError("station expert replay mismatch")
            rows.append(dict(out,actual=actual,reference_prediction=float(r["fcm"]),
                             evidence="original_station_holdout"))
        if len(seen)!=len(e["concepts"])*m["test_pairs"]:
            raise ValueError("station holdout count mismatch")
        for i,a in enumerate(e["concepts"]):
            for j,b in enumerate(e["concepts"]):
                station_edges.append(dict(expert_id=e["expert_id"],site_id=site,region=e["region"],
                    level=e["level"],alias_of=e["alias_of"],source_concept=a,target_concept=b,
                    source_category=classify(a)[0],target_category=classify(b)[0],
                    weight=m["matrix_source_to_target"][i][j],
                    evidence="within_station_predictive_coefficient"))
    expected_mixture=0
    for site,f in router.folds.items():
        for scope in SCOPES:
            for policy in POLICIES:
                name=policy+"_blend" if scope=="unforced" else scope+"_"+policy+"_fallback"
                matches=[r for k,r in expected.items() if k[0]==site and k[3]==name]
                n=manifest["n_reference_targets"]//len(router.folds)
                if len(matches)!=n:
                    raise ValueError("mixture is not evaluated on every matched target")
                for r in matches:
                    out=router.infer(site,r["date"],r["concept"],policy,scope)
                    actual=router.stations[site]["states"][r["date"]][r["concept"]]
                    if not close(out["prediction"],r["prediction"]) or not close(actual,r["actual"]):
                        raise ValueError("mixture replay mismatch")
                    rows.append(dict(out,actual=actual,reference_prediction=float(r["prediction"]),
                                     evidence="original_spatial_temporal_holdout"))
                    expected_mixture+=1
                detail=f if scope=="unforced" else f["forcing"].get(scope,{})
                if policy+"_gate" in detail:
                    for c,w in zip(router.cohort["concepts"],detail[policy+"_gate"]):
                        weights.append(dict(site_id=site,region=router.cohort["region_screen"],scope=scope,
                            policy=policy,concept=c,persistence=w[0],regional=w[1],local=w[2],
                            evidence="pretest_validation_selected_fixed_weights"))
            detail=f["forcing"].get(scope,{})
            ms={"regional":f["residual_regional"],"local":f["residual_local"]} if scope=="unforced" else {
                k:detail[v] for k,v in (("regional","forced"),("local","local_forced")) if v in detail}
            names=router.cohort["concepts"]+list(FEATURES.get(scope,()))
            for role,m in ms.items():
                for j,c in enumerate(router.cohort["concepts"]):
                    for i,a in enumerate(names):
                        residual_edges.append(dict(expert_id=f"residual:{site}:{role}:{scope}",
                            heldout_site=site,scope=scope,role=role,source_feature=a,target_concept=c,
                            source_type="observed_state" if i<2 else "external_proxy",
                            weight=m["weights"][j][i+1],
                            evidence="standardized_input_to_scaled_delta_not_transport"))
    return rows,station_edges,residual_edges,weights,expected_mixture


def summarize(rows):
    groups=defaultdict(list)
    for r in rows:
        # Do not pool station-specific expert scopes with mismatched test windows.
        key=(r["site_id"],r["concept"],r["requested_policy"],r["requested_scope"],
             r["selected_expert"] if r["requested_policy"]=="expert" else "")
        groups[key].append(r)
        if r["evidence"]=="original_spatial_temporal_holdout":
            groups[("all_sites",r["concept"],r["requested_policy"],r["requested_scope"],"")].append(r)
    return [dict(site_id=k[0],concept=k[1],policy=k[2],scope=k[3],expert_id=k[4],
                 n=len(v),mae=mean(abs(r["prediction"]-r["actual"]) for r in v),
                 persistence_mae=mean(abs(r["components"]["persistence"]-r["actual"]) for r in v)
                 if k[2]!="expert" else "",
                 n_forcing_fallback=sum(r["fallback_reason"]=="forcing_missing_or_unfitted" for r in v),
                 evidence=v[0]["evidence"]) for k,v in sorted(groups.items())]


def coverage(router):
    result=[]
    for region in REGIONS:
        for cat in CATEGORIES:
            # Primary regions are exclusive for this count. Screening overlap
            # is reported separately and must not be counted as extra stations.
            observed=[s for s in router.stations.values() if s["primary_region"]==region and
                      any(classify(c)[0]==cat for c in s["units"])]
            screened=[s for s in router.stations.values() if region in s["geographic_screens"] and
                      any(classify(c)[0]==cat for c in s["units"])]
            local=[e for e in router.registry.values() if e["kind"]=="station_fcm" and
                   not e["alias_of"] and e["region"]==region and
                   any(classify(c)[0]==cat for c in e["concepts"])]
            regional=(bool(router.folds) and region==router.cohort["region_screen"] and cat=="water_quality")
            result.append(dict(region=region,category=cat,primary_observed_sites=len(observed),
                screened_observed_sites=len(screened),distinct_local_fitted_scopes=len(local),
                regional_holdout_folds=len(router.folds) if regional else 0,
                status="regional_retrospective_evidence" if regional else
                       "station_local_evidence" if local else "observed_only" if observed else "screened_overlap_only" if screened else "not_observed",
                deployed=False,transport_verified=False))
    return result


def html_atlas(out,router,cover,summary,weights):
    def table(headers,rows):
        return ("<table><thead><tr>"+"".join("<th>"+escape(str(h))+"</th>" for h in headers)+
            "</tr></thead><tbody>"+"".join("<tr>"+"".join("<td>"+escape(str(v))+"</td>" for v in r)+"</tr>" for r in rows)+"</tbody></table>")
    # Render an offline evidence matrix, not a causal network.
    cells={(r["region"],r["category"]):r for r in cover}
    region_rows=[]
    for region in REGIONS:
        row=[region.replace("_"," ")]
        for cat in CATEGORIES:
            c=cells[region,cat]
            row.append(f"{c['primary_observed_sites']} primary / {c['screened_observed_sites']} screened; "
                       f"{c['distinct_local_fitted_scopes']} local; {c['regional_holdout_folds']} folds")
        region_rows.append(row)
    scores=[[r["concept"],r["policy"],r["scope"],r["n"],f"{r['mae']:.4f}",
             f"{r['persistence_mae']:.4f}",r["n_forcing_fallback"]]
            for r in summary if r["site_id"]=="all_sites"]
    links="".join(f'<li><a href="{f}">{label}</a></li>' for f,label in (
        ("expert_registry.csv","Expert registry"),("region_category_coverage.csv","Region/category coverage"),
        ("station_edges.csv","Station FCM edges"),("residual_edges.csv","Residual predictive coefficients"),
        ("mixture_weights.csv","Validation-selected weights"),("route_replay.csv","Inference replay"),
        ("route_metrics.csv","Route performance"),("paired_policy_evidence.csv","Conditional paired uncertainty"),("manifest.json","Source lineage")))
    content=("<!doctype html><html lang='en'><meta charset='utf-8'><title>M10.4 evidence atlas</title>"
             "<style>body{font:15px system-ui;margin:32px;color:#18324b;max-width:1500px}h1,h2{color:#245b89}"
             "table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:9px;border:1px solid #cbd5df;"
             "text-align:left;vertical-align:top}th{background:#e5eff8}tr:nth-child(even){background:#f6f9fc}"
             "a{color:#245b89}.note{padding:12px;background:#edf4fa}</style>"
             "<h1>South Florida expert evidence atlas</h1><p class='note'>Retrospective research only. "
             "No deployed expert, cross-station transport or overall ecosystem fit. Geographic screens overlap; "
             "counts of local fits are not counts of independent stations.</p><h2>Region × subsystem</h2>"+
             table(["Region",*CATEGORIES],region_rows)+"<h2>Matched regional policy performance</h2>"+
             table(["Concept","Policy","Scope","n","MAE","Persistence MAE","Forcing fallbacks"],scores)+
             "<h2>Validation-selected mixture weights</h2>"+
             table(["Target station","Scope","Policy","Concept","Persistence","Regional","Local"],
                   [[r[k] for k in ("site_id","scope","policy","concept","persistence","regional","local")] for r in weights])+
             "<h2>Evidence files</h2><ul>"+links+"</ul><p>Edges are predictive coefficients, not causality. "
             "Station holdout dates vary; only matched regional policy errors are aggregated here. "
             "The evaluation is retrospective and forcing publication timing is unverified.</p></html>")
    (out/"atlas.html").write_text(content,encoding="utf-8")


def run(out,verify_raw=False,bundle=None):
    COMBINED=globals()['COMBINED'] if bundle is None else bundle['combined']
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty atlas output required")
    router,entries,manifest,fm,source_hashes,lineage=context(verify_raw,bundle)
    rows,se,re,weights,nmix=replay(router,entries,manifest,bundle)
    scores=summarize(rows); cover=coverage(router)
    original_comparisons={(r["site_id"],r["concept"],r["model"],r["baseline"]):r
        for r in ([] if bundle is not None and bundle.get("local_only",False) else read_csv(COMBINED/"paired_comparisons.csv"))}
    paired=[]
    for r in scores:
        if r["evidence"]!="original_spatial_temporal_holdout":
            continue
        name=r["policy"]+"_blend" if r["scope"]=="unforced" else r["scope"]+"_"+r["policy"]+"_fallback"
        src=original_comparisons[r["site_id"],r["concept"],name,"persistence"]
        if int(src["n"])!=r["n"] or not close(src["delta_mae"],r["mae"]-r["persistence_mae"]):
            raise ValueError("paired comparison point estimate mismatch")
        paired.append(dict(src,policy=r["policy"],scope=r["scope"]))
    out.mkdir(parents=True,exist_ok=True)
    def export(name,rs):
        # JSON-encode nested values to preserve schema in CSV.
        flat=[{k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rs]
        fields=list(dict.fromkeys(k for r in flat for k in r))
        if not fields:
            fields={"route_replay.csv":["site_id","concept","prediction"],"route_metrics.csv":["site_id","concept","mae"],"station_edges.csv":["expert_id","weight"],"residual_edges.csv":["expert_id","weight"],"mixture_weights.csv":["site_id","scope","policy"],"paired_policy_evidence.csv":["site_id","concept","policy","scope"]}.get(name,["status"])
        write_csv(out/name,flat,fields)
    export("expert_registry.csv",list(router.registry.values()))
    export("route_replay.csv",rows); export("route_metrics.csv",scores)
    export("station_edges.csv",se); export("residual_edges.csv",re)
    export("mixture_weights.csv",weights); export("region_category_coverage.csv",cover)
    export("paired_policy_evidence.csv",paired)
    html_atlas(out,router,cover,scores,weights)
    counts=Counter(e["kind"] for e in router.registry.values())
    report=dict(n_observed_stations=len(router.stations),n_registry_entries=len(router.registry),
        registry_counts=dict(counts),n_duplicate_scope_aliases=sum(bool(e["alias_of"]) for e in router.registry.values()),
        n_regional_holdout_folds=len(router.folds),n_station_replay_targets=len(rows)-nmix,
        n_mixture_replay_targets=nmix,n_route_replay_rows=len(rows),n_station_edges=len(se),
        n_residual_edges=len(re),n_mixture_weight_rows=len(weights),n_region_category_cells=len(cover),
        replay_matches_original=True,raw_reverified=verify_raw,source_lineage=lineage,
        source_hashes=source_hashes,source_experiment_manifest_sha256=(None if bundle is not None and bundle.get("local_only",False) else sha(COMBINED/"manifest.json")),
        model_selection_on_test=False,exploratory_reused_test_period=bundle is None,
        deployed_experts=0,overall_ecosystem_fcms_trained=0,new_models_trained=0,
        regional_transport_model_trained=False,hydrological_connectivity_verified=False,
        as_issued_availability_verified=False,exact_sensor_depth_verified=False,
        outputs_sha256={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    lines=["# M10.4 — hierarchical research evidence atlas","",
           f"{report['n_observed_stations']} stations; {report['n_registry_entries']} registry entries; "
           f"{report['n_regional_holdout_folds']} regional folds; {len(rows)} reproduced predictions.",
           "No new fits or deployment. All routes are archive-only.", "",
           "[Open offline HTML atlas](atlas.html) · [Expert registry](expert_registry.csv) · [Route metrics](route_metrics.csv)","",
           "## Scientific synthesis","",
           "M10.3.1 absolute-state activation saturated outside donor training ranges. "
           "M10.3.2 fixed-coefficient activation ablation recovered the pooled ridge result. "
           "Residual experts use persistence as the anchor; no general skill advantage was demonstrated. "
           "Observed weather/coastal-level proxies did not consistently improve direct forecasts. "
           "M10.3.4 validation-selected convex mixtures retain persistence when complexity does not help.",
           "","| Concept | Policy | Scope | n | MAE | Persistence MAE |","|---|---|---|---:|---:|---:|"]
    for r in scores:
        if r["site_id"]=="all_sites":
            lines.append(f"| {r['concept']} | {r['policy']} | {r['scope']} | {r['n']} | {r['mae']:.4f} | {r['persistence_mae']:.4f} |")
    lines+=["","The adapted weather+level salinity mixture is an exploratory candidate, not a selected deployment policy. "
            "No test-based automatic selection is performed. Next: independent region/season replication, "
            "particularly Biscayne Bay; verify exact sensor depths, hydrological connectivity and forcing provenance.",
            "","See [lineage](manifest.json), [station edges](station_edges.csv), [regional residual edges](residual_edges.csv) "
            "and [gate weights](mixture_weights.csv). The original M9 evidence atlas remains immutable."]
    if bundle is not None:
        lines=["# Regional research evidence atlas","",f"Region: {router.cohort['region_screen']}. Frozen M10 protocol; independent geographic replication, retrospective only.","",f"Regional holdout folds: {len(router.folds)}. Station-local evidence retained regardless of regional readiness.","","| Concept | Policy | Scope | n | MAE | Persistence MAE |","|---|---|---|---:|---:|---:|"]+[line for line in lines if line.startswith("| ") and not line.startswith("| Concept")]
        lines+=["","No best policy selected from these test results.","","[Offline HTML atlas](atlas.html) · [Registry](expert_registry.csv) · [Matched policy evidence](paired_policy_evidence.csv)"]
    (out/"INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    report["outputs_sha256"]["INDEX.md"]=sha(out/"INDEX.md")
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path)
    p.add_argument("--verify-raw",action="store_true")
    p.add_argument("--query",nargs=3,metavar=("SITE","DATE","CONCEPT"))
    p.add_argument("--policy",default="persistence")
    p.add_argument("--scope",default="unforced")
    p.add_argument("--region")
    p.add_argument("--expert-id")
    a=p.parse_args()
    if bool(a.out)==bool(a.query):
        p.error("choose --out or --query")
    if a.query:
        router,*_=context(a.verify_raw)
        print(json.dumps(router.infer(*a.query,a.policy,a.scope,a.expert_id,a.region),indent=2))
    else:
        r=run(a.out,a.verify_raw)
        print(f"{r['n_registry_entries']} registry entries; {r['n_route_replay_rows']} replayed predictions; "
              f"{r['n_regional_holdout_folds']} regional folds; see {a.out/'INDEX.md'}")


if __name__=="__main__":
    main()
