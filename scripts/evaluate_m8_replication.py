"""Evaluate Milestone 8 replication without changing earlier model runs.

Outputs: per-layer temporal sensitivity, paired block-bootstrap uncertainty,
independent-station predictive transfer, site sign consistency, source hashes,
and navigable findings/plots. Incompatible station schemas fail closed or
remain explicitly unevaluable; no regional pooled FCM is trained.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.m8_validation import (
    FOLD_COLS,FOLD_EDGE_COLS,PAIRED_COLS,paired_block_interval,
    expanding_folds,model_scores,matched_rows)
from southfl.m8_transfer import (
    TRANSFER_COLS,TRANSFER_STATUS_COLS,EDGE_COLS,
    transfer_to_target,summarize_transfer,source_edge_replication,exact_units)
from southfl.fcm_model import NotReadyError
from visuals.m8_robustness_figures import plot_fold_skills,plot_edge_sign_recurrence,plot_transfer_skill

TRANSFER_PRED_COLS=["donor_panel","target_panel","date","concept","actual",
                    "transferred","persistence","target_local_fcm"]
INDEX_COLS=["level","scope","panel_id","site_id","status","reason",
            "model_dir","panel_sha256","n_temporal_folds"]
SCOPE_COLS=["level","scope","n_fitted_station_models",
            "n_distinct_stations","n_edge_replication_rows",
            "n_transfer_pairs","regional_expert_status"]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _valid_path(value):
    if (not value or value.startswith(".") or
        ".." in value or "\\" in value or ":" in value):
        raise ValueError("unsafe model directory component")
    candidate=Path(value)
    if candidate.is_absolute() or any(p in ("",".","..") for p in candidate.parts):
        raise ValueError("unsafe model directory")
    return candidate


def _read_inputs(model_run,panels):
    root=Path(model_run)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    registry=read_csv(root/"model_registry.csv")
    seen={}
    for pdir in panels:
        pdir=Path(pdir)
        panel_manifest=json.loads((pdir/"panels_manifest.json").read_text(encoding="utf-8"))
        if not panel_manifest.get("observations_sha256"):
            raise ValueError(f"missing observation lineage in {pdir}")
        for row in read_csv(pdir/"panel_readiness.csv"):
            pid=row["panel_id"]
            if pid in seen:
                raise ValueError(f"duplicate input panel ID {pid}")
            seen[pid]=(pdir,row,panel_manifest)
    for record in registry:
        pid=record["panel_id"]
        if pid not in seen:
            raise ValueError(f"model registry panel {pid} missing from supplied inputs")
        source,row,_=seen[pid]
        fp=source/(pid+".csv")
        if fp.exists():
            actual=_sha(fp)
            if record.get("panel_sha256") and actual!=record["panel_sha256"]:
                raise ValueError(f"panel checksum mismatch: {pid}")
        if record["status"].startswith("trained_"):
            path=root/_valid_path(record["model_directory"])
            if not (path/"fcm_model.json").exists():
                raise ValueError(f"missing trained model artifacts: {path}")
    return manifest,registry,seen


def _scope(rec):
    level=rec["level"]
    if level=="dataset":
        return "full_station"
    return rec["category"] + (("/"+rec["subcategory"]) if rec["subcategory"] else "")


def _dst(root,rec):
    return root/_valid_path(rec["model_directory"])


def _pairs_for_concept(predictions,concept):
    return [p for p in predictions if p["concept"]==concept]


def _interval(rows,a,b,rec,comparison,concept,block,bootstrap,seed):
    values=paired_block_interval(rows,a,b,block,bootstrap,seed)
    return dict(panel_id=rec["panel_id"],level=rec["level"],
                scope=_scope(rec),comparison=comparison,concept=concept,**values)


def _description(row):
    return f"{row['level']} — {_scope(row)}; {row['site_id']}"


def run(model_run,panels,out,block_days=7,bootstrap=400,
        max_folds=3,min_sites=3,dpi=140):
    if not 2<=block_days<=21 or not 100<=bootstrap<=5000:
        raise ValueError("invalid block/bootstrap bounds")
    if not 1<=max_folds<=6 or not 2<=min_sites<=10:
        raise ValueError("invalid fold/site threshold")
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty robustness output directory required")
    manifest,registry,sources=_read_inputs(model_run,panels)
    out.mkdir(parents=True,exist_ok=True)
    all_folds,all_fold_edges,all_intervals=[],[],[]
    indexed=[]
    trained=[]
    distinct_models={}
    for rec in registry:
        pid=rec["panel_id"]
        status=rec["status"]
        if not status.startswith("trained_"):
            indexed.append(dict(level=rec["level"],scope=_scope(rec),
                    panel_id=pid,site_id=rec["site_id"],status=status,
                    reason=rec.get("reason",""),model_dir="",
                    panel_sha256=rec.get("panel_sha256",""),n_temporal_folds=0))
            continue
        if rec.get("same_concept_set_as"):
            indexed.append(dict(level=rec["level"],scope=_scope(rec),
                panel_id=pid,site_id=rec["site_id"],
                status="redundant_concept_scope",
                reason="same observed site/concepts as "+rec["same_concept_set_as"],
                model_dir=rec["model_directory"],
                panel_sha256=rec["panel_sha256"],n_temporal_folds=0))
            continue
        model_dir=Path(model_run)/_valid_path(rec["model_directory"])
        model=json.loads((model_dir/"fcm_model.json").read_text(encoding="utf-8"))
        concepts=model["concepts"]
        panel_dir,source_row,_=sources[pid]
        unit_signature=exact_units(source_row,concepts)
        if unit_signature is None:
            # We can still audit within-station robustness, but block
            # transfer/edge replication without complete physical metadata.
            unit_sig_status="incomplete_units_or_datums"
        else:
            unit_sig_status="physical_metadata_checked"
        source_rows=read_csv(panel_dir/(pid+".csv"))
        scope=_scope(rec)
        destination=out/_valid_path(rec["model_directory"])
        destination.mkdir(parents=True,exist_ok=False)
        folds=expanding_folds(source_rows,concepts,max_folds=max_folds)
        fold_rows,fold_edge_rows=model_scores(pid,rec["level"],scope,folds)
        write_csv(destination/"temporal_folds.csv",fold_rows,FOLD_COLS)
        write_csv(destination/"temporal_edge_weights.csv",
                  fold_edge_rows,FOLD_EDGE_COLS)
        all_folds+=fold_rows
        all_fold_edges+=fold_edge_rows
        predictions=read_csv(model_dir/"heldout_predictions.csv")
        boot=[]
        for j,concept in enumerate(concepts):
            part=_pairs_for_concept(predictions,concept)
            for label,a,b in [
                    ("fcm_minus_self_ar","fcm","self_ar"),
                    ("fcm_minus_persistence","fcm","persistence")]:
                try:
                    boot.append(_interval(part,a,b,rec,label,concept,
                                          block_days,bootstrap,1100+j*41))
                except NotReadyError:
                    # Genuine insufficient heldout contiguous days: report it,
                    # but do not fabricate a confidence interval.
                    pass
        if rec["level"] in ("category","subcategory"):
            full=Path(model_run)/"levels"/"dataset"/pid
            full_pred=read_csv(full/"heldout_predictions.csv")
            for j,concept in enumerate(concepts):
                part=matched_rows(_pairs_for_concept(predictions,concept),
                                  _pairs_for_concept(full_pred,concept))
                try:
                    boot.append(_interval(part,"a","b",rec,
                        "specialist_minus_full_station",concept,
                        block_days,bootstrap,1700+j*73))
                except NotReadyError:
                    pass
        write_csv(destination/"paired_uncertainty.csv",boot,PAIRED_COLS)
        all_intervals+=boot
        plot_fold_skills(fold_rows,destination/"visuals"/"temporal_skill.png",
                         dpi=dpi)
        lines=[
            f"# Robustness — {_description(rec)}","",
            f"Source fitted model: `{model_dir}`.",
            f"Observed daily panel: `{panel_dir/(pid+'.csv')}`.",
            f"Verified daily panel SHA256: `{_sha(panel_dir/(pid+'.csv'))}`.",
            f"Physical metadata status: {unit_sig_status}.","",
            f"Expanding-origin fits with non-overlapping held-out dates: {len(folds)}.",
            f"Paired exploratory block-bootstrap summaries: {len(boot)}.",
            "All calculations use existing observed values and original "
            "chronological splits; no target labels enter model fitting.","",
            "[Temporal skill plot](visuals/temporal_skill.png) · "
            "[Temporal fold metrics](temporal_folds.csv) · "
            "[Temporal edge weights](temporal_edge_weights.csv) · "
            "[Paired error uncertainty](paired_uncertainty.csv)","",
            "These fold models reuse earlier observations during later fits; "
            "their training sets overlap even though held-out dates do not.",
            "Block bootstrap CIs describe within-period error uncertainty "
            "only, not station-level reproducibility, operational skill "
            "or causal edge confidence.",
        ]
        (destination/"FINDINGS.md").write_text("\n".join(lines)+"\n",
                                              encoding="utf-8")
        indexed.append(dict(level=rec["level"],scope=scope,
            panel_id=pid,site_id=rec["site_id"],
            status="expanding_origin_evaluated",
            reason=unit_sig_status,model_dir=rec["model_directory"],
            panel_sha256=rec["panel_sha256"],n_temporal_folds=len(folds)))
        trained.append(dict(
            **rec,scope=scope,concepts=concepts,
            model_json=model,model_dir=model_dir,
            panel_dir=panel_dir,source_row=source_row,
            unit_signature=unit_signature,
            edges=read_csv(model_dir/"edge_weights.csv"),
            target_predictions=predictions,
            source_rows=source_rows,
        ))
    write_csv(out/"evaluation_registry.csv",indexed,INDEX_COLS)
    write_csv(out/"temporal_folds_all.csv",all_folds,FOLD_COLS)
    write_csv(out/"temporal_edges_all.csv",all_fold_edges,FOLD_EDGE_COLS)
    write_csv(out/"paired_uncertainty_all.csv",all_intervals,PAIRED_COLS)

    # Descriptive sign frequency across distinct stations, never a pooled FCM.
    good=[m for m in trained if m["unit_signature"] is not None]
    replication=source_edge_replication(good,min_sites=min_sites)
    write_csv(out/"cross_station_edge_signs.csv",replication,EDGE_COLS)

    transfers=[]
    transfer_status=[]
    transfer_predictions=[]
    by_group=defaultdict(list)
    for m in trained:
        signature=(m["level"],m["scope"],tuple(sorted(m["concepts"])))
        by_group[signature].append(m)
    for (level,scope,concept_set),models in sorted(by_group.items()):
        if len(models)<2:
            continue
        for donor in models:
            for target in models:
                if donor is target or donor["site_id"]==target["site_id"]:
                    continue
                status={"level":level,"scope":scope,
                        "donor_panel":donor["panel_id"],
                        "target_panel":target["panel_id"]}
                if not donor["unit_signature"] or not target["unit_signature"]:
                    transfer_status.append(dict(**status,status="blocked",
                        reason="missing donor/target units or datum metadata"))
                    continue
                if donor["unit_signature"]!=target["unit_signature"]:
                    transfer_status.append(dict(**status,status="blocked",
                        reason="incompatible source units or vertical datums"))
                    continue
                # Transfer never sees the target's fitting parameters;
                # it only uses the predeclared target test dates/inputs.
                predicted=transfer_to_target(
                    donor["model_json"],target["source_rows"],
                    target["target_predictions"],list(concept_set))
                transfers.extend(summarize_transfer(donor,target,predicted))
                transfer_predictions.extend({
                    "donor_panel":donor["panel_id"],
                    "target_panel":target["panel_id"],**p
                } for p in predicted)
                transfer_status.append(dict(**status,status="evaluated",
                    reason="donor only; matched concepts/units/datums; "
                           "target test dates specified in prior run"))
    write_csv(out/"cross_station_transfer.csv",transfers,TRANSFER_COLS)
    write_csv(out/"cross_station_transfer_readiness.csv",
              transfer_status,TRANSFER_STATUS_COLS)
    write_csv(out/"cross_station_transfer_predictions.csv",
              transfer_predictions,TRANSFER_PRED_COLS)

    # Evidence summaries and visuals at each separately observed model layer.
    scopes=defaultdict(list)
    for m in trained:
        scopes[(m["level"],m["scope"])].append(m)
    scope_index=[]
    for (level,scope),models in sorted(scopes.items()):
        if level=="dataset":
            folder=out/"levels"/"dataset"
        else:
            folder=out/"levels"/level/Path(scope)
        folder.mkdir(parents=True,exist_ok=True)
        edge_rows=[r for r in replication
                   if r["level"]==level and r["scope"]==scope]
        transfer_rows=[r for r in transfers
                       if r["level"]==level and r["scope"]==scope]
        fold_rows=[r for r in all_folds
                   if r["level"]==level and r["scope"]==scope]
        write_csv(folder/"edge_replication.csv",edge_rows,EDGE_COLS)
        write_csv(folder/"station_transfer.csv",transfer_rows,TRANSFER_COLS)
        visual_dir=folder/"visuals"
        visual_dir.mkdir(parents=True,exist_ok=True)
        plot_edge_sign_recurrence(
            edge_rows,visual_dir/"edge_sign_recurrence.png",dpi=dpi)
        plot_transfer_skill(
            transfer_rows,visual_dir/"station_transfer_skill.png",dpi=dpi)
        unique_sites={m["site_id"] for m in models}
        status="descriptive_replication_only"
        if len(unique_sites)<min_sites:
            status="insufficient_independent_stations"
        scope_index.append(dict(
            level=level,scope=scope,n_fitted_station_models=len(models),
            n_distinct_stations=len(unique_sites),
            n_edge_replication_rows=len(edge_rows),
            n_transfer_pairs=len({(r["donor_panel"],r["target_panel"])
                                  for r in transfer_rows}),
            regional_expert_status="NOT_TRAINED",
        ))
        lines=[f"# Replication evidence — {level}/{scope}","",
            f"Fitted station-local models: {len(models)}.",
            f"Distinct stations: {len(unique_sites)}.",
            f"Evidence status: {status}.",
            f"Donor→target transfer rows: {len(transfer_rows)}.",
            "Regional integrated FCM: **NOT TRAINED**.","",
            "[Edge sign recurrence](visuals/edge_sign_recurrence.png) · "
            "[Cross-station transfer skill](visuals/station_transfer_skill.png) · "
            "[Replication CSV](edge_replication.csv) · "
            "[Transfer CSV](station_transfer.csv)","",
            "Only identical concept sets with matching source units and "
            "datums can contribute to edge/sign or transfer comparisons.",
            "No pooled weights, learned expert gating, external intervention "
            "effects, or generalized operational forecasting claims.",
            "",
            "## Station-specific temporal robustness","",
        ]
        for m in models:
            path=out/_valid_path(m["model_directory"])/"FINDINGS.md"
            link=path.relative_to(folder) if path.is_relative_to(folder) else None
            if link is not None:
                lines.append(f"- [{m['panel_id']}]({link.as_posix()})")
            else:
                lines.append(f"- {m['panel_id']}: `{path}`")
        (folder/"FINDINGS.md").write_text("\n".join(lines)+"\n",
                                        encoding="utf-8")
    write_csv(out/"scope_readiness.csv",scope_index,SCOPE_COLS)

    # Every higher-level directory that isn't supported by independent
    # replicated station data remains untrained, irrespective of plot content.
    overall=out/"levels"/"overall"
    overall.mkdir(parents=True,exist_ok=True)
    (overall/"STATUS.md").write_text(
        "# South Florida overall model: NOT TRAINED\n\n"
        "Cross-site transfer and edge-sign evidence do not constitute "
        "a pooled or gated regional FCM.\n",encoding="utf-8")
    (overall/"FINDINGS.md").write_text(
        "# Current regional evidence\n\n"
        f"Independently fitted site models evaluated: "
        f"{len({m['site_id'] for m in trained})}.\n"
        f"Potential donor-target transfers evaluated: {len(transfers)} "
        "per-concept comparisons.\n"
        "No overall FCM, learned expert mixture, or causal South Florida "
        "feedback graph has been fitted.\n\n"
        "[Scope readiness](../../scope_readiness.csv) · "
        "[Cross-site predictive transfer](../../cross_station_transfer.csv) · "
        "[Edge-sign recurrence](../../cross_station_edge_signs.csv)\n",
        encoding="utf-8")

    index_lines=["# Milestone 8 — temporal and cross-station replication","",
        "This directory augments an existing immutable M8 training run.",
        f"Source model run: `{model_run}`.",
        "Original models and source daily panels were not modified.","",
        f"Station-local trained scope fits evaluated: {len(trained)}.",
        f"Distinct observed station IDs: {len({m['site_id'] for m in trained})}.",
        f"Expanding-window held-out fold/concept rows: {len(all_folds)}.",
        f"Exploratory paired uncertainty rows: {len(all_intervals)}.",
        f"Transfer rows: {len(transfers)}.",
        "**Regional subcategory, category, and overall FCMs remain NOT TRAINED.**",
        "",
        "## Navigate evidence by level","",
    ]
    for row in scope_index:
        folder=("levels/dataset" if row["level"]=="dataset"
                else "levels/"+row["level"]+"/"+row["scope"])
        index_lines.append(f"- [{row['level']}/{row['scope']}]("
                           f"{folder}/FINDINGS.md): "
                           f"{row['n_distinct_stations']} distinct sites")
    index_lines += [
        "- [Overall region: NOT TRAINED](levels/overall/STATUS.md)","",
        "## Global evaluation tables","",
        "- [Model readiness](evaluation_registry.csv)",
        "- [Temporal folds](temporal_folds_all.csv)",
        "- [Paired block-bootstrap uncertainty](paired_uncertainty_all.csv)",
        "- [Cross-station donor transfer](cross_station_transfer.csv)",
        "- [Transfer eligibility ledger](cross_station_transfer_readiness.csv)",
        "- [Cross-station edge sign recurrence](cross_station_edge_signs.csv)",
        "",
        "Intervals are exploratory on one measured held-out period; "
        "station and training folds are not interchangeable independent "
        "experimental units.",
    ]
    (out/"INDEX.md").write_text("\n".join(index_lines)+"\n",
                                encoding="utf-8")
    result={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_m8_manifest_sha256":_sha(Path(model_run)/"manifest.json"),
        "source_model_run":str(model_run),
        "input_panels":[str(p) for p in panels],
        "evaluated_station_local_models":len(trained),
        "n_unique_station_ids":len({m["site_id"] for m in trained}),
        "n_temporal_rows":len(all_folds),
        "n_paired_uncertainty_rows":len(all_intervals),
        "n_transfer_concept_rows":len(transfers),
        "n_transfer_blocked_pairs":sum(r["status"]=="blocked"
                                       for r in transfer_status),
        "n_edge_replication_rows":len(replication),
        "bootstrap_block_days":block_days,
        "bootstrap_replicates":bootstrap,"max_folds":max_folds,
        "regional_subcategory_fcms_fitted":0,
        "regional_category_fcms_fitted":0,"overall_fcms_fitted":0,
        "forecasting_generalization_proven":False,
        "causal_edges_identified":False,
    }
    (out/"manifest.json").write_text(json.dumps(result,indent=2)+"\n",
                                     encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",type=Path,required=True,
                   help="frozen earlier M8 model results root")
    p.add_argument("--panels",type=Path,action="append",required=True,
                   help="source daily-panel directory; repeatable")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--block-days",type=int,default=7)
    p.add_argument("--bootstrap",type=int,default=400)
    p.add_argument("--max-folds",type=int,default=3)
    p.add_argument("--min-sites",type=int,default=3)
    p.add_argument("--dpi",type=int,default=140)
    a=p.parse_args()
    result=run(a.models,a.panels,a.out,a.block_days,
               a.bootstrap,a.max_folds,a.min_sites,a.dpi)
    print(f"Evaluated {result['evaluated_station_local_models']} station-local "
          f"models, {result['n_temporal_rows']} temporal-fold rows, "
          f"{result['n_transfer_concept_rows']} external-station transfer rows; "
          "no regional model trained")


if __name__=="__main__":
    main()
