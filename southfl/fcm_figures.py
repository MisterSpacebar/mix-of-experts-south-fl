"""Standalone static SVGs for interpretable *predictive*, not causal FCMs.

No network or plotting dependencies. Network arrows are learned lag-one
associations, and hindcast is held-out one-day-ahead teacher-forced prediction.
"""
from html import escape
from math import cos,sin,pi


def network_svg(result,max_edges=14,min_abs=.08):
    concepts=result["concepts"]
    n=len(concepts)
    w,h=900,580
    cx,cy=w/2,278
    radius=175 if n>3 else 150
    pts={name:(cx+radius*cos(2*pi*i/n-pi/2),
               cy+radius*sin(2*pi*i/n-pi/2))
         for i,name in enumerate(concepts)}
    edges=[r for r in result["edges"] if r["edge_kind"]=="cross_concept"
           and abs(r["weight"])>=min_abs]
    edges.sort(key=lambda r:-abs(r["weight"]))
    edges=edges[:max_edges]
    lines=[
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<defs><marker id="pos" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#236fa1"/></marker>',
        '<marker id="neg" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#b06054"/></marker></defs>',
        '<text x="35" y="45" fill="#173c59" font-size="24" font-family="Arial">Dynamic FCM: learned one-day associations</text>',
        '<text x="35" y="70" fill="#5d7181" font-size="14" font-family="Arial">Arrows predict tomorrow from today. NOT inferred causal effects.</text>',
    ]
    for e in edges:
        a,b=pts[e["source_concept"]],pts[e["target_concept"]]
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=(dx*dx+dy*dy)**.5 or 1
        ux,uy=dx/length,dy/length
        p=(a[0]+30*ux,a[1]+30*uy)
        q=(b[0]-36*ux,b[1]-36*uy)
        tint="#236fa1" if e["weight"]>0 else "#b06054"
        marker="pos" if e["weight"]>0 else "neg"
        width=1.3+min(3.8,abs(e["weight"])*3)
        lines.append(f'<path d="M {p[0]:.1f},{p[1]:.1f} L {q[0]:.1f},{q[1]:.1f}" '
                     f'stroke="{tint}" stroke-width="{width:.1f}" fill="none" '
                     f'opacity=".63" marker-end="url(#{marker})"/>')
    for label,(x,y) in pts.items():
        text=escape(label.replace("_"," "))
        self_weight=next((e["weight"] for e in result["edges"]
                          if e["source_concept"]==label and e["target_concept"]==label),0)
        lines.extend([
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="50" fill="#edf5fa" stroke="#518db5" stroke-width="1.7"/>',
            f'<text x="{x:.1f}" y="{y-3:.1f}" fill="#17486a" text-anchor="middle" font-size="12" font-family="Arial">{text}</text>',
            f'<text x="{x:.1f}" y="{y+17:.1f}" fill="#506f82" text-anchor="middle" font-size="11" font-family="Arial">self {self_weight:+.2f}</text>',
        ])
    lines.extend([
        '<rect x="35" y="497" width="16" height="4" rx="2" fill="#236fa1"/>',
        '<text x="60" y="504" font-family="Arial" font-size="13" fill="#405566">positive predictive weight</text>',
        '<rect x="305" y="497" width="16" height="4" rx="2" fill="#b06054"/>',
        '<text x="329" y="504" font-family="Arial" font-size="13" fill="#405566">negative predictive weight</text>',
        f'<text x="35" y="539" font-family="Arial" font-size="12" fill="#6b7882">{len(edges)} strongest displayed non-self edges; source units differ; weights are standardized.</text>',
        '</svg>'])
    return "\n".join(lines)


def hindcast_svg(result,concept):
    samples=[p for p in result["predictions"] if p["concept"]==concept]
    w,h=950,460
    values=[v for r in samples for v in (r["actual"],r["fcm"],r["persistence"])]
    low,high=min(values),max(values)
    if low==high: high=low+1
    padding=(high-low)*.08
    low-=padding; high+=padding
    left,right,top,bottom=82,910,78,368
    sx=lambda i:left+(right-left)*i/max(1,len(samples)-1)
    sy=lambda v:bottom-(v-low)/(high-low)*(bottom-top)
    def line(key,color):
        points=" ".join(f"{sx(i):.1f},{sy(r[key]):.1f}" for i,r in enumerate(samples))
        return f'<polyline points="{points}" stroke="{color}" fill="none" stroke-width="1.9" />'
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="32" y="39" font-family="Arial" font-size="21" fill="#163b59">Held-out 1-day forecast: {escape(concept.replace("_"," "))}</text>',
           '<text x="32" y="61" font-family="Arial" font-size="12" fill="#596b75">Each prediction uses the previous observed day. No future test targets used in fitting.</text>',
           f'<path d="M {left},{top} V {bottom} H {right}" stroke="#6a7f8f" stroke-width="1.1" fill="none"/>']
    for frac in (0,.25,.5,.75,1):
        y=top+(bottom-top)*frac
        v=high-(high-low)*frac
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#e7edf2"/>')
        lines.append(f'<text x="{left-9}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="11" fill="#647889">{v:.2f}</text>')
    lines.extend([line("actual","#1b476a"),line("fcm","#2c98bb"),
                  line("persistence","#c48b47")])
    for i in (0,len(samples)//2,len(samples)-1):
        lines.append(f'<text x="{sx(i):.1f}" y="{bottom+24}" font-family="Arial" font-size="11" text-anchor="middle" fill="#536978">{escape(samples[i]["date"])}</text>')
    lines.extend([
        '<text x="91" y="420" font-family="Arial" font-size="13" fill="#1b476a">■ Observed</text>',
        '<text x="234" y="420" font-family="Arial" font-size="13" fill="#2c98bb">■ Dynamic FCM</text>',
        '<text x="425" y="420" font-family="Arial" font-size="13" fill="#c48b47">■ Persistence baseline</text>',
        '<text x="650" y="420" font-family="Arial" font-size="12" fill="#536978">Uncertainty not calibrated</text>',
        '</svg>'])
    return "\n".join(lines)
