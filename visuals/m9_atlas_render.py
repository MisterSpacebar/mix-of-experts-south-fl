"""Linked SVG evidence atlas and supporting charts for M9.2.

In station tiles SOLID ARROWS = independently fitted directed one-day
predictive FCM coefficients. Between tiles DASHED UNDIRECTED lines = geographic
screening only. Observed cross-site change correlations are a separate PNG
with no directed arrow. No regional FCM or causal path is fabricated.
"""
from __future__ import annotations
from html import escape
from math import atan2,cos,sin,pi,hypot,ceil
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from visuals.hierarchy import classify
from visuals.network_svg import CATEGORY_FILL,POSITIVE,NEGATIVE


def _xml(value):
    return escape(str(value),quote=True)


def atlas_svg(stations,pairs,minimum=.08,max_cards=9):
    if not 0<=minimum<=1 or max_cards<1:
        raise ValueError("invalid atlas cutoff or station display cap")
    ordered=sorted(stations,key=lambda s:s["site_id"])
    shown=ordered[:max_cards]
    ncol=min(3,max(1,len(shown)));nrow=max(1,ceil(len(shown)/3))
    cardw,cardh=440,590
    width=40+ncol*cardw+30
    height=162+nrow*(cardh+15)+70
    lines=[
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="South Florida cross-axis FCM evidence atlas">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<defs>',
        f'<marker id="pos" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        f'orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="{POSITIVE}"/></marker>',
        f'<marker id="neg" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        f'orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="{NEGATIVE}"/></marker>',
        '</defs>',
        '<text x="30" y="38" font-size="25" font-weight="bold" '
        'font-family="Arial,sans-serif" fill="#173d58">'
        'Geography × environmental subsystem: linked evidence</text>',
        '<text x="30" y="66" font-size="13" font-family="Arial,sans-serif" '
        'fill="#526675">Solid signed arrows: fitted within-station lag-one weights '
        f'(|w| ≥ {minimum:g}), NOT causal links or spatial FCM edges.</text>',
        '<text x="30" y="88" font-size="13" font-family="Arial,sans-serif" '
        'fill="#526675">Dashed gray lines: geographically screened station '
        'pairs ONLY (neither flow nor trained coefficients).</text>',
        '<text x="30" y="110" font-size="13" font-family="Arial,sans-serif" '
        'fill="#526675">Station cards are arranged by ID, NOT on a map. '
        'All higher-level regional and overall FCMs: NOT TRAINED.</text>',
    ]
    if not ordered:
        lines.append('<text x="300" y="240" font-size="15" '
                     'font-family="Arial,sans-serif">No fitted source stations</text>')
        return "\n".join(lines+["</svg>"])+"\n"
    bysite={}
    for number,st in enumerate(shown):
        x0=30+(number%3)*cardw
        y0=132+(number//3)*(cardh+15)
        bysite[st["site_id"]]=(x0+cardw/2,y0+cardh-21,number//3)
        lines.append(
            f'<rect x="{x0}" y="{y0}" width="{cardw-10}" height="{cardh-5}" '
            'rx="14" fill="#fbfdfe" stroke="#b4c8d5" stroke-width="1.5"/>')
        site=st["site_id"].replace("USGS-","")
        name=st.get("site_name") or st["site_id"]
        lines += [
            f'<text x="{x0+18}" y="{y0+30}" font-size="19" font-weight="bold" '
            f'font-family="Arial,sans-serif" fill="#173e58">{_xml(site)}</text>',
            f'<text x="{x0+18}" y="{y0+50}" font-size="12" '
            f'font-family="Arial,sans-serif" fill="#5b6f7b">{_xml(name[:47])}</text>',
            f'<text x="{x0+18}" y="{y0+67}" font-size="11" '
            f'font-family="Arial,sans-serif" fill="#607682">'
            f'Primary: {_xml(st["region"].replace("_"," "))}</text>',
        ]
        names=st["_model"]["concepts"]
        categories=sorted({classify(c)[0] for c in names})
        visible=names[:8] if len(names)>8 else list(names)
        groups={cat:[] for cat in categories}
        for c in visible:
            groups[classify(c)[0]].append(c)
        n_groups=len(groups)
        # Up to 5 taxonomy columns; source remains available in raw CSV
        colpos=[x0+66+(i+.5)*292/max(1,n_groups) for i in range(n_groups)]
        points={}
        for cidx,cat in enumerate(categories):
            cats=groups.get(cat,[])
            if not cats:
                continue
            x=colpos[cidx]
            lines.append(
                f'<rect x="{x-66:.1f}" y="{y0+88}" width="132" height="410" '
                'rx="10" fill="#f2f6f9" stroke="#e0e8ee"/>')
            lines.append(
                f'<text x="{x:.1f}" y="{y0+109}" '
                'font-size="11" text-anchor="middle" font-weight="bold" '
                f'font-family="Arial,sans-serif" fill="#344e60">'
                f'{_xml(cat.replace("_"," ").upper())}</text>')
            for i,concept in enumerate(cats):
                cy=y0+170+(i+.5)*280/max(1,len(cats))
                points[concept]=(x,cy)
        # Learnable, directed solid arrows confined to ONE source station.
        shown_links=0
        for (a,b),w in sorted(st["_edges"].items(),
                 key=lambda z:(-abs(z[1]),z[0][0],z[0][1])):
            if a==b or abs(w)<minimum or a not in points or b not in points:
                continue
            if shown_links>=24:
                break
            ax,ay=points[a];bx,by=points[b]
            delta=hypot(bx-ax,by-ay)
            if delta<1:
                continue
            ux,uy=(bx-ax)/delta,(by-ay)/delta
            # Curvature breaks apart reciprocal arrows. Opposite direction
            # is deliberately a separate source-model link, not symmetry.
            nx,ny=-uy,ux
            sign=1 if a<b else -1
            bend=31*sign if classify(a)[0]!=classify(b)[0] else 42*sign
            sx,sy=ax+ux*47,ay+uy*26
            tx,ty=bx-ux*51,by-uy*30
            cx=(sx+tx)/2+nx*bend
            cy=(sy+ty)/2+ny*bend
            color=POSITIVE if w>=0 else NEGATIVE
            cross=classify(a)[0]!=classify(b)[0]
            lw=1.6+3*abs(w) if cross else 1.0+2*abs(w)
            lines.append(
                f'<path data-type="fitted_station_edge" '
                f'data-cross-category="{str(cross).lower()}" '
                f'd="M {sx:.1f},{sy:.1f} Q {cx:.1f},{cy:.1f} '
                f'{tx:.1f},{ty:.1f}" fill="none" stroke="{color}" '
                f'opacity=".84" stroke-width="{lw:.2f}" '
                f'marker-end="url(#{ "pos" if w>=0 else "neg" })">'
                f'<title>{_xml(a)} → {_xml(b)}: {w:+.3f} '
                '(source t → target t+1, station-local FCM)</title></path>')
            if cross:
                lx=(sx+2*cx+tx)/4
                ly=(sy+2*cy+ty)/4
                lines.append(
                    f'<text x="{lx:.1f}" y="{ly-3:.1f}" '
                    'text-anchor="middle" font-size="9" '
                    f'font-family="Arial,sans-serif" fill="{color}" '
                    f'stroke="#fff" stroke-width="2" paint-order="stroke">'
                    f'{w:+.2f}</text>')
            shown_links+=1
        # Nodes drawn atop arrows; self-loop coefficient explicitly labeled.
        for c,(nx,ny) in points.items():
            color=CATEGORY_FILL.get(classify(c)[0],"#eeeeee")
            w=st["_edges"].get((c,c))
            lines.append(
                f'<rect x="{nx-58:.1f}" y="{ny-30:.1f}" '
                f'width="116" height="60" rx="12" fill="{color}" '
                'stroke="#58758a" stroke-width="1.1"/>')
            lines.append(
                f'<text x="{nx:.1f}" y="{ny-7:.1f}" '
                'text-anchor="middle" font-size="10.5" '
                f'font-family="Arial,sans-serif" fill="#193e57">'
                f'{_xml(c.replace("_"," "))}</text>')
            if w is not None:
                lines.append(
                    f'<text x="{nx:.1f}" y="{ny+14:.1f}" '
                    'text-anchor="middle" font-size="11" '
                    'font-family="Arial,sans-serif" fill="#526a7d">'
                    f'self {w:+.2f}</text>')
        lines += [
            f'<text x="{x0+15}" y="{y0+516}" font-size="11" '
            'font-family="Arial,sans-serif" fill="#526675">'
            f'{shown_links} directed cross-concept arrows shown</text>',
            f'<text x="{x0+15}" y="{y0+536}" font-size="11" '
            'font-family="Arial,sans-serif" fill="#526675">'
            'Blue = positive; orange = negative; self = memory</text>',
            f'<text x="{x0+15}" y="{y0+559}" font-size="10" '
            'font-family="Arial,sans-serif" fill="#6a7a88">'
            'All original weights retained in evidence CSV</text>',
        ]
    # Distinct dashed geographic-screening track BELOW card content,
    # never an arrow between variable nodes.
    for pair in pairs:
        if not pair["geographic_candidate"]:
            continue
        if pair["site_a"] not in bysite or pair["site_b"] not in bysite:
            continue
        ax,ay,ar=bysite[pair["site_a"]]
        bx,by,br=bysite[pair["site_b"]]
        if ar==br:
            y=max(ay,by)+18
            left,right=sorted((ax,bx))
            lines.append(
                f'<path data-type="geographic_screening_only" '
                f'd="M {left:.1f},{y:.1f} L {right:.1f},{y:.1f}" '
                'stroke="#687985" stroke-width="2" '
                'stroke-dasharray="7 5" fill="none"/>')
            label=(f"{float(pair['distance_km']):.1f} km "
                   "straight-line · screening only")
            lines.append(
                f'<text x="{(left+right)/2:.1f}" y="{y+14:.1f}" '
                'text-anchor="middle" font-size="10" '
                f'font-family="Arial,sans-serif" fill="#4c6371">'
                f'{_xml(label)}</text>')
        else:
            # Cross-row links are recorded in the CSV and per-region pages,
            # not drawn across category-specific cards where ambiguous.
            pass
    if len(ordered)>len(shown):
        lines.append(
            f'<text x="30" y="{height-23}" font-size="12" '
            f'font-family="Arial,sans-serif" fill="#546876">'
            f'Showing {len(shown)} of {len(ordered)} stations; '
            'all source models and edges remain available in the CSV.</text>')
    lines.append('</svg>')
    return "\n".join(lines)+"\n"


def plot_change_matrix(pair,records,path,dpi=150):
    """Concurrent first-difference Pearson r, only descriptively."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    ca=sorted({r["concept_a"] for r in records})
    cb=sorted({r["concept_b"] for r in records})
    fig,ax=plt.subplots(figsize=(max(6,1.5*len(cb)+2),
                                 max(5,1.05*len(ca)+2)))
    if ca and cb:
        lookup={(r["concept_a"],r["concept_b"]):r for r in records}
        matrix=np.full((len(ca),len(cb)),np.nan)
        for i,a in enumerate(ca):
            for j,b in enumerate(cb):
                row=lookup.get((a,b))
                if row and row["concurrent_change_pearson_r"]!="":
                    matrix[i,j]=float(row["concurrent_change_pearson_r"])
        figim=ax.imshow(np.ma.masked_invalid(matrix),vmin=-1,vmax=1,
                        cmap="coolwarm")
        for i,a in enumerate(ca):
            for j,b in enumerate(cb):
                text="n/a" if np.isnan(matrix[i,j]) else f"{matrix[i,j]:+.2f}"
                ax.text(j,i,text,ha="center",va="center",fontsize=11)
        ax.set_xticks(range(len(cb)),
                      [x.replace("_"," ") for x in cb],rotation=35,ha="right")
        ax.set_yticks(range(len(ca)),
                      [x.replace("_"," ") for x in ca])
        ax.set_xlabel("Site B: daily change in measured concept")
        ax.set_ylabel("Site A: daily change in measured concept")
        fig.colorbar(figim,ax=ax,shrink=.72,
                     label="Exploratory concurrent-change Pearson r")
    else:
        ax.axis("off")
        ax.text(.5,.5,"No eligible aligned cross-site observed changes",
                transform=ax.transAxes,ha="center")
    ax.set_title("Same-day co-fluctuation — NOT directed regional FCM")
    fig.text(.01,.01,f"{pair['site_a']} / {pair['site_b']} · "
             f"{pair['n_common_one_day_transitions']} aligned daily transitions. "
             "Common forcing and serial dependence not controlled.",fontsize=8)
    fig.tight_layout(rect=(0,.065,1,1))
    fig.savefig(path,dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def plot_region_taxonomy_matrix(rows,path,dpi=150):
    from southfl.regions import REGIONS
    from visuals.hierarchy import CATEGORIES
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    lookup={(r["discovery_region"],r["category"]):r for r in rows}
    values=np.array([[
        int(lookup[(region,cat)]["n_distinct_trained_station_panels"])
        for cat in CATEGORIES] for region in REGIONS])
    fig,ax=plt.subplots(figsize=(11,9))
    image=ax.imshow(values,cmap="Blues",vmin=0,
                    vmax=max(1,int(values.max())))
    ax.set_yticks(range(len(REGIONS)),
                  [r.replace("_"," ") for r in REGIONS],fontsize=9)
    ax.set_xticks(range(len(CATEGORIES)),
                  [c.replace("_"," ") for c in CATEGORIES],
                  rotation=20,ha="right",fontsize=10)
    for i in range(len(REGIONS)):
        for j in range(len(CATEGORIES)):
            ax.text(j,i,str(values[i,j]),ha="center",va="center",
                    fontsize=10,color="#213d50")
    fig.colorbar(image,ax=ax,shrink=.6,
                 label="Distinct trained station panels measuring this category")
    ax.set_title("Geography × category coverage — NOT regional expert counts")
    fig.text(.01,.01,"A station can appear in overlapping discovery rectangles; "
             "cells are screening coverage, NOT independent regional fits.",
             fontsize=9)
    fig.tight_layout(rect=(0,.055,1,1))
    fig.savefig(path,dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def plot_weight_contrast(pair,contrasts,path,dpi=150):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(7,6))
    if contrasts:
        x=[float(r["site_a_weight"]) for r in contrasts]
        y=[float(r["site_b_weight"]) for r in contrasts]
        c=["#237fa4" if r["cross_category"] else "#d2855e"
           for r in contrasts]
        ax.scatter(x,y,c=c,s=45,alpha=.78)
        ax.plot([-1,1],[-1,1],linestyle="--",linewidth=1,color="#7f909c")
        ax.axvline(0,color="#a7b4bc",linewidth=.7)
        ax.axhline(0,color="#a7b4bc",linewidth=.7)
        ax.set_xlim(-1.05,1.05);ax.set_ylim(-1.05,1.05)
        ax.set_aspect("equal",adjustable="box")
        ax.set_xlabel("Fitted weight at station A")
        ax.set_ylabel("Fitted weight at station B")
    else:
        ax.axis("off")
        ax.text(.5,.5,"No comparable original trained weights",
                transform=ax.transAxes,ha="center")
    ax.set_title("Source-trained edge contrast — no pooled FCM")
    fig.text(.01,.01,f"{pair['site_a']} / {pair['site_b']}. "
             "Blue: cross-category; orange: within-category. "
             "Comparison of two station-specific models only.",fontsize=8)
    fig.tight_layout(rect=(0,.065,1,1))
    fig.savefig(path,dpi=dpi,bbox_inches="tight")
    plt.close(fig)
