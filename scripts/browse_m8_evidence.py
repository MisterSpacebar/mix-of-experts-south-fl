"""Build a linked, scientifically conservative browser over frozen M8 results.

Read-only with respect to --models, --evidence and --panels. Does NOT train,
pool, select or alter models. A new output directory is always required.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.m8_transfer import transfer_to_target
from southfl.m8_evidence import (
    transfer_diagnostics,edge_strength_diagnostics,uncertainty_integrity,
    TRANSFER_DIAGNOSTIC_COLS,EDGE_DIAGNOSTIC_COLS,UNCERTAINTY_AUDIT_COLS)
from visuals.hierarchy import CATEGORIES
from visuals.m8_evidence_figures import (
    plot_transfer_ratios,plot_edge_strength,plot_scope_coverage)

SCOPE_COLS=[
    "level","scope","n_station_fit_artifacts",
    "n_independent_station_signatures","n_transfer_concept_rows",
    "n_donor_target_pairs","n_edge_records","n_weak_magnitude_edges",
    "n_stage_datum_unverified_transfer_rows","n_interval_audit_warnings",
    "evidence_status","regional_expert_status",
]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _check_text_lineage(path, expected, label):
    """Accept exactly stored bytes or an LF/CRLF-only portability change.

    Git on Windows may normalize CSV/JSON newlines while checking out on
    Linux. Do NOT relax numeric/data/manifest content: only byte-identical
    or newline-equivalent hashes can be accepted.
    """
    data=Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest()==expected:
        return "exact"
    lf=data.replace(b"\\r\\n",b"\\n")
    crlf=lf.replace(b"\\n",b"\\r\\n")
    if (hashlib.sha256(lf).hexdigest()==expected or
            hashlib.sha256(crlf).hexdigest()==expected):
        return "line_ending_only_equivalent"
    raise ValueError(f"{label} SHA256 mismatch: not newline-equivalent")


def _scope(record):
    if record["level"]=="dataset":
        return "full_station"
    return record["category"]+(("/"+record["subcategory"])
                                if record["subcategory"] else "")


def _link(target,from_dir):
    return Path(os.path.relpath(Path(target),Path(from_dir))).as_posix()


def _mdlink(title,target,folder):
    return f"[{title}]({_link(target,folder)})"


def _safe_part(value):
    if not value or any(x in value for x in (".",":","\\","/")):
        raise ValueError("unsafe scope/panel path")
    return value


def _scope_dir(out,level,scope):
    if level=="dataset":
        return out/"levels"/"dataset"/"full_station"
    if level=="overall":
        return out/"levels"/"overall"
    if level not in ("category","subcategory"):
        raise ValueError("unknown model layer")
    return out/"levels"/level/Path(*[_safe_part(x) for x in scope.split("/")])


def _load_sources(panels):
    sources={}
    for root in map(Path,panels):
        manifest=json.loads((root/"panels_manifest.json").read_text(encoding="utf-8"))
        if not manifest.get("observations_sha256"):
            raise ValueError("daily source manifest missing observation lineage hash")
        for row in read_csv(root/"panel_readiness.csv"):
            pid=row["panel_id"]
            if pid in sources:
                raise ValueError(f"duplicate panel ID across source folders: {pid}")
            fp=root/(pid+".csv")
            sources[pid]=(row,fp)
    return sources


def run(models,evidence,panels,out,edge_threshold=.08,dpi=140):
    models,evidence,out=Path(models),Path(evidence),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty output directory required")
    if not 0<=edge_threshold<=1 or not 40<=dpi<=600:
        raise ValueError("invalid plotting limits")
    original_manifest_path=models/"manifest.json"
    prior=json.loads((evidence/"manifest.json").read_text(encoding="utf-8"))
    try:
        manifest_hash_status=_check_text_lineage(
            original_manifest_path,prior["source_m8_manifest_sha256"],
            "source model manifest")
    except ValueError as exc:
        raise ValueError(
            "saved evidence does not belong to requested model run"
        ) from exc
    registry=read_csv(models/"model_registry.csv")
    source=_load_sources(panels)
    reconciled_hashes=(1 if manifest_hash_status==
                       "line_ending_only_equivalent" else 0)
    for entry in registry:
        pid=entry["panel_id"]
        if pid not in source:
            raise ValueError("model panel missing from selected daily sources: "+pid)
        _,fp=source[pid]
        if fp.exists() and entry.get("panel_sha256"):
            status=_check_text_lineage(
                fp,entry["panel_sha256"],"daily panel "+pid)
            if status=="line_ending_only_equivalent":
                reconciled_hashes+=1
        if entry["status"].startswith("trained_") and not fp.exists():
            raise ValueError("missing daily source panel: "+pid)
    # Freeze all input tables before creating any output files.
    transfer=read_csv(evidence/"cross_station_transfer.csv")
    transfer_readiness=read_csv(evidence/"cross_station_transfer_readiness.csv")
    recurrence=read_csv(evidence/"cross_station_edge_signs.csv")
    intervals=read_csv(evidence/"paired_uncertainty_all.csv")
    folds=read_csv(evidence/"temporal_folds_all.csv")
    model_index={}
    edge_weights=defaultdict(list)
    for entry in registry:
        if not entry["status"].startswith("trained_"):
            continue
        level,scope,pid=entry["level"],_scope(entry),entry["panel_id"]
        base=models/entry["model_directory"]
        if not (base/"fcm_model.json").exists():
            raise ValueError("trained model not found: "+str(base))
        # Redundant source scopes are visible, but not counted as
        # independent station-level evaluations.
        if entry.get("same_concept_set_as"):
            continue
        key=(level,scope,pid)
        if key in model_index:
            raise ValueError("duplicate model registry identity")
        model=json.loads((base/"fcm_model.json").read_text(encoding="utf-8"))
        model_index[key]=(entry,model,base)
        edges=read_csv(base/"edge_weights.csv")
        for edge in edges:
            key2=(level,scope,edge["source_concept"],edge["target_concept"])
            edge_weights[key2].append((entry["site_id"],float(edge["weight"])))
    # Transfer predictions CSV intentionally has no layer key. Therefore
    # recompute each previously evaluated donor->target pair by the original
    # saved model and target test dates rather than ambiguously joining it.
    grouped=defaultdict(list)
    for row in transfer:
        grouped[(row["level"],row["scope"],
                 row["donor_panel"],row["target_panel"])].append(row)
    expected_ready={(r["level"],r["scope"],r["donor_panel"],r["target_panel"])
                    for r in transfer_readiness if r["status"]=="evaluated"}
    if set(grouped)!=expected_ready:
        raise ValueError("transfer scores and evaluated-pair ledger mismatch")
    diagnostics=[]
    cached_rows={}
    for (level,scope,donor_id,target_id),original in sorted(grouped.items()):
        if donor_id==target_id:
            raise ValueError("donor and target station cannot match")
        donor_entry,donor_model,_=model_index[(level,scope,donor_id)]
        target_entry,_,target_dir=model_index[(level,scope,target_id)]
        if donor_entry["site_id"]==target_entry["site_id"]:
            raise ValueError("transfer pair uses same source station")
        target_source,target_fp=source[target_id]
        if target_id not in cached_rows:
            cached_rows[target_id]=read_csv(target_fp)
        predictions=read_csv(target_dir/"heldout_predictions.csv")
        recomputed=transfer_to_target(
            donor_model,cached_rows[target_id],predictions,
            donor_model["concepts"])
        donor_source,_=source[donor_id]
        # Include verified true panel IDs and station IDs from model registry.
        donor=dict(donor_source,panel_id=donor_id,
                   site_id=donor_entry["site_id"])
        target=dict(target_source,panel_id=target_id,
                    site_id=target_entry["site_id"])
        diagnostics.extend(transfer_diagnostics(
            donor,target,donor_model,recomputed,original))
    edges=edge_strength_diagnostics(recurrence,edge_weights,edge_threshold)
    ci=uncertainty_integrity(intervals)
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"transfer_failure_audit.csv",
              diagnostics,TRANSFER_DIAGNOSTIC_COLS)
    write_csv(out/"edge_strength_audit.csv",edges,EDGE_DIAGNOSTIC_COLS)
    write_csv(out/"bootstrap_interval_audit.csv",ci,UNCERTAINTY_AUDIT_COLS)

    # Each category and observed subcategory gets a first-class directory,
    # including untrained single-concept scopes and entirely unobserved
    # ecological/socioeconomic branches.
    scopes={("dataset","full_station"),("overall","south_florida")}
    scopes.update(("category",name) for name in CATEGORIES)
    scopes.update((r["level"],_scope(r)) for r in registry
                  if r["level"] in ("category","subcategory"))
    summary=[]
    for level,scope in sorted(scopes):
        folder=_scope_dir(out,level,scope)
        folder.mkdir(parents=True,exist_ok=True)
        members=[r for r in registry if r["level"]==level
                 and _scope(r)==scope] if level!="overall" else []
        fitted=[r for r in members if r["status"].startswith("trained_")]
        unique_signatures={(r["site_id"],r["concepts"])
                           for r in fitted}
        e=[r for r in edges if (r["level"],r["scope"])==(level,scope)]
        t=[r for r in diagnostics if (r["level"],r["scope"])==(level,scope)]
        ci_scoped=[r for r in ci if (r["level"],r["scope"])==(level,scope)]
        warning_count=sum(r["audit_status"]==
                 "point_estimate_outside_bootstrap_interval"
                 for r in ci_scoped)
        n_datum=sum(r["datum_check"]=="reference_datum_unverified" for r in t)
        pair_count=len({(r["donor_panel"],r["target_panel"]) for r in t})
        if level=="overall":
            evidence_status="regional_overall_not_trained"
        elif not fitted:
            evidence_status=("observed_but_no_independent_specialist"
                if members else "no_station_models_in_this_scope")
        elif all(r.get("same_concept_set_as") for r in fitted):
            evidence_status="redundant_concept_scope_not_independent"
        elif pair_count:
            evidence_status="station_transfer_evidence_available"
        else:
            evidence_status="station_models_without_transfer_evidence"
        graded_weak=sum(r["evidence_grade"]==
                "weak_weight_in_at_least_one_site" for r in e)
        record={
            "level":level,"scope":scope,
            "n_station_fit_artifacts":len(fitted),
            "n_independent_station_signatures":len(unique_signatures),
            "n_transfer_concept_rows":len(t),
            "n_donor_target_pairs":pair_count,
            "n_edge_records":len(e),
            "n_weak_magnitude_edges":graded_weak,
            "n_stage_datum_unverified_transfer_rows":n_datum,
            "n_interval_audit_warnings":warning_count,
            "evidence_status":evidence_status,
            "regional_expert_status":"NOT_TRAINED",
        }
        summary.append(record)
        write_csv(folder/"transfer_diagnostics.csv",t,TRANSFER_DIAGNOSTIC_COLS)
        write_csv(folder/"edge_evidence.csv",e,EDGE_DIAGNOSTIC_COLS)
        write_csv(folder/"bootstrap_audit.csv",ci_scoped,UNCERTAINTY_AUDIT_COLS)
        figures=folder/"visuals"
        figures.mkdir(parents=True,exist_ok=True)
        plot_transfer_ratios(t,figures/"transfer_vs_persistence.png",scope,dpi)
        plot_edge_strength(e,figures/"edge_magnitude_and_sign.png",scope,dpi)
        narrative=[
            f"# {level.title()} — {scope}","",
            f"**Evidence state:** `{evidence_status}`.",
            "**Regional integrated expert: NOT TRAINED.**","",
            f"- Within-station fitted scope artifacts: {len(fitted)}.",
            f"- Distinct station/concept-set signatures: {len(unique_signatures)}.",
            f"- Evaluated donor→target station pairs: {pair_count}.",
            f"- Evaluated per-concept transfer comparisons: {len(t)}.",
            f"- Directed edges with station evidence: {len(e)}.",
            f"- Weak edges (one or more station magnitudes below {edge_threshold:g}): "
            f"{graded_weak}.",
            f"- Unverified cross-station stage-datum comparisons: {n_datum}.",
            f"- Bootstrap intervals excluding original error point estimates: "
            f"{warning_count}.","",
            "## Evidence and visualizations","",
            "- "+_mdlink("Transfer MAE ratios (log scale)",
                      figures/"transfer_vs_persistence.png",folder),
            "- "+_mdlink("Edge strength and direction screening",
                      figures/"edge_magnitude_and_sign.png",folder),
            "- "+_mdlink("Donor transfer diagnostics",
                      folder/"transfer_diagnostics.csv",folder),
            "- "+_mdlink("Edge evidence grades",folder/"edge_evidence.csv",folder),
            "- "+_mdlink("Bootstrap uncertainty audit",
                      folder/"bootstrap_audit.csv",folder),
        ]
        prior_folder=(evidence/"levels"/level/
                      (Path(scope) if level!="dataset" else Path()))
        if level in ("category","dataset") and (prior_folder/"FINDINGS.md").exists():
            narrative.append("- "+_mdlink(
                "Prior station-replication findings",
                prior_folder/"FINDINGS.md",folder))
        if level=="subcategory" and evidence_status==(
                "redundant_concept_scope_not_independent"):
            narrative += ["","**Same concept set as a category fit:** "
                          "the existing subcategory fit is a separate artifact, "
                          "not independent observational evidence. "
                          "The replication evaluator correctly omits duplicate "
                          "scope comparisons."]
        if level=="overall":
            narrative += ["","There is no fitted regional or overall FCM. "
                          "These are separate station-level predictive results."]
        narrative += ["","## Trained station models and source findings",""]
        for rec in fitted:
            base=models/rec["model_directory"]
            narrative.append(
                "- **"+rec["site_id"]+"**: "+
                _mdlink("FCM network",base/"visuals"/"network.svg",folder)+
                " · "+_mdlink("Model findings",base/"FINDINGS.md",folder)+
                " · "+_mdlink("Data provenance",base/"DATA.md",folder)+
                (f" · redundant with `{rec['same_concept_set_as']}`"
                 if rec.get("same_concept_set_as") else ""))
        if not fitted:
            narrative.append("No independently trainable multivariate model "
                             "for this scope in the supplied station panels.")
        narrative += ["","The unit check confirms reported unit labels, not "
            "verified hydrological connectivity or sensor reference frames. "
            "Missing stage datums are flagged rather than silently treated "
            "as physically interchangeable.",
            "Edge magnitudes are learned coefficients, not causal strengths. "
            "Source-specific forecasts and the original files are unchanged.",
        ]
        (folder/"FINDINGS.md").write_text("\n".join(narrative)+"\n",
                                          encoding="utf-8")
    write_csv(out/"scope_summary.csv",summary,SCOPE_COLS)
    plot_scope_coverage(summary,out/"scope_coverage.png",dpi)
    index=[
        "# Milestone 8 — scientific evidence browser","",
        "This is a **read-only diagnostic layer** over existing measured "
        "station FCM results. No new regional model was fitted.","",
        f"Independent observed station IDs: "
        f"{len({r['site_id'] for r in registry if r['level']=='dataset' and r['status'].startswith('trained_')})}.",
        f"Previously scored donor→target concept comparisons: {len(transfer)}.",
        f"Recomputed and audited comparisons: {len(diagnostics)}.",
        f"Recorded edge comparisons: {len(edges)}.",
        f"Potentially misleading bootstrap intervals flagged: "
        f"{sum(x['audit_status']=='point_estimate_outside_bootstrap_interval' for x in ci)}.",
        "**Regional category and overall FCMs are NOT TRAINED.**","",
        _mdlink("Scope coverage chart",out/"scope_coverage.png",out),
        "",
        "## Browse by hierarchy layer","",
    ]
    for row in summary:
        folder=_scope_dir(out,row["level"],row["scope"])
        index.append("- "+_mdlink(
            f"{row['level']} / {row['scope']}",folder/"FINDINGS.md",out)+
            f" — {row['n_station_fit_artifacts']} fits; "
            f"{row['n_donor_target_pairs']} evaluated station pairs; "
            f"{row['evidence_status']}")
    index += ["","## Data quality and interpretation","",
        "- "+_mdlink("Transfer model-shift and datum audit",
                     out/"transfer_failure_audit.csv",out),
        "- "+_mdlink("Edge sign **and magnitude** audit",
                     out/"edge_strength_audit.csv",out),
        "- "+_mdlink("Bootstrap interval consistency",
                     out/"bootstrap_interval_audit.csv",out),
        "- "+_mdlink("Scope summary table",
                     out/"scope_summary.csv",out),
        "",
        "A transfer can be numerically evaluated with identical units "
        "while remaining **physically unverified** due to missing stage "
        "datums or station-regime differences. Likewise, 3/3 agreeing "
        "signs on tiny weights is weak evidence. These are screening "
        "diagnostics, not a newly trained South Florida mixture model.",
        "",
        "Original results: "+_mdlink("M8 training browser",
                                    models/"INDEX.md",out)+" · "+
        _mdlink("M8 replication browser",evidence/"INDEX.md",out),
    ]
    (out/"INDEX.md").write_text("\n".join(index)+"\n",encoding="utf-8")
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "models_manifest_sha256":_sha(original_manifest_path),
        "evidence_manifest_sha256":_sha(evidence/"manifest.json"),
        "n_transfer_diagnostics":len(diagnostics),
        "n_edge_evidence_rows":len(edges),
        "n_unverified_stage_datum_rows":sum(
            r["datum_check"]=="reference_datum_unverified" for r in diagnostics),
        "n_bootstrap_point_outside_ci":sum(
            r["audit_status"]=="point_estimate_outside_bootstrap_interval"
            for r in ci),
        "n_scopes":len(summary),
        "edge_magnitude_threshold":edge_threshold,
        "n_line_ending_only_source_hash_matches":reconciled_hashes,
        "lineage_portability":"only exact or LF/CRLF-only SHA equivalence accepted",
        "regional_category_expert_trained":False,
        "regional_overall_expert_trained":False,
        "read_only_source_inputs":True,
    }
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",
                                     encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    p.add_argument("--panels",type=Path,action="append",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--edge-threshold",type=float,default=.08)
    p.add_argument("--dpi",type=int,default=140)
    args=p.parse_args()
    result=run(args.models,args.evidence,args.panels,args.out,
               args.edge_threshold,args.dpi)
    print(f"{result['n_transfer_diagnostics']} audited transfer rows; "
          f"{result['n_edge_evidence_rows']} edge evidence rows; "
          f"{result['n_unverified_stage_datum_rows']} unverified "
          "stage-datum comparisons; NO regional expert fitted")
    print("Browse",args.out/"INDEX.md")


if __name__=="__main__":
    main()
