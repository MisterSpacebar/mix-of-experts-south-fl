"""Fit descriptive dynamic FCM previews from qualified, held-out daily panels.

Refuses insufficient observed continuity and writes an explicit skip record
instead of fabricated edges/forecasts. All results remain untracked under data/.
"""
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.fcm_model import NotReadyError,fit_preview,EVAL_COLS,EDGE_COLS
from southfl.fcm_figures import network_svg,hindcast_svg

PRED_COLS=["date","concept","actual","fcm","self_ar","persistence"]
ROLL_COLS=["step","concept","simulated_value"]


def run(panels,out,min_pairs=79):
    panels,out=Path(panels),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new output directory required")
    summary=read_csv(panels/"panel_readiness.csv")
    source_manifest=json.loads((panels/"panels_manifest.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    for item in summary:
        pid=item["panel_id"]
        if item["status"]!="candidate_for_held_out_evaluation":
            results.append(dict(panel_id=pid,status="skipped",reason=item["status"]))
            continue
        concepts=item["concepts"].split(";")
        units=dict(part.split("=",1) for part in item.get("concept_units","").split(";") if "=" in part)
        datums=dict(part.split("=",1) for part in item.get("concept_datums","").split(";") if "=" in part)
        path=panels/(pid+".csv")
        try:
            model=fit_preview(read_csv(path),concepts,min_pairs=min_pairs)
            # Validate/render everything BEFORE creating the panel's artifact
            # directory. A plotting/programming failure must not leave a
            # seemingly complete model report behind.
            target=min(model["evaluation"],key=lambda r:r["fcm_mae"])["concept"]
            network=network_svg(model)
            hindcast=hindcast_svg(model,target,units.get(target,""))
            directory=out/pid
            directory.mkdir(parents=True,exist_ok=False)
            (directory/"fcm_model.json").write_text(json.dumps({
                k:v for k,v in model.items() if k not in
                ("evaluation","predictions","edges","rollout")
            },indent=2)+"\n",encoding="utf-8")
            write_csv(directory/"edge_weights.csv",model["edges"],EDGE_COLS)
            for metric in model["evaluation"]:
                datum=datums.get(metric["concept"],"")
                metric["unit_note"]=units.get(metric["concept"],"") + (f" ({datum})" if datum else "")
            write_csv(directory/"heldout_metrics.csv",model["evaluation"],EVAL_COLS)
            write_csv(directory/"heldout_predictions.csv",model["predictions"],PRED_COLS)
            write_csv(directory/"illustrative_rollout.csv",model["rollout"],ROLL_COLS)
            (directory/"fcm_network.svg").write_text(network,encoding="utf-8")
            (directory/"heldout_hindcast.svg").write_text(hindcast,encoding="utf-8")
            metrics=["| Concept | FCM MAE | Self-AR MAE | Persistence MAE |",
                     "|---|---:|---:|---:|"]
            for m in model["evaluation"]:
                metrics.append(f'| {m["concept"]} | {m["fcm_mae"]:.4f} | '
                               f'{m["self_ar_mae"]:.4f} | {m["persistence_mae"]:.4f} |')
            report=[
                f'# First dynamic FCM preview: {pid}',
                "",
                f'Canonical station: `{item["site_id"]}`. Screening region: `{item["region"]}`.',
                f'Concepts: {", ".join(concepts)}. Source units: {item.get("concept_units","")}.',
                f'Vertical references: {item.get("concept_datums","")}.',
                f'Chronological pairs: {model["n_pairs"]}. '
                f'Train {model["train_pairs"]}, validation {model["validation_pairs"]}, '
                f'test {model["test_pairs"]}.',
                f'Validation-chosen ridge alpha: {model["ridge_alpha"]}.',
                "",
                *metrics,"",
                'Negative MAE delta versus a baseline indicates lower error.',
                'Metrics are one-day-ahead, *conditional on the previous observed day*.',
                'Weights are signed lag-one predictive associations, not validated causal effects.',
                'The seven-step forward rollout is illustrative and unvalidated.',
                'Do not use as an operational environmental or hypoxia warning model.',
                'No cross-region weights or expert mixture has been fitted.',
            ]
            (directory/"PREVIEW.md").write_text("\n".join(report)+"\n",encoding="utf-8")
            results.append(dict(panel_id=pid,status="trained_preview",
                                reason="held_out_comparison_reported",
                                n_pairs=model["n_pairs"],target_plotted=target,
                                panel_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            print(f"{pid}: {model['n_pairs']} pairs, held-out evaluation saved")
        except NotReadyError as exc:
            # Only a specific, scientifically defined readiness failure may
            # be a skip. KeyError / ValueError may indicate a code, schema,
            # or rendering defect and must fail loudly instead.
            results.append(dict(panel_id=pid,status="skipped",reason=str(exc)))
            print(f"{pid}: skipped — {exc}")
        except (KeyError,ValueError) as exc:
            raise RuntimeError(
                f"FCM preview processing failed for {pid}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "input_panels":str(panels),"input_manifest":source_manifest,
        "n_fitted_previews":sum(x["status"]=="trained_preview" for x in results),
        "n_skipped":sum(x["status"]=="skipped" for x in results),
        "results":results,
        "validation":"chronological train-validation-test; no future-data features",
        "causal_discovery":False,"operational_ready":False,
    }
    (out/"preview_manifest.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panels",type=Path,default=Path("data/m7/daily_panels_v1"))
    p.add_argument("--out",type=Path,default=Path("data/m7/fcm_preview_v1"))
    p.add_argument("--min-pairs",type=int,default=79)
    a=p.parse_args()
    report=run(a.panels,a.out,a.min_pairs)
    print(f"{report['n_fitted_previews']} held-out FCM previews; "
          f"{report['n_skipped']} skipped panels")
    if not report["n_fitted_previews"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
