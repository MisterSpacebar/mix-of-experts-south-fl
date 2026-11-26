"""Standalone, file-backed replication diagnostics for every model layer.

Plots summarize station-local evidence only. No regional fitted network or
causal direction is inferred from cross-site sign frequencies.
"""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _ready(path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    return path


def _empty(ax,message):
    ax.axis("off")
    ax.text(.5,.5,message,transform=ax.transAxes,ha="center",va="center",
            fontsize=12,color="#667681")


def plot_fold_skills(rows,path,dpi=140):
    fig,ax=plt.subplots(figsize=(9,4.8))
    by_concept={}
    for row in rows:
        by_concept.setdefault(row["concept"],[]).append(row)
    if by_concept:
        for concept,items in sorted(by_concept.items()):
            items.sort(key=lambda r:int(r["fold"]))
            pts=[(int(item["fold"]),float(item["skill_vs_self_ar"]))
                 for item in items if item["skill_vs_self_ar"] is not None]
            if pts:
                ax.plot([x for x,_ in pts],[y for _,y in pts],
                        marker="o",label=concept.replace("_"," "))
        ax.axhline(0,color="#445566",linewidth=1,linestyle="--")
        ax.set_xlabel("Chronological expanding-window evaluation fold")
        ax.set_ylabel("FCM skill vs self-AR (positive favors FCM)")
        ax.set_title("Temporal sensitivity — non-overlapping test dates")
        ax.legend(loc="best",fontsize=8,frameon=False)
    else:
        _empty(ax,"No valid expanding-window folds in this scope")
    fig.text(.02,.01,"Folds share earlier training histories; "
             "they are not independent replications.",fontsize=9)
    fig.tight_layout(rect=(0,.04,1,1))
    fig.savefig(_ready(path),dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def plot_edge_sign_recurrence(rows,path,dpi=140):
    eligible=[r for r in rows if r["status"]==
              "replication_candidate_not_causal" and
              r["sign_consistency"]!=""]
    eligible.sort(key=lambda r:(
        -int(r["n_distinct_sites"]),
        -float(r["sign_consistency"]),r["source_concept"],r["target_concept"]))
    displayed=eligible[:18]
    fig,ax=plt.subplots(figsize=(9,max(4.5,len(displayed)*.43+1.4)))
    if displayed:
        labels=[r["source_concept"].replace("_"," ")+" → "+
                r["target_concept"].replace("_"," ") for r in displayed]
        ys=list(range(len(labels)))
        ax.barh(ys,[float(r["sign_consistency"]) for r in displayed])
        ax.set_yticks(ys,labels=labels,fontsize=8)
        ax.invert_yaxis()
        ax.set_xlim(0,1.05)
        ax.set_xlabel("Fraction sharing majority sign (nonzero learned weights)")
        for i,r in enumerate(displayed):
            ax.text(float(r["sign_consistency"])+.01,i,
                    f"n={r['n_distinct_sites']}",va="center",fontsize=8)
    else:
        _empty(ax,"Insufficient independent comparable stations "
               "for sign-recurrence screening")
    ax.set_title("Independent-station edge sign recurrence — descriptive only")
    fig.text(.02,.01,"No pooled FCM, statistical significance or causal edge "
             "is implied. Matching measured units/datums required.",fontsize=8)
    fig.tight_layout(rect=(0,.045,1,1))
    fig.savefig(_ready(path),dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def plot_transfer_skill(rows,path,dpi=140):
    points=[r for r in rows if r["transfer_skill_vs_persistence"] is not None]
    points.sort(key=lambda r:(r["donor_site"],r["target_site"],r["concept"]))
    displayed=points[:24]
    fig,ax=plt.subplots(figsize=(10,max(4.8,len(displayed)*.40+1.8)))
    if displayed:
        labels=[
            r["donor_panel"]+" → "+r["target_panel"]+" · "+
            r["concept"].replace("_"," ") for r in displayed]
        ys=list(range(len(displayed)))
        scores=[float(r["transfer_skill_vs_persistence"]) for r in displayed]
        ax.barh(ys,scores)
        ax.set_yticks(ys,labels=labels,fontsize=7.5)
        ax.invert_yaxis()
        ax.axvline(0,color="#555555",linewidth=1)
        ax.set_xlabel("Donor transfer skill vs target persistence "
                      "(positive favors donor)")
    else:
        _empty(ax,"No physically compatible distinct-station "
               "donor→target test currently available")
    ax.set_title("Held-out donor-only FCM transfer — station generalization probe")
    fig.text(.02,.01,"One-day conditional forecast; no target station fitted "
             "into donor model. Limited test periods.",fontsize=8)
    fig.tight_layout(rect=(0,.045,1,1))
    fig.savefig(_ready(path),dpi=dpi,bbox_inches="tight")
    plt.close(fig)
