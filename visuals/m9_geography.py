"""Milestone 9 geographic evidence graphics — no invented FCM edges or maps."""
from __future__ import annotations
from datetime import date
from html import escape
from pathlib import Path
from math import cos, sin, pi

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from southfl.regions import REGIONS
from visuals.hierarchy import classify

NODE_COLORS = {
    "hydrology":"#e9f3fd","water_quality":"#e3f7f1",
    "oceanography":"#eeeefd","ecology":"#e9f6e4",
    "socioeconomic":"#fff1e4","unclassified":"#eeeeee",
}


def _save(fig,path,dpi):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fig.tight_layout()
    fig.savefig(path,dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def region_timeline(stations,path,region,dpi=140):
    """Plot exactly observed complete UTC days, showing gaps explicitly."""
    fig,ax=plt.subplots(figsize=(11,max(3.8,1.0+len(stations)*.65)))
    if not stations:
        ax.axis("off")
        ax.text(.5,.5,"No observed daily station panels assigned to this region",
                transform=ax.transAxes,ha="center",va="center",fontsize=11)
    else:
        for i,site in enumerate(sorted(stations,key=lambda x:x["site_id"])):
            observed=sorted(site["_dates"])
            if observed:
                ax.scatter(observed,[i]*len(observed),s=13,alpha=.65)
        ax.set_yticks(list(range(len(stations))),
                       [s["site_id"] for s in sorted(stations,key=lambda x:x["site_id"])],
                       fontsize=8)
        ax.set_xlabel("Observed complete UTC calendar days (gaps retained)")
        ax.set_ylim(-.5,len(stations)-.5)
        ax.grid(axis="x",alpha=.2)
    ax.set_title(region.replace("_"," ").title()+" — measured daily overlap")
    fig.text(.02,.01,"Discovery region assignments only; no gap fill, "
             "verified watershed connectivity, or regional FCM.",
             fontsize=8)
    _save(fig,path,dpi)


def scope_counts(rows,path,dpi=140):
    """One regional status bar per screening-region (station count only)."""
    fig,ax=plt.subplots(figsize=(11,max(5.0,len(rows)*.42+1.0)))
    if rows:
        ordered=sorted(rows,key=lambda r:(-int(r["n_distinct_stations"]),
                                          r["region"]))
        labels=[r["region"].replace("_"," ") for r in ordered]
        nums=[int(r["n_distinct_stations"]) for r in ordered]
        ax.barh(range(len(ordered)),nums)
        ax.set_yticks(range(len(ordered)),labels=labels,fontsize=9)
        ax.invert_yaxis()
        ax.set_xlim(0,max(nums+[0])+1.3)
        ax.set_xlabel("Distinct observed USGS stations assigned to screening region")
        for i,n in enumerate(nums):
            ax.text(n+.05,i,str(n),va="center",fontsize=9)
        ax.axvline(3,linestyle="--",color="#607588",
                   label="Illustrative station-count gate (3)")
        ax.legend(frameon=False,fontsize=8)
    else:
        ax.axis("off")
    ax.set_title("Geographic FCM readiness — observed station coverage")
    fig.text(.02,.01,"Three stations in different regions do not constitute a "
             "three-station model in any one region.",fontsize=8)
    _save(fig,path,dpi)


def discovery_bbox(stations,region,path,dpi=140):
    """Plot source-derived station coordinates if supplied; NEVER fake pins."""
    west,south,east,north=REGIONS[region]
    fig,ax=plt.subplots(figsize=(8,6))
    ax.add_patch(Rectangle((west,south),east-west,north-south,fill=False,
                           edgecolor="#367599",linewidth=2,linestyle="--"))
    verified=[s for s in stations if s["latitude"]!="" and s["longitude"]!=""]
    for s in verified:
        ax.scatter([float(s["longitude"])],[float(s["latitude"])],
                   marker="o",s=65,zorder=3)
        ax.annotate(s["site_id"],(float(s["longitude"]),float(s["latitude"])),
                    xytext=(5,6),textcoords="offset points",fontsize=8)
    if not verified:
        ax.text((west+east)/2,(north+south)/2,
                "No source-verified station coordinates supplied.\n"
                "No station points have been drawn.",
                ha="center",va="center",fontsize=10)
    span=max(east-west,north-south)
    ax.set_xlim(west-.10*span,east+.10*span)
    ax.set_ylim(south-.10*span,north+.10*span)
    ax.set_xlabel("Longitude (WGS84 decimal degrees)")
    ax.set_ylabel("Latitude (WGS84 decimal degrees)")
    ax.set_title(region.replace("_"," ").title()+
                 " — discovery envelope, NOT a watershed polygon")
    fig.text(.02,.01,"Blue dashed rectangle is metadata search bounds. "
             "Points are drawn only from supplied canonical station inventory.",
             fontsize=8)
    _save(fig,path,dpi)


def observed_concept_network(stations,region):
    """Bipartite observed station→measured concept SVG.

    Thin gray lines indicate *measurement membership only*. Do not
    mistake them for trained FCM weights, transport, or causal arrows.
    """
    ordered=sorted(stations,key=lambda x:x["site_id"])
    concepts=sorted({c for s in ordered for c in s["_concepts"]},
                    key=lambda c:(*classify(c),c))
    height=max(450,135+max(len(ordered),len(concepts))*75)
    width=1150
    sx, cx=245,875
    def y_positions(n):
        return ([height/2] if n==1 else
                [100+(height-200)*i/(n-1) for i in range(n)])
    sites_at={s["site_id"]:y for s,y in zip(ordered,y_positions(len(ordered)))}
    concept_at={c:y for c,y in zip(concepts,y_positions(len(concepts)))}
    lines=[
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(region,quote=True)} observed station concept coverage">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="28" y="34" fill="#173d58" font-size="21" '
        f'font-family="Arial,sans-serif" font-weight="bold">'
        f'{escape(region.replace("_"," ").title())}: observed concept coverage</text>',
        '<text x="28" y="57" fill="#506675" font-size="12" '
        'font-family="Arial,sans-serif">Lines denote observed measurement '
        'membership ONLY — not fitted edges or hydrological connections.</text>',
        '<text x="245" y="78" text-anchor="middle" font-size="14" '
        'font-family="Arial,sans-serif">USGS station panels</text>',
        '<text x="875" y="78" text-anchor="middle" font-size="14" '
        'font-family="Arial,sans-serif">Measured concepts (classified)</text>',
    ]
    for station in ordered:
        sy=sites_at[station["site_id"]]
        for c in station["_concepts"]:
            ty=concept_at[c]
            lines.append(f'<path d="M {sx+175},{sy:.1f} C 590,{sy:.1f} '
                         f'590,{ty:.1f} {cx-175},{ty:.1f}" fill="none" '
                         'stroke="#cbd6de" stroke-width="1.5"/>')
    for station in ordered:
        y=sites_at[station["site_id"]]
        lines.append(f'<rect x="{sx-175}" y="{y-21:.1f}" width="350" '
                     'height="42" rx="10" fill="#e9f3fd" stroke="#52748a"/>')
        lines.append(f'<text x="{sx}" y="{y+4:.1f}" '
                     'text-anchor="middle" font-size="13" '
                     'font-family="Arial,sans-serif" fill="#18435a">'+
                     escape(station["site_id"])+'</text>')
    for c in concepts:
        y=concept_at[c]
        category,_=classify(c)
        bg=NODE_COLORS.get(category,"#eeeeee")
        lines.append(f'<rect x="{cx-175}" y="{y-21:.1f}" width="350" '
                     f'height="42" rx="10" fill="{bg}" stroke="#52748a"/>')
        lines.append(f'<text x="{cx}" y="{y+4:.1f}" '
                     'text-anchor="middle" font-size="12" '
                     'font-family="Arial,sans-serif" fill="#18435a">'+
                     escape(c.replace("_"," ")+f"  [{category}]")+'</text>')
    if not ordered:
        lines.append('<text x="575" y="250" text-anchor="middle" '
                     'font-size="16" font-family="Arial,sans-serif" '
                     'fill="#647887">No observed station panels in region</text>')
    lines.append(f'<text x="28" y="{height-24}" fill="#647887" font-size="12" '
                 'font-family="Arial,sans-serif">REGIONAL FCM NOT TRAINED. '
                 'No inferred station-to-station connections or directed '
                 'regional predictive edges.</text>')
    lines.append("</svg>")
    return "\n".join(lines)+"\n"
