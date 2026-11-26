"""Readable, scope-specific *evidence* charts, not regional FCM graphs."""
from __future__ import annotations
from math import log10
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _finish(fig,path,dpi):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fig.tight_layout(rect=(0,.07,1,1))
    fig.savefig(path,dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def plot_transfer_ratios(rows,path,scope,dpi=140):
    """Log10(MAE transfer / MAE persistence), so extreme failures stay visible.

    All ratios are dimensionless. Sign above zero means persistence wins.
    Original per-concept native-unit MAEs remain in audit CSV.
    """
    usable=[r for r in rows if r["mae_ratio_vs_persistence"]!=""
            and float(r["mae_ratio_vs_persistence"])>0]
    usable.sort(key=lambda r:(r["target_site"],r["concept"],r["donor_site"]))
    fig,ax=plt.subplots(figsize=(10,max(4.5,len(usable)*.34+1.7)))
    if usable:
        xs=[log10(float(r["mae_ratio_vs_persistence"])) for r in usable]
        names=[r["donor_site"].replace("USGS-","")+" → "+
               r["target_site"].replace("USGS-","")+" · "+
               r["concept"].replace("_"," ") for r in usable]
        ax.barh(range(len(usable)),xs)
        ax.set_yticks(range(len(usable)),labels=names,fontsize=8)
        ax.invert_yaxis()
        ax.axvline(0,color="#445566",linewidth=1)
        ax.set_xlabel("log10(transfer MAE / target persistence MAE); "
                      "> 0 favors persistence")
    else:
        ax.axis("off")
        ax.text(.5,.5,"No scored distinct-station transfers in this scope",
                transform=ax.transAxes,ha="center",va="center")
    ax.set_title(f"Donor-only transfer failure audit — {scope}")
    fig.text(.01,.01,"Positive log-ratios indicate worse transfer forecasts. "
             "Stage comparisons with unverified reference datums are flagged "
             "in the CSV.",fontsize=9)
    _finish(fig,path,dpi)


def plot_edge_strength(rows,path,scope,dpi=140):
    """Show edge magnitude and sign with a minimum-strength threshold."""
    items=sorted(rows,key=lambda r:(
        r["edge_kind"]!="self_memory",
        r["source_concept"],r["target_concept"]))
    fig,ax=plt.subplots(figsize=(10,max(4.5,len(items)*.40+1.6)))
    if items:
        ys=list(range(len(items)))
        labels=[r["source_concept"].replace("_"," ")+" → "+
                r["target_concept"].replace("_"," ") for r in items]
        vals=[float(r["median_abs_weight"]) for r in items]
        ax.barh(ys,vals)
        ax.set_yticks(ys,labels=labels,fontsize=8)
        ax.invert_yaxis()
        threshold=float(items[0]["weight_threshold"])
        ax.axvline(threshold,color="#566677",linestyle="--",linewidth=1,
                   label=f"minimum display magnitude {threshold:g}")
        ax.legend(frameon=False,fontsize=8)
        for i,row in enumerate(items):
            ax.text(vals[i]+.005,i,
                    f"{row['n_sites_above_threshold']}/{row['n_sites']} sites; "
                    f"{row['n_positive']}+/{row['n_negative']}−",
                    va="center",fontsize=7.5)
        ax.set_xlim(0,max(1.12,max(vals)+.35))
        ax.set_xlabel("Median absolute station-specific standardized edge weight")
    else:
        ax.axis("off")
        ax.text(.5,.5,"No independently comparable station edges in this scope",
                ha="center",va="center",transform=ax.transAxes)
    ax.set_title(f"Edge sign and magnitude evidence — {scope}")
    fig.text(.01,.01,"Same sign alone does not imply a strong, stable, "
             "causal, or pooled regional edge.",fontsize=9)
    _finish(fig,path,dpi)


def plot_scope_coverage(rows,path,dpi=140):
    fig,ax=plt.subplots(figsize=(10,max(4.5,.5*len(rows)+1.5)))
    if rows:
        sorted_rows=sorted(rows,key=lambda x:(x["level"],x["scope"]))
        ys=list(range(len(sorted_rows)))
        labels=[r["level"]+" / "+r["scope"] for r in sorted_rows]
        ns=[int(r["n_independent_station_signatures"]) for r in sorted_rows]
        ax.barh(ys,ns)
        ax.set_yticks(ys,labels=labels,fontsize=9)
        ax.invert_yaxis()
        for i,r in enumerate(sorted_rows):
            ax.text(ns[i]+.04,i,
                    f"{r['n_transfer_concept_rows']} transfer concept rows",
                    va="center",fontsize=8)
        ax.set_xlim(0,max(ns)+1.9)
        ax.set_xlabel("Independent fitted stations (not regional expert count)")
    else:
        ax.axis("off")
        ax.text(.5,.5,"No fitted observed station scopes",
                transform=ax.transAxes,ha="center")
    ax.set_title("M8 evidence coverage by environmental scope")
    fig.text(.01,.01,"This is observed station coverage only. "
             "Regional integrated FCMs remain NOT TRAINED.",fontsize=9)
    _finish(fig,path,dpi)
