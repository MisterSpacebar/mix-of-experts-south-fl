"""Evidence graphics for Milestone 9.1, without fabricated regional edges."""
from __future__ import annotations

from html import escape
from pathlib import Path
from math import isfinite
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _write_svg_start(title, subtitle, width=1100, height=620):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(title,quote=True)}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="30" y="42" font-size="24" font-weight="bold" '
        f'font-family="Arial,sans-serif" fill="#193c51">{escape(title)}</text>',
        f'<text x="30" y="67" font-size="13" '
        f'font-family="Arial,sans-serif" fill="#526776">{escape(subtitle)}</text>',
    ]


def candidate_pair_network(sites, pairs, title, region=None):
    """Unweighted, undirected screening geometry only.

    Draw coordinates with the same linear WGS84 axis mapping; this is a
    diagram, not a basemap, GIS watershed or transport network. No
    arrows, because there is no learned flow direction or FCM edge.
    """
    width,height=1100,620
    lines=_write_svg_start(
        title,"Gray dashed lines = shared discovery rectangle or proximity "
              "screening ONLY; never a trained FCM or confirmed flow.",
        width,height)
    valid=[s for s in sites if s["latitude"]!="" and s["longitude"]!=""]
    if not valid:
        lines += ['<text x="550" y="285" text-anchor="middle" font-size="17" '
                  'font-family="Arial,sans-serif" fill="#647587">'
                  'No source-verified point coordinates supplied</text>',
                  '<text x="550" y="310" text-anchor="middle" font-size="13" '
                  'font-family="Arial,sans-serif">No candidate edges drawn</text>']
    else:
        lat=[float(s["latitude"]) for s in valid]
        lon=[float(s["longitude"]) for s in valid]
        midlon=(max(lon)+min(lon))/2
        midlat=(max(lat)+min(lat))/2
        spanlon=max(max(lon)-min(lon),.08)
        spanlat=max(max(lat)-min(lat),.08)
        def xy(site):
            x=160+(float(site["longitude"])-(midlon-spanlon*.65))/(spanlon*1.3)*780
            y=530-(float(site["latitude"])-(midlat-spanlat*.65))/(spanlat*1.3)*370
            return x,y
        coords={s["site_id"]:xy(s) for s in valid}
        for pair in pairs:
            if not pair["geographic_candidate"]:
                continue
            a,b=pair["site_a"],pair["site_b"]
            if a not in coords or b not in coords:
                continue
            x1,y1=coords[a];x2,y2=coords[b]
            lines.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                f'y2="{y2:.1f}" stroke="#879ca9" stroke-width="2" '
                f'stroke-dasharray="7 5"/>')
            lines.append(
                f'<text x="{(x1+x2)/2:.1f}" y="{(y1+y2)/2-10:.1f}" '
                'text-anchor="middle" font-size="11" '
                'font-family="Arial,sans-serif" fill="#465e6f">'
                +escape(f"{float(pair['distance_km']):.1f} km straight-line")
                +'</text>')
        for site in valid:
            x,y=coords[site["site_id"]]
            lines.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" '
                'fill="#e2f0fb" stroke="#2f6788" stroke-width="2"/>')
            short=site["site_id"].replace("USGS-","")
            lines.append(
                f'<text x="{x+12:.1f}" y="{y-10:.1f}" '
                'font-size="13" font-family="Arial,sans-serif" '
                f'fill="#184258">{escape(short)}</text>')
            lines.append(
                f'<text x="{x+12:.1f}" y="{y+10:.1f}" '
                'font-size="10" font-family="Arial,sans-serif" '
                f'fill="#718492">{escape(site["region"].replace("_"," "))}</text>')
    lines.append(
        '<text x="30" y="580" font-size="13" '
        'font-family="Arial,sans-serif" fill="#596b79">'
        'Observed monitoring sites only. Dotted proximity is NOT a '
        'hydrological connection. Regional FCM: NOT TRAINED.</text>')
    lines.append('</svg>')
    return "\n".join(lines)+"\n"


def temporal_pair_bars(rows, title, path, dpi=140):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    rows=sorted(rows,key=lambda r:(r["site_a"],r["site_b"]))
    fig,ax=plt.subplots(figsize=(11,max(4.2,2.4+.55*len(rows))))
    if not rows:
        ax.axis("off")
        ax.text(.5,.5,"No eligible screened station pairs in this region",
                transform=ax.transAxes,ha="center",va="center")
    else:
        labels=[r["site_a"].replace("USGS-","")+" / "+
                r["site_b"].replace("USGS-","") for r in rows]
        x=list(range(len(rows)))
        a=[int(r["n_common_observed_days"]) for r in rows]
        b=[int(r["n_common_one_day_transitions"]) for r in rows]
        ax.barh([i-.18 for i in x],a,height=.32,label="Shared observed UTC days")
        ax.barh([i+.18 for i in x],b,height=.32,
                label="Valid shared one-day transitions")
        ax.set_yticks(x,labels=labels,fontsize=9)
        ax.invert_yaxis()
        ax.axvline(79,color="#748492",linestyle="--",linewidth=1,
                   label="79 one-day-transition reference")
        ax.set_xlabel("Count (observed days vs distinct consecutive-day transitions)")
        ax.legend(fontsize=9,frameon=False)
    ax.set_title(title)
    fig.text(.02,.01,"No interpolation. A transition requires both sites "
             "observed on successive UTC dates. Rectangle overlap is not "
             "water transport.",fontsize=9)
    fig.tight_layout(rect=(0,.06,1,1))
    fig.savefig(path,dpi=dpi,bbox_inches="tight")
    plt.close(fig)


def region_candidate_counts(rows,path,dpi=140):
    fig,ax=plt.subplots(figsize=(11,6))
    ordered=sorted(rows,key=lambda x:x["candidate_region"])
    ys=list(range(len(ordered)))
    vals=[int(r["n_unique_screened_station_pairs"]) for r in ordered]
    ax.barh(ys,vals)
    ax.set_yticks(ys,[r["candidate_region"].replace("_"," ") for r in ordered],
                  fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0,max(vals+[0])+1.4)
    for i,v in enumerate(vals):
        ax.text(v+.04,i,str(v),va="center",fontsize=9)
    ax.set_xlabel("Unique site-pair IDs per discovery rectangle")
    ax.set_title("Geographic candidate-pair coverage (not regional FCMs)")
    fig.text(.02,.01,"A pair may occur in two overlapping discovery envelopes; "
             "it is one underlying site pair, not independent replicated data.",
             fontsize=9)
    fig.tight_layout(rect=(0,.055,1,1))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=dpi,bbox_inches="tight")
    plt.close(fig)
