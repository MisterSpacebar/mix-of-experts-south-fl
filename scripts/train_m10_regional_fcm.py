"""Fit first regional water-quality FCM with predeclared spatial/temporal folds."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from statistics import mean

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.temporal_integrity import verify_historical_hash
from southfl.regional_fcm import (CONCEPTS, MODELS, BASELINES, split,
                                  evaluate_fold, metrics, paired_block)
from scripts.audit_m10_regional_cohort import DEFAULT_SNAPSHOTS, run as audit_run

ROOT=Path("data/m10")
COHORT=ROOT/"cohort_expanded_v1"
SNAPSHOTS=DEFAULT_SNAPSHOTS+[(ROOT/f"daily_{b}",ROOT/f"history_{b}",ROOT/f"identity_{b}")
                             for b in ("03","04","05","06")]
UNITS={"salinity":"ppt","water_temperature":"degC"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def normalize(p):
    return Path(str(p).replace("\\","/"))


def indexed(rows,key):
    result={}
    for row in rows:
        if row[key] in result:
            raise ValueError(f"duplicate {key}")
        result[row[key]]=row
    return result


def load_cohort(cohort, verify_raw=False, config=None):
    """Re-audit source identities/coverage; verify original recorded input hashes."""
    cohort=Path(cohort)
    snapshots_config=SNAPSHOTS if config is None else config["snapshots"]
    manifest=load_json(cohort/"manifest.json")
    if (manifest["temporal_metadata_screen_pass"] is not True or
        manifest["raw_bytes_verified"] is not True or
        manifest["concepts"]!=list(CONCEPTS) or manifest["regional_fcms_trained"]!=0):
        raise ValueError("requires predeclared, raw-verified regional cohort")
    snapshots={str(normalize(k)):v for k,v in manifest["snapshots"].items()}
    if set(snapshots)!={str(d) for d,_,_ in snapshots_config}:
        raise ValueError("unexpected cohort source roots")
    lineage={}
    for daily,history,identity in snapshots_config:
        record=snapshots[str(daily)]
        paths={"history_manifest":history/"history_manifest.json",
               "panels_manifest":daily/"panels_manifest.json",
               "identity_manifest":identity/"identity_manifest.json",
               "identity_audit":identity/"series_identity_audit.csv",
               "panel_readiness":daily/"panel_readiness.csv"}
        lineage[str(daily)]={k:verify_historical_hash(p,record[k]) for k,p in paths.items()}
        if load_json(paths["history_manifest"])["observations_sha256"]!=record["raw_sha256_recorded"]:
            raise ValueError("raw digest changed since cohort audit")
        if record.get("raw_bytes_verified") is not True:
            raise ValueError("source not raw-verified in cohort")
    for path,digest in manifest["coordinate_sources"].items():
        verify_historical_hash(normalize(path),digest)
    # Rerun the existing conservative screen into disposable scratch; do
    # not trust a manually changed eligible station list or fold table.
    with tempfile.TemporaryDirectory() as tmp:
        check=Path(tmp)/"audit"
        fresh=audit_run(snapshots_config,check,region=manifest["region_screen"],
                        **({} if config is None else dict(assignments=config["coordinates"],shortlist=config["coordinates"],min_sites=config["min_sites"],screen_insufficient=True)),
                        start=manifest["start"],end=manifest["end"],verify_raw=verify_raw)
        keys=("eligible_sites","concepts","common_days","common_transitions",
              "longest_common_stretch","n_observed_sites","n_spatial_folds",
              "train_target_date_end","validation_target_date_end","temporal_metadata_screen_pass")
        if any(fresh[k]!=manifest[k] for k in keys):
            raise ValueError("cohort does not reproduce from source evidence")
        for f in ("site_split_counts.csv","spatial_fold_plan.csv"):
            if read_csv(check/f)!=read_csv(cohort/f):
                raise ValueError("predeclared fold/split table differs from source")
        stations=indexed(read_csv(cohort/"station_cohort.csv"),"site_id")
        now=indexed(read_csv(check/"station_cohort.csv"),"site_id")
        if stations.keys()!=now.keys():
            raise ValueError("station registry differs from source")
        for s,r in stations.items():
            p=normalize(r["daily_path"])
            if p!=normalize(now[s]["daily_path"]):
                raise ValueError("daily source path differs from audit")
            lineage[s]=verify_historical_hash(p,r["daily_sha256"])
            for k in ("cohort_status","sensor_positions","concepts","primary_region",
                      "common_window_days","common_window_pairs"):
                if r[k]!=now[s][k]:
                    raise ValueError("station evidence changed")
    splits={}
    counts=indexed(read_csv(cohort/"site_split_counts.csv"),"site_id")
    folds=indexed(read_csv(cohort/"spatial_fold_plan.csv"),"heldout_site")
    sites=manifest["eligible_sites"]
    if len(sites)<3 or len(sites)!=len(set(sites)) or set(sites)!=set(counts) or set(sites)!=set(folds):
        raise ValueError("invalid eligible station set")
    for s in sites:
        splits[s]=split(read_csv(normalize(stations[s]["daily_path"])),manifest["start"],
                        manifest["train_target_date_end"],manifest["validation_target_date_end"],manifest["end"])
        if any(len(v)!=int(counts[s][k]) for k,v in splits[s].items()):
            raise ValueError("split counts changed")
        if any(len(splits[s][k])<n for k,n in (("train",35),("validation",15),("test",15))):
            raise ValueError("insufficient local or donor split")
    for s,f in folds.items():
        donors=set(sites)-{s}
        if (set(f["donor_sites"].split(";"))!=donors or f["temporal_screen_pass"]!="True"
            or int(f["donor_train_pairs"])!=sum(len(splits[d]["train"]) for d in donors)
            or int(f["donor_validation_pairs"])!=sum(len(splits[d]["validation"]) for d in donors)
            or int(f["target_test_pairs"])!=len(splits[s]["test"])):
            raise ValueError("fold does not match independent donor/target splits")
    dates=[tuple(p[0] for p in splits[s]["test"]) for s in sites]
    if config is None:
        if any(d!=dates[0] for d in dates):
            raise ValueError("this first experiment requires identical observed test dates")
    else:
        # Fixed intersection of observed target dates, never outcome-based.
        common=set.intersection(*(set(d) for d in dates))
        if len(common)<15:
            raise ValueError("insufficient shared observed test dates")
        for s in sites:
            splits[s]["test"]=[p for p in splits[s]["test"] if p[0] in common]
    return manifest,splits,lineage


def run(cohort,out,verify_raw=False,draws=2000,config=None):
    cohort,out=Path(cohort),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty model output required")
    if not 100<=draws<=20000:
        raise ValueError("invalid bootstrap draws")
    manifest,splits,lineage=load_cohort(cohort,verify_raw,config)
    fitted,predictions,edges={},[],[]
    for s in sorted(splits):
        models,rows=evaluate_fold(splits,s)
        fitted[s]=models
        predictions.extend(rows)
        for model in ("regional_fcm","target_local_fcm"):
            for j,target in enumerate(CONCEPTS):
                for i,source in enumerate(CONCEPTS):
                    edges.append(dict(heldout_site=s,model=model,source_concept=source,
                                      target_concept=target,weight=models[model]["coefficients_target_rows"][j][i+1],
                                      interpretation="predictive coefficient, not transport or causality"))
    scores=metrics(predictions)
    for r in scores:
        r["unit"]=UNITS[r["concept"]]
    comparisons=[]
    for site in sorted(splits)+["all_sites"]:
        for c in CONCEPTS:
            selected=[r for r in predictions if r["concept"]==c and
                      (site=="all_sites" or r["site_id"]==site)]
            for baseline in BASELINES:
                for block in (3,7,14):
                    try:
                        estimate=paired_block(selected,baseline,block,draws)
                    except ValueError:
                        if config is None:
                            raise
                        from statistics import mean
                        estimate=dict(delta_mae=mean(abs(r["regional_fcm"]-r["actual"])-abs(r[baseline]-r["actual"]) for r in selected),ci_low="",ci_high="",n_dates=len({r["date"] for r in selected}),n_sites=len({r["site_id"] for r in selected}),block_days=block,n_available_blocks=0,draws=0,seed=20261126)
                    comparisons.append(dict(site_id=site,concept=c,baseline=baseline,
                                            unit=UNITS[c],**estimate))
    out.mkdir(parents=True,exist_ok=True)
    for filename,rows in (("predictions.csv",predictions),("metrics.csv",scores),
                          ("paired_comparisons.csv",comparisons),("edge_weights.csv",edges)):
        write_csv(out/filename,rows,list(rows[0]))
    (out/"fold_models.json").write_text(json.dumps(fitted,indent=2)+"\n",encoding="utf-8")
    report=dict(cohort=str(cohort),cohort_files_sha256={f:sha(cohort/f) for f in
                ("manifest.json","station_cohort.csv","site_split_counts.csv","spatial_fold_plan.csv")},
                source_lineage=lineage,raw_bytes_reverified_this_run=verify_raw,
                sites=sorted(splits),concepts=CONCEPTS,
                train_target_date_end=manifest["train_target_date_end"],
                validation_target_date_end=manifest["validation_target_date_end"],
                n_spatial_folds=len(splits),n_regional_fcm_fold_fits=len(splits),
                n_target_local_fcm_fold_fits=len(splits),n_prediction_targets=len(predictions),
                n_models_compared=len(MODELS),n_test_dates_per_site=len(next(iter(splits.values()))["test"]),
                bootstrap_draws=draws,bootstrap_block_days=[3,7,14],
                bootstrap_scope="paired date-synchronous conditional temporal uncertainty; not independent site inference",
                model_selection_on_test=False,regional_transport_model_trained=False,
                deployed_model_trained=False,mixture_gate_trained=False,
                external_forcing_included=False,hydrological_connectivity_verified=False,
                exact_sensor_depth_verified=False,
                outputs_sha256={f:sha(out/f) for f in ("predictions.csv","metrics.csv",
                    "paired_comparisons.csv","edge_weights.csv","fold_models.json")})
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# M10.3.1 — shared regional water-quality FCM" if config is None else "# M11 — frozen shared regional water-quality FCM","",
           f"{len(splits)} spatial folds; {len(predictions)} matched station-date-concept targets. No deployed model or spatial transport fit.","",
           "## Aggregate held-out native-unit MAE","",
           "| Concept | Persistence | Pooled self-AR | Pooled ridge | Regional FCM | Target-local FCM |",
           "|---|---:|---:|---:|---:|---:|"]
    for c in CONCEPTS:
        vals={r["model"]:r["mae"] for r in scores if r["site_id"]=="all_sites" and r["concept"]==c}
        lines.append("| "+c+" ("+UNITS[c]+") | "+" | ".join(f"{vals[m]:.4f}" for m in MODELS)+" |")
    lines+=["","## Regional FCM minus baseline MAE (7-day paired blocks)","",
            "Negative favors regional FCM; conditional temporal intervals, not new-site inference.","",
            "| Concept | Baseline | Delta | 95% interval |","|---|---|---:|---:|"]
    for r in comparisons:
        if r["site_id"]=="all_sites" and r["block_days"]==7:
            ci="not estimable" if r["ci_low"]=="" else f"[{r['ci_low']:.4f}, {r['ci_high']:.4f}]"
            lines.append(f"| {r['concept']} | {r['baseline']} | {r['delta_mae']:.4f} | {ci} |")
    lines+=["","- [Per-site and aggregate metrics](metrics.csv)",
            "- [Matched predictions and clipping diagnostics](predictions.csv)",
            "- [Block-length sensitivity](paired_comparisons.csv)",
            "- [Fold parameters and donor-only scalers](fold_models.json)",
            "- [FCM edges](edge_weights.csv) · [Lineage](manifest.json)","",
            "Target-local FCM uses target history and is an adaptation reference, not zero-shot. "
            "Previous-day target observations are available at issue time. These data have already "
            been examined descriptively in M10; the M11 protocol is predeclared. Results are retrospective, not prospective confirmation. "
            "Exact sensor depth, common forcing and connectivity remain unverified."]
    (out/"INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort",type=Path,default=COHORT)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-raw",action="store_true")
    p.add_argument("--draws",type=int,default=2000)
    a=p.parse_args()
    report=run(a.cohort,a.out,a.verify_raw,a.draws)
    print(f"{report['n_spatial_folds']} spatial folds; {report['n_prediction_targets']} matched targets; "
          f"{report['n_regional_fcm_fold_fits']} regional FCM fold fits. See {a.out/'INDEX.md'}")


if __name__=="__main__":
    main()
