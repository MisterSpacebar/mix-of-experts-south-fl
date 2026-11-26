"""Milestone 8: run and browse newly fitted station-local FCM specialists.

Accept one or more already-verified observed-only daily panel directories.
Train a full dataset-level model AND separately fit a category- and
subcategory-restricted model where >=2 concepts are present. Every model
has chronological held-out results and source hashes.

This is NOT a spatially pooled category expert or an overall MoE. No
future observations, station averages, or fabricated links are used.
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
from southfl.fcm_model import fit_preview,NotReadyError,EVAL_COLS,EDGE_COLS
from southfl.fcm_figures import hindcast_svg
from southfl.m8_layers import concept_scopes,fit_scoped,compare_matched,COMPARISON_COLS,STATUS_COLS
from visuals.hierarchy import CATEGORIES
from visuals.network_svg import network_svg
from visuals.render import plot_baseline_comparison,plot_edge_weight_heatmap

PRED_COLS=["date","concept","actual","fcm","self_ar","persistence"]
ROLL_COLS=["step","concept","simulated_value"]
REGISTRY_COLS=STATUS_COLS+["n_train_pairs","n_validation_pairs","n_test_pairs","n_beating_self_ar","n_beating_persistence"]
FINDING_COLS=["panel_id","level","scope","concept","n_test_pairs","fcm_mae",
              "self_ar_mae","persistence_mae","skill_vs_self_ar",
              "skill_vs_persistence","note"]


def _safe(fragment):
    if not fragment or fragment.startswith(".") or any(
            x in fragment for x in ("/","\\","..",":")):
        raise ValueError(f"unsafe panel or hierarchy identifier: {fragment!r}")
    return fragment


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_index(directories):
    output={}
    for root in map(Path,directories):
        items=read_csv(root/"panel_readiness.csv")
        manifest_path=root/"panels_manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"missing panel lineage manifest: {root}")
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        if "observations_sha256" not in manifest:
            raise ValueError(f"panel lineage missing observations SHA256: {root}")
        for item in items:
            pid=_safe(item["panel_id"])
            if pid in output:
                raise ValueError(f"duplicate panel ID across input folders: {pid}")
            output[pid]=(root,item,manifest)
    return output


def _unit_map(row):
    return dict(p.split("=",1) for p in row.get("concept_units","").split(";")
                if "=" in p)


def _write_model(directory,model,units,headline,source_note,dpi,min_edge):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    details={k:v for k,v in model.items() if k not in
             ("evaluation","predictions","edges","rollout")}
    details["scope_model_status"]="independently_fitted_within_one_station"
    details["regional_category_expert"]=False
    (directory/"fcm_model.json").write_text(json.dumps(details,indent=2)+"\n",
                                             encoding="utf-8")
    for metric in model["evaluation"]:
        metric["unit_note"]=units.get(metric["concept"],"native source unit")
    write_csv(directory/"edge_weights.csv",model["edges"],EDGE_COLS)
    write_csv(directory/"heldout_metrics.csv",model["evaluation"],EVAL_COLS)
    write_csv(directory/"heldout_predictions.csv",model["predictions"],PRED_COLS)
    write_csv(directory/"illustrative_rollout.csv",model["rollout"],ROLL_COLS)
    target=model["evaluation"][0]["concept"]
    fig=directory/"visuals"
    fig.mkdir(parents=True,exist_ok=True)
    graph=network_svg(model["concepts"],model["edges"],title=headline,
        subtitle=source_note,min_abs=min_edge,
        view_warning="New station-local fitted model, not a regional category expert or causal FCM.")
    (fig/"network.svg").write_text(graph,encoding="utf-8")
    (fig/"heldout_hindcast.svg").write_text(
        hindcast_svg(model,target,units.get(target,"")),encoding="utf-8")
    plot_baseline_comparison(directory,fig/"baseline_comparison.png",dpi=dpi)
    plot_edge_weight_heatmap(directory,fig/"edge_weight_heatmap.png",dpi=dpi)
    lines=[
        f"# {headline}","",
        f"{source_note}. **Independently fitted within one station**, not an integrated regional category expert.","",
        f"Concepts: {', '.join(model['concepts'])}.",
        f"Consecutive observed one-day pairs: {model['n_pairs']}; "
        f"train {model['train_pairs']}, validation {model['validation_pairs']}, "
        f"test {model['test_pairs']}.",
        f"Chronological test interval: {model['test_start']} through {model['test_end']}.","",
        "| Concept | FCM MAE | Self-AR MAE | Persistence MAE | Unit |",
        "|---|---:|---:|---:|---|",
    ]
    for row in model["evaluation"]:
        lines.append(
            f"| {row['concept']} | {row['fcm_mae']:.4f} | "
            f"{row['self_ar_mae']:.4f} | {row['persistence_mae']:.4f} | "
            f"{row['unit_note']} |")
    lines += ["",
        "[Node-link FCM](visuals/network.svg) · "
        "[Held-out hindcast](visuals/heldout_hindcast.svg) · "
        "[Baseline chart](visuals/baseline_comparison.png) · "
        "[Edge heatmap](visuals/edge_weight_heatmap.png)",
        "",
        "These are one-day-ahead predictive associations on one held-out "
        "period. Edges are not proven causal. Multi-day simulation is "
        "unvalidated. Model complexity and test-set reuse limit inference.",
    ]
    (directory/"FINDINGS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


def _status(level,cat,sub,pid,item,concepts,status,reason,relative="",sha="",model=None):
    result=dict(
        level=level,category=cat,subcategory=sub,panel_id=pid,
        site_id=item.get("site_id",""),region=item.get("region",""),
        concepts=";".join(concepts),n_concepts=len(concepts),
        n_complete_days=item.get("n_complete_days",""),
        n_consecutive_daily_pairs=item.get("n_consecutive_daily_pairs",""),
        status=status,reason=reason,model_directory=relative,panel_sha256=sha,
        n_train_pairs="",n_validation_pairs="",n_test_pairs="",
        n_beating_self_ar="",n_beating_persistence="")
    if model is not None:
        result.update(
            n_train_pairs=model["train_pairs"],
            n_validation_pairs=model["validation_pairs"],
            n_test_pairs=model["test_pairs"],
            n_beating_self_ar=sum(
                m["fcm_mae"]<m["self_ar_mae"] for m in model["evaluation"]),
            n_beating_persistence=sum(
                m["fcm_mae"]<m["persistence_mae"]
                for m in model["evaluation"]))
    return result


def _source_data_md(item,panel_file,observations_sha):
    return "\n".join([
        "# Observed data and provenance","",
        f"- Site: `{item.get('site_id','')}`; screening region: `{item.get('region','')}`",
        f"- Daily panel file: `{panel_file}`",
        f"- Daily panel SHA256: `{_sha(panel_file)}`",
        f"- Source observations SHA256: `{observations_sha}`",
        f"- Source series: `{item.get('source_series_ids','')}`",
        f"- Native units: `{item.get('concept_units','')}`",
        f"- Datums: `{item.get('concept_datums','')}`",
        f"- Complete UTC calendar days: {item.get('n_complete_days','')}",
        f"- Consecutive one-day transitions: {item.get('n_consecutive_daily_pairs','')}",
        f"- Excluded source observations: {item.get('n_excluded_source_values','')}",
        "",
        "Only observed, same-site aligned daily records were modeled. "
        "There is no missing-data interpolation, cross-site pooling or "
        "implied physical datum conversion.",
    ])+"\n"


def run(panel_dirs,out,min_pairs=79,dpi=150,min_edge=.08):
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty Milestone 8 output directory required")
    if not 0 <= min_edge <= 1 or not 40 <= dpi <= 600:
        raise ValueError("invalid figure resolution or edge cutoff")
    index=_source_index(panel_dirs)
    out.mkdir(parents=True,exist_ok=True)
    statuses=[]
    comparisons=[]
    level_members=defaultdict(list)
    valid_panels=0
    for pid,(root,item,manifest) in sorted(index.items()):
        concepts=[c for c in item.get("concepts","").split(";") if c]
        units=_unit_map(item)
        panel_file=root/(pid+".csv")
        panel_sha=_sha(panel_file) if panel_file.exists() else ""
        data_note=_source_data_md(item,panel_file,manifest["observations_sha256"]) if panel_sha else (
            "No observed daily panel was produced for this candidate.\n")
        base=out/"levels"/"dataset"/pid
        if item["status"]!="candidate_for_held_out_evaluation" or not panel_sha:
            statuses.append(_status("dataset","","",pid,item,concepts,
                                   "skipped_insufficient_observations",
                                   item["status"],sha=panel_sha))
            base.mkdir(parents=True,exist_ok=True)
            (base/"STATUS.md").write_text("# Dataset expert not trained\n\n"+
                item["status"]+"\n",encoding="utf-8")
            (base/"DATA.md").write_text(data_note,encoding="utf-8")
            continue
        source=read_csv(panel_file)
        try:
            full=fit_preview(source,concepts,min_pairs=min_pairs)
        except NotReadyError as exc:
            statuses.append(_status("dataset","","",pid,item,concepts,
                                   "skipped_insufficient_observations",str(exc),
                                   sha=panel_sha))
            base.mkdir(parents=True,exist_ok=True)
            (base/"STATUS.md").write_text(
                "# Dataset expert not trained\n\n"+str(exc)+"\n",encoding="utf-8")
            (base/"DATA.md").write_text(data_note,encoding="utf-8")
            continue
        _write_model(base,full,units,
                     f"{pid}: full dataset expert",
                     f"{item['site_id']} · {item['region']}",dpi,min_edge)
        (base/"DATA.md").write_text(data_note,encoding="utf-8")
        valid_panels+=1
        statuses.append(_status("dataset","","",pid,item,concepts,
                         "trained_station_expert","chronological held-out evaluated",
                         base.relative_to(out).as_posix(),panel_sha,full))
        for level,cat,sub,subset in concept_scopes(concepts):
            rel=(Path("levels")/level/cat/sub/pid if sub
                 else Path("levels")/level/cat/pid)
            destination=out/rel
            scope=cat+(("/"+sub) if sub else "")
            level_members[(level,scope)].append(pid)
            if len(subset)<2:
                result=_status(level,cat,sub,pid,item,subset,
                    "not_trained_insufficient_concepts",
                    "single-concept scope cannot identify cross-concept weights",
                    sha=panel_sha)
                statuses.append(result)
                destination.mkdir(parents=True,exist_ok=True)
                (destination/"STATUS.md").write_text(
                    f"# {level}: {scope} (not trained)\n\n"
                    "Only one observed concept at this station. "
                    "A self-memory relationship is not evidence for a "
                    "multivariate specialist.\n",encoding="utf-8")
                (destination/"DATA.md").write_text(data_note,encoding="utf-8")
                continue
            try:
                fitted=fit_scoped(source,subset,min_pairs=min_pairs)
            except NotReadyError as exc:
                statuses.append(_status(level,cat,sub,pid,item,subset,
                          "not_trained_temporal_readiness",str(exc),sha=panel_sha))
                destination.mkdir(parents=True,exist_ok=True)
                (destination/"STATUS.md").write_text(
                    f"# {level}: {scope} (not trained)\n\n{exc}\n",encoding="utf-8")
                (destination/"DATA.md").write_text(data_note,encoding="utf-8")
                continue
            compare=compare_matched(full,fitted,pid,level,scope)
            comparisons.extend(compare)
            _write_model(destination,fitted,units,
                         f"{scope}: within-station {level} prototype",
                         f"{item['site_id']} · {item['region']}",dpi,min_edge)
            (destination/"DATA.md").write_text(data_note,encoding="utf-8")
            write_csv(destination/"matched_full_comparison.csv",
                      compare,COMPARISON_COLS)
            (destination/"FINDINGS.md").open("a",encoding="utf-8").write(
                "\n## Comparison to full station FCM on identical held-out days\n\n"
                "| Concept | Specialist MAE | Full panel MAE | Difference |\n"
                "|---|---:|---:|---:|\n"+
                "".join(f"| {x['concept']} | {x['specialist_fcm_mae']:.4f} | "
                        f"{x['full_panel_fcm_mae']:.4f} | "
                        f"{x['specialist_minus_full_mae']:+.4f} |\n"
                        for x in compare)+
                "\nNegative difference favors this station-local specialist. "
                "Comparison is descriptive, not a separately validated "
                "regional category/mixture expert.\n")
            statuses.append(_status(level,cat,sub,pid,item,subset,
                "trained_within_station_prototype",
                "independent restricted-concept fit; no cross-station pooling",
                rel.as_posix(),panel_sha,fitted))
    write_csv(out/"model_registry.csv",statuses,REGISTRY_COLS)
    write_csv(out/"matched_specialist_comparisons.csv",comparisons,COMPARISON_COLS)

    # Folder-level navigation and explicit scope reports are created for all
    # named categories, even when no data/model exists for those branches.
    (out/"levels"/"overall").mkdir(parents=True,exist_ok=True)
    (out/"levels"/"overall"/"STATUS.md").write_text(
        "# Overall South Florida FCM — NOT TRAINED\n\n"
        "No cross-region coupling, timescale harmonization or mixture gating "
        "has been fitted. These station-local specialists do not establish "
        "a regional ecosystem model.\n",encoding="utf-8")
    for category in CATEGORIES:
        level_root=out/"levels"/"category"/category
        level_root.mkdir(parents=True,exist_ok=True)
        present=[r for r in statuses if r["level"]=="category"
                 and r["category"]==category]
        fitted=[r for r in present if r["status"]=="trained_within_station_prototype"]
        lines=[
            f"# Category — {category}","",
            "**Regional category expert: NOT TRAINED.**",
            f"Station-local category prototypes fitted: {len(fitted)}.",
            f"Station candidates seen: {len(present)}.","",
            "## Per-station outputs","",
        ]
        for item in present:
            link=item["panel_id"]
            if item["model_directory"]:
                rel=Path(item["model_directory"]).relative_to(
                    Path("levels")/"category"/category)
                lines.append(f"- [{link}]({rel.as_posix()}/FINDINGS.md): {item['status']}")
            else:
                lines.append(f"- {link}: {item['status']}")
        if not present:
            lines.append("No qualifying observed panel concepts yet.")
        lines.extend(["","No station-to-station pooling, regional transfer "
                       "or category-level MoE gating has been fitted."])
        (level_root/"INDEX.md").write_text("\n".join(lines)+"\n",
                                         encoding="utf-8")
    subcategories=sorted({(r["category"],r["subcategory"]) for r in statuses
                          if r["level"]=="subcategory"})
    for category,subcategory in subcategories:
        root=out/"levels"/"subcategory"/category/subcategory
        root.mkdir(parents=True,exist_ok=True)
        matches=[r for r in statuses if r["level"]=="subcategory"
                 and r["category"]==category and
                 r["subcategory"]==subcategory]
        lines=[f"# Subcategory — {category}/{subcategory}","",
               "**Regional subcategory expert: NOT TRAINED.**","",
               "These are independently fitted within-station prototypes "
               "where at least two measured concepts were available.","",
               "## Station panels",""]
        for item in matches:
            if item["model_directory"]:
                lines.append(f"- [{item['panel_id']}]({item['panel_id']}/FINDINGS.md): "
                             f"{item['status']}")
            else:
                lines.append(f"- {item['panel_id']}: {item['status']}")
        (root/"INDEX.md").write_text("\n".join(lines)+"\n",
                                    encoding="utf-8")
    if valid_panels:
        rendered_data=out/"levels"/"dataset"
        lines=["# Dataset / station FCMs",""]
        for r in statuses:
            if r["level"]=="dataset":
                p=r["panel_id"]
                link="FINDINGS.md" if r["status"]=="trained_station_expert" else "STATUS.md"
                lines.append(f"- [{p}]({p}/{link}): {r['status']}")
        (rendered_data/"INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

    lines=[
        "# Milestone 8 — FCM hierarchy and evidence browser","",
        f"Observed station panels supplied: {len(index)}.",
        f"New full dataset-level fits: {valid_panels}.",
        f"Within-station restricted-concept specialist fits: "
        f"{sum(r['status']=='trained_within_station_prototype' for r in statuses)}.",
        "**Regional subcategory, category and overall experts: NOT TRAINED.**","",
        "All model results are chronological held-out fits, "
        "not causal identification or spatial generalization.","",
        "## Browse by level","",
        "- [Dataset / station experts](levels/dataset/INDEX.md)",
    ]
    for category in CATEGORIES:
        lines.append(f"- [Category: {category}](levels/category/{category}/INDEX.md)")
    for cat,sub in subcategories:
        lines.append(f"- [Subcategory: {cat}/{sub}]("
                     f"levels/subcategory/{cat}/{sub}/INDEX.md)")
    lines += ["- [Overall system — untrained](levels/overall/STATUS.md)","",
              "## Cross-panel evidence",
              "- [Model registry](model_registry.csv)",
              "- [Matched specialist/full comparisons](matched_specialist_comparisons.csv)",
              "Each fitted scope has DATA.md, FINDINGS.md, native-unit metrics, "
              "edge weights and a visuals/ folder. Unfitted scopes have STATUS.md.",
              "All full-vs-specialist comparisons are on identical held-out dates.",
              "No test-set winner is automatically promoted to a regional expert.",
              "",
              "To add sites, download new verified histories in bounded batches; "
              "then point this offline tool at multiple daily-panel directories."
             ]
    (out/"INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "panel_inputs":[str(Path(p)) for p in panel_dirs],
        "n_panel_candidates":len(index),"n_fitted_dataset_models":valid_panels,
        "n_station_local_specialist_fits":sum(
            r["status"]=="trained_within_station_prototype" for r in statuses),
        "n_unfitted_scope_candidates":sum(
            r["level"] in ("subcategory","category") and
            r["status"].startswith("not_trained") for r in statuses),
        "regional_subcategory_experts_trained":0,
        "regional_category_experts_trained":0,
        "overall_experts_trained":0,
        "model_selection_on_test":False,
        "causal_identification":False,
        "all_source_data_stays_external":True,
    }
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",
                                     encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panels",action="append",required=True,type=Path,
                   help="observed-only daily panels directory; repeatable")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--min-pairs",type=int,default=79)
    p.add_argument("--dpi",type=int,default=150)
    p.add_argument("--min-edge",type=float,default=.08)
    a=p.parse_args()
    result=run(a.panels,a.out,a.min_pairs,a.dpi,a.min_edge)
    print(f"{result['n_fitted_dataset_models']} full models and "
          f"{result['n_station_local_specialist_fits']} station-local "
          f"specialists; 0 integrated category/overall experts")
    if not result["n_fitted_dataset_models"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
