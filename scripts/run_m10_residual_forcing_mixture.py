"""M10.3.2–4: activation ablation, residual, forcing and expert blending."""
import argparse
import json
import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path
from statistics import mean

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.net import write_csv
from southfl.audit import read_csv
from southfl.temporal_integrity import verify_historical_hash
from southfl.m10_forcing import acquire,load,FEATURES,sha
from southfl.residual_fcm import fold
from southfl.regional_fcm import paired_block
from scripts.train_m10_regional_fcm import COHORT,load_cohort

BASE=Path("data/m10/regional_fcm_v1")
UNITS={"salinity":"ppt","water_temperature":"degC"}


def verify_original(splits,base):
    m=json.loads((base/"manifest.json").read_text(encoding="utf-8"))
    for f,h in m["outputs_sha256"].items():
        verify_historical_hash(base/f,h)
    rows=read_csv(base/"predictions.csv")
    expected={(s,d,c):(x[j],y[j]) for s,v in splits.items()
              for d,x,y in v["test"] for j,c in enumerate(UNITS)}
    if len(rows)!=len(expected):
        raise ValueError("original prediction count differs")
    seen=set()
    for r in rows:
        k=r["site_id"],r["date"],r["concept"]
        if k in seen or k not in expected or expected[k]!=(float(r["previous"]),float(r["actual"])):
            raise ValueError("original target differs")
        seen.add(k)
    return { (r["site_id"],r["date"],r["concept"]):r for r in rows }


def summarize(rows):
    by=defaultdict(list)
    for r in rows:
        by[r["site_id"],r["concept"],r["model"]].append(r)
        by["all_sites",r["concept"],r["model"]].append(r)
    scores=[]; comparisons=[]
    for (s,c,m),rs in sorted(by.items()):
        errors=[r["prediction"]-r["actual"] for r in rs]
        pe=[r["previous"]-r["actual"] for r in rs]
        scores.append(dict(site_id=s,concept=c,model=m,unit=UNITS[c],n=len(rs),
                           n_sites=len({r["site_id"] for r in rs}),mae=mean(map(abs,errors)),
                           rmse=sqrt(mean(e*e for e in errors)),bias=mean(errors),
                           matched_persistence_mae=mean(map(abs,pe)),
                           delta_vs_persistence=mean(abs(e)-abs(p) for e,p in zip(errors,pe))))
        baselines=["persistence"]
        if m.endswith("_forced"):
            baselines.append(m.removesuffix("_forced")+"_matched_unforced")
        if m.endswith("_fallback"):
            baselines.append("adapted_blend" if "_adapted_" in m else "zero_shot_blend")
        if m in ("residual_regional","residual_unbounded"):
            baselines.append("level_activation_ablation")
        if m=="level_activation_ablation":
            baselines.append("level_bounded")
        if m=="adapted_blend":
            baselines+=["residual_local","residual_regional","zero_shot_blend"]
        if m=="zero_shot_blend":
            baselines.append("residual_regional")
        for b in baselines:
            if b==m:
                continue
            lookup={(r["site_id"],r["date"]):r for r in by.get((s,c,b),[])}
            pairs=[]
            for r in rs:
                k=r["site_id"],r["date"]
                if k in lookup:
                    q=lookup[k]
                    if q["actual"]!=r["actual"]:
                        raise ValueError("unmatched actuals")
                    pairs.append(dict(site_id=k[0],date=k[1],concept=c,actual=r["actual"],
                                      regional_fcm=r["prediction"],persistence=q["prediction"]))
            if not pairs:
                continue
            delta=mean(abs(r["regional_fcm"]-r["actual"])-abs(r["persistence"]-r["actual"]) for r in pairs)
            record=dict(site_id=s,concept=c,model=m,baseline=b,unit=UNITS[c],
                        n=len(pairs),n_sites=len({r["site_id"] for r in pairs}),delta_mae=delta,
                        ci_low="",ci_high="",interval_status="insufficient_matched_contiguous_dates")
            try:
                ci=paired_block(pairs,"persistence",block=7,draws=2000)
                record.update(ci_low=ci["ci_low"],ci_high=ci["ci_high"],
                              interval_status="conditional_date_block_7")
            except ValueError:
                pass
            comparisons.append(record)
    return scores,comparisons


def run(out,forcing_dir=None,verify_raw=False,cohort=COHORT,base=BASE):
    out,base=Path(out),Path(base)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty experiment output required")
    cohort_manifest,splits,lineage=load_cohort(cohort,verify_raw)
    original=verify_original(splits,base)
    forcing,forcing_manifest=load(forcing_dir) if forcing_dir else ({},{})
    models,rows={},[]
    for site in sorted(splits):
        model,rs=fold(splits,site,forcing,FEATURES if forcing_dir else {})
        models[site]=model
        rows.extend(rs)
    # Verify exact replay of v1, then preserve its other reference predictions.
    for r in rows:
        orig=original[r["site_id"],r["date"],r["concept"]]
        if r["model"]=="level_bounded" and abs(r["prediction"]-float(orig["regional_fcm"]))>1e-9:
            raise ValueError("activation ablation does not replay original FCM")
    for (s,d,c),r in original.items():
        for m in ("pooled_self_ar","pooled_ridge","target_local_fcm"):
            rows.append(dict(site_id=s,date=d,concept=c,model="v1_"+m,actual=float(r["actual"]),
                             previous=float(r["previous"]),prediction=float(r[m])))
    if len(rows)!=len({(r["site_id"],r["date"],r["concept"],r["model"]) for r in rows}):
        raise ValueError("duplicate model predictions")
    scores,comparisons=summarize(rows)
    out.mkdir(parents=True,exist_ok=True)
    for name,rs in (("predictions.csv",rows),("metrics.csv",scores),("paired_comparisons.csv",comparisons)):
        write_csv(out/name,rs,list(rs[0]))
    (out/"fold_models.json").write_text(json.dumps(models,indent=2)+"\n",encoding="utf-8")
    coverage=[]
    for site,m in models.items():
        for label,v in m["forcing"].items():
            coverage.append(dict(site_id=site,scope=label,status=v["status"],
                                 target_test_pairs=v["counts"]["target_test"],
                                 counts=json.dumps(v["counts"],sort_keys=True)))
    write_csv(out/"forcing_coverage.csv",coverage,["site_id","scope","status","target_test_pairs","counts"])
    report=dict(sites=sorted(splits),concepts=list(UNITS),n_folds=len(splits),
                n_reference_targets=len(original),n_prediction_rows=len(rows),
                source_lineage=lineage,cohort_manifest_sha256=sha(Path(cohort)/"manifest.json"),
                original_manifest_sha256=sha(base/"manifest.json"),
                forcing_manifest_sha256=sha(Path(forcing_dir)/"manifest.json") if forcing_dir else None,
                forcing_coverage=forcing_manifest.get("coverage",{}),
                forcing_fold_fits=sum(v["status"]=="fitted" for m in models.values() for v in m["forcing"].values()),
                raw_reverified=verify_raw,exploratory_reused_test_period=True,
                model_selection_on_test=False,deployed_model_trained=False,
                regional_transport_model_trained=False,as_issued_availability_verified=False,
                hydrological_connectivity_verified=False,
                exact_sensor_depth_verified=False,
                outputs_sha256={f:sha(out/f) for f in ("predictions.csv","metrics.csv","paired_comparisons.csv","fold_models.json","forcing_coverage.csv")})
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# M10.3.2–4 — exploratory residual, forcing and mixture experiments","",
           f"{len(splits)} spatial folds; {len(original)} original matched targets. Forcing fold fits: {report['forcing_fold_fits']}.",
           "Same previously inspected test season; no prospective confirmation or deployment.","",
           "| Concept | Model | Sites | n | MAE | Matched persistence MAE | Delta |",
           "|---|---|---:|---:|---:|---:|---:|"]
    for r in scores:
        if r["site_id"]=="all_sites":
            lines.append(f"| {r['concept']} | {r['model']} | {r['n_sites']} | {r['n']} | {r['mae']:.4f} | {r['matched_persistence_mae']:.4f} | {r['delta_vs_persistence']:.4f} |")
    lines+=["","Compare forced vs matched-unforced on exactly the same rows in paired_comparisons.csv.",
            "Different model coverage is not a fair unconditional ranking. Fallback policies are all-date within fitted folds.",
            "Seven-day intervals are conditional on the observed season/sites and omitted when synchronous blocks cannot cover the dates.",
            "Zero-shot blends use donor validation only; adapted blends use target historical validation.",
            "Weather and water levels are regional proxies, archive-based, not verified as-issued forecasts.","",
            "- [Metrics](metrics.csv) · [Matched comparisons](paired_comparisons.csv)",
            "- [Predictions](predictions.csv) · [Gate weights and fits](fold_models.json)",
            "- [Forcing coverage](forcing_coverage.csv) · [Lineage](manifest.json)"]
    (out/"INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--forcing",type=Path,help="Existing acquired forcing snapshot")
    p.add_argument("--acquire-forcing",type=Path,help="Acquire source snapshot first, then run all experiments")
    p.add_argument("--verify-raw",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.forcing and a.acquire_forcing:
        p.error("choose one forcing input")
    if a.out.exists() and any(a.out.iterdir()):
        p.error("new/empty experiment output required")
    if a.acquire_forcing:
        print(json.dumps(acquire(a.acquire_forcing),indent=2))
    r=run(a.out,a.forcing or a.acquire_forcing,a.verify_raw)
    print(f"{r['n_folds']} folds; {r['n_reference_targets']} original targets; {r['forcing_fold_fits']} forcing fold fits. See {a.out/'INDEX.md'}")


if __name__=="__main__":
    main()
