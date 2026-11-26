"""Plot descriptive hierarchy views, never synthetic higher-level models.

Dataset/station FCMs remain the only learned experts. Concept taxonomy
merely labels and reorders the same within-panel weights. Subcategory and
category ledgers are projections of that existing model, NOT new fitted
FCMs. Cross-category edges are descriptive observed associations.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np

from .common import read_csv, write_csv
from .fcm_charts import load_edge_matrix
from .network_svg import network_svg
from .hierarchy import (
    COVERAGE_COLS, EDGE_INDEX_COLS, STATUS_COLS, classify,
    concept_taxonomy_rows, edge_index_rows, summarize_hierarchy
)

CONCEPT_ASSIGNMENT_COLS = ["panel_id", "concept", "category", "subcategory",
                           "status"]
CROSS_COLS = EDGE_INDEX_COLS
NETWORK_CATALOG_COLS = [
    "panel_id", "level", "category", "subcategory", "relative_path",
    "n_nodes", "n_source_edges", "n_visible_cross_edges",
    "model_status",
]
HIERARCHY_CAVEAT = ("Views of previously trained station FCMs only. "
                    "No independently trained category, subcategory or overall FCM.")


def plot_grouped_edges(panel_dir, dest, dpi=180):
    """Same trained edge matrix, reordered to make taxonomy separation visible."""
    concepts, matrix = load_edge_matrix(panel_dir)
    idx = {c: i for i, c in enumerate(concepts)}
    ordered = sorted(concepts, key=lambda c: (*classify(c), c))
    values = np.asarray([[matrix[idx[s]][idx[t]] for t in ordered]
                         for s in ordered], dtype=float)
    bound = max(float(np.max(np.abs(values))), 1e-5)
    n = len(ordered)
    fig, ax = plt.subplots(figsize=(max(7.5, 1.5*n+2),
                                    max(6.5, 1.0*n+2)))
    image = ax.imshow(values, cmap="coolwarm",
                      norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound))
    labels = [f"{c.replace('_',' ')}\n({classify(c)[0]}/"
              f"{classify(c)[1]})" for c in ordered]
    ax.set_xticks(np.arange(n), labels=labels, rotation=35, ha="right",
                  fontsize=8)
    ax.set_yticks(np.arange(n), labels=labels, fontsize=8)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{values[i,j]:+.2f}", ha="center",
                    va="center", fontsize=9)
    for i in range(1, n):
        if classify(ordered[i]) != classify(ordered[i-1]):
            ax.axhline(i-.5, color="black", linewidth=0.8)
            ax.axvline(i-.5, color="black", linewidth=0.8)
    ax.set_xlabel("Target concept (category/subcategory)")
    ax.set_ylabel("Source concept (category/subcategory)")
    ax.set_title("Single fitted panel: edges grouped by concept subcategory")
    fig.colorbar(image, ax=ax, label="Standardized signed lag-one weight",
                 shrink=0.85)
    fig.text(0.02, 0.01, HIERARCHY_CAVEAT, fontsize=8)
    fig.tight_layout(rect=(0,0.045,1,1))
    fig.savefig(dest, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def plot_concept_coverage(coverage, dest, dpi=180):
    """Concept counts by taxonomy; never call this category model performance."""
    fig, ax = plt.subplots(figsize=(10, max(4.5, 0.6*len(coverage)+1.8)))
    if coverage:
        labels = [f"{r['category']} / {r['subcategory']}" for r in coverage]
        y = np.arange(len(labels))
        counts = [r["n_distinct_concepts"] for r in coverage]
        ax.barh(y, counts)
        ax.set_yticks(y, labels=labels, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlim(0, max(counts)+1.5)
        for i, r in enumerate(coverage):
            ax.text(r["n_distinct_concepts"]+0.08, i,
                    f"{r['n_distinct_concepts']} concepts · "
                    f"{r['n_panels']} source panels", va="center", fontsize=8)
    else:
        ax.text(.5,.5,"No trained station panels to classify.",
                transform=ax.transAxes,ha="center")
    ax.set_xlabel("Distinct concepts observed in trained station panels")
    ax.set_title("Concept coverage by subcategory — descriptive taxonomy")
    fig.text(.01,.01,HIERARCHY_CAVEAT,fontsize=8)
    fig.tight_layout(rect=(0,0.06,1,1))
    fig.savefig(dest,dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def plot_hierarchy_overview(statuses, dest, dpi=180):
    """Show what is learned versus merely organized into a taxonomy."""
    order={"overall":0,"category":1,"subcategory":2,"dataset_panel":3}
    active=[r for r in statuses if r["level"] in ("overall","dataset_panel")
            or int(r["n_observed_concepts"])>0]
    active.sort(key=lambda r:(order.get(r["level"],9),r["scope"]))
    fig,ax=plt.subplots(figsize=(11,max(4.5,len(active)*.52+1.6)))
    ax.set_xlim(0,1)
    ax.set_ylim(-1,len(active)+.65)
    ax.axis("off")
    for idx,item in enumerate(active):
        y=len(active)-idx-.5
        level=item["level"]
        shift={"overall":0.025,"category":.075,
               "subcategory":.125,"dataset_panel":.025}.get(level,.025)
        color="#eaf3fa" if item["status"]=="trained_preview" else "#f1f1f1"
        rect=plt.Rectangle((shift,y-.34),.96-shift,.68,
                           facecolor=color,edgecolor="#cbd5dd",linewidth=.7)
        ax.add_patch(rect)
        scope=item["scope"].replace("_"," ")
        label=f"{level.upper()}  |  {scope}"
        ax.text(shift+.02,y+.10,label,va="center",fontsize=10,
                fontweight="bold",color="#244865")
        ax.text(shift+.02,y-.14,
                f"{item['status']} · {item['n_observed_concepts']} distinct "
                f"observed concepts · {item['n_contributing_panels']} panels",
                va="center",fontsize=8,color="#5c6670")
    ax.set_title("FCM hierarchy: trained station panels vs planned model levels",
                 loc="left",fontsize=14,pad=12)
    fig.text(.01,.015,HIERARCHY_CAVEAT,fontsize=9)
    fig.tight_layout(rect=(0,.045,1,1))
    fig.savefig(dest,dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def render_panel_networks(panel_id, concepts, edges, panel_root,
                          min_network_weight=0.08):
    """Render scope-specific SVGs without learning or aggregating new weights."""
    panel_root=Path(panel_root)
    if not 0 <= min_network_weight <= 1:
        raise ValueError("min_network_weight must be between 0 and 1")
    rows=[]
    def add(level,category,subcategory,selected,links,relative,title):
        destination=panel_root/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        subtitle=(f"Station panel {panel_id} · "
                  "source t → target t+1 · single fitted model")
        content=network_svg(
            selected,links,title=title,subtitle=subtitle,
            min_abs=min_network_weight)
        destination.write_text(content,encoding="utf-8")
        visible=sum(
            x["source_concept"] != x["target_concept"]
            and abs(float(x["weight"]))>=min_network_weight
            for x in links
        )
        rows.append(dict(
            panel_id=panel_id,level=level,category=category,
            subcategory=subcategory,relative_path=relative,
            n_nodes=len(selected),n_source_edges=len(links),
            n_visible_cross_edges=min(visible,36),
            model_status=("trained_station_panel" if level=="dataset_panel"
                          else "projection_only_not_a_separately_trained_fcm"),
        ))

    ordered=sorted(concepts,key=lambda concept:(*classify(concept),concept))
    add("dataset_panel","","",ordered,edges,"full_network.svg",
        "Full station FCM: all concepts")
    for cat in sorted({classify(c)[0] for c in concepts}):
        selected=[c for c in ordered if classify(c)[0]==cat]
        same=[edge for edge in edges
              if edge["source_concept"] in selected
              and edge["target_concept"] in selected]
        add("category",cat,"",selected,same,
            f"categories/{cat}_network.svg",
            f"{cat.replace('_',' ').title()} — category view")
    for cat,sub in sorted({classify(c) for c in concepts}):
        selected=[c for c in ordered if classify(c)==(cat,sub)]
        same=[edge for edge in edges
              if edge["source_concept"] in selected
              and edge["target_concept"] in selected]
        add("subcategory",cat,sub,selected,same,
            f"subcategories/{cat}__{sub}_network.svg",
            f"{sub.replace('_',' ').title()} — subcategory view")
    categories={classify(c)[0] for c in concepts}
    if len(categories)>1:
        bridges=[edge for edge in edges if
                 classify(edge["source_concept"])[0] !=
                 classify(edge["target_concept"])[0]]
        bridged={e["source_concept"] for e in bridges} | {
            e["target_concept"] for e in bridges
        }
        selected=[c for c in ordered if c in bridged]
        if selected:
            add("cross_category","","",selected,bridges,
                "cross_category_bridge_network.svg",
                "Cross-category bridge edges (same trained panel)")
    write_csv(panel_root/"network_catalog.csv",rows,NETWORK_CATALOG_COLS)
    lines=[
        f"# Network views — {panel_id}","",
        "These SVGs are filtered views of ONE trained station-level FCM.",
        "Category and subcategory networks are not separately trained models.",
        "Arrowheads show the one-day predictive direction, not causality.",
        "Cross-concept edges below the display cutoff are hidden only in figures.",
        "The original `edge_weights.csv` and classified edges CSV preserve every weight.","",
    ]
    for row in rows:
        level=row["level"].replace("_"," ").title()
        scope="/".join(x for x in (row["category"],row["subcategory"]) if x)
        lines.append(
            f"- [{level}: {scope or 'all concepts'}]({row['relative_path']}) "
            f"— {row['n_nodes']} nodes, {row['n_visible_cross_edges']} "
            "displayed non-self arrows"
        )
    (panel_root/"NETWORKS.md").write_text("\n".join(lines)+"\n",
                                          encoding="utf-8")
    return rows


def render_hierarchy(panel_dirs, out_dir, dpi=180, min_network_weight=0.08):
    """Write hierarchical reporting directories from existing fitted panels.

    panel_dirs is [(panel_id, filesystem Path)] from preview manifest.
    """
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    panel_concepts={}
    all_edges=[]
    network_rows=[]
    for panel_id, panel_path in panel_dirs:
        concepts, _ = load_edge_matrix(panel_path)
        panel_concepts[panel_id] = concepts
        panel_root=out_dir/"panels"/panel_id
        panel_root.mkdir(parents=True,exist_ok=True)
        assignment=concept_taxonomy_rows(panel_id,concepts)
        write_csv(panel_root/"concept_assignments.csv",assignment,
                  CONCEPT_ASSIGNMENT_COLS)
        edges=edge_index_rows(panel_id,read_csv(Path(panel_path)/"edge_weights.csv"))
        all_edges.extend(edges)
        write_csv(panel_root/"classified_edges.csv",edges,EDGE_INDEX_COLS)
        network_rows.extend(render_panel_networks(
            panel_id,concepts,edges,panel_root,
            min_network_weight=min_network_weight))
        plot_grouped_edges(panel_path,panel_root/"subcategory_grouped_heatmap.png",
                           dpi=dpi)
        # Views contain only original learned edges, never averaged weights.
        for cat, sub in sorted({classify(c) for c in concepts}):
            internal=[e for e in edges
                      if (e["source_category"],e["source_subcategory"])==(cat,sub)
                      and (e["target_category"],e["target_subcategory"])==(cat,sub)]
            root=out_dir/"subcategories"/cat/sub
            write_csv(root/(panel_id+"_internal_edges.csv"),internal,EDGE_INDEX_COLS)
        for cat in sorted({classify(c)[0] for c in concepts}):
            category_rows=[r for r in assignment if r["category"]==cat]
            root=out_dir/"categories"/cat
            write_csv(root/(panel_id+"_concepts.csv"),category_rows,
                      CONCEPT_ASSIGNMENT_COLS)
    coverage,statuses=summarize_hierarchy(panel_concepts)
    write_csv(out_dir/"concept_coverage.csv",coverage,COVERAGE_COLS)
    write_csv(out_dir/"hierarchy_status.csv",statuses,STATUS_COLS)
    write_csv(out_dir/"all_classified_edges.csv",all_edges,EDGE_INDEX_COLS)
    cross=[e for e in all_edges if
           (e["source_category"],e["source_subcategory"]) !=
           (e["target_category"],e["target_subcategory"])]
    write_csv(out_dir/"cross_subcategory_edges.csv",cross,CROSS_COLS)
    plot_concept_coverage(coverage,out_dir/"subcategory_coverage.png",dpi=dpi)
    plot_hierarchy_overview(statuses,out_dir/"hierarchy_overview.png",dpi=dpi)
    write_csv(out_dir/"network_views.csv",network_rows,NETWORK_CATALOG_COLS)
    index=[
        "# FCM node-link network browser","",
        "These are signed, directional views of trained station-level FCMs.",
        "Subcategory/category files are **not independent fitted models**.","",
        "## Available station panels","",
    ]
    for panel_id,_ in panel_dirs:
        index.append(f"- [{panel_id}](panels/{panel_id}/NETWORKS.md)")
    if not panel_dirs:
        index.append("No trained panels are available in this preview.")
    index+=["","See `hierarchy_status.csv` for the actual training status of each level."]
    (out_dir/"NETWORK_INDEX.md").write_text("\n".join(index)+"\n",encoding="utf-8")
    return {
        "taxonomy_version": "visual_concept_hierarchy_v1",
        "trained_dataset_panels": len(panel_concepts),
        "observed_subcategories": len(coverage),
        "network_svg_views": len(network_rows),
        "network_min_abs_weight": min_network_weight,
        "network_catalog": str(out_dir/"network_views.csv"),
        "network_index": str(out_dir/"NETWORK_INDEX.md"),
        "trained_subcategory_models": 0,
        "trained_category_models": 0,
        "trained_overall_models": 0,
        "descriptive_cross_subcategory_edges": len(cross),
        "note": HIERARCHY_CAVEAT,
    }
