"""M9.2: integrate geographic and subsystem *evidence*, not fitted regions.

Three distinct evidence types are deliberately kept separate:
1. Within-station, source-trained, directed lag-one predictive FCM edges.
2. Between-station screened *geography*, undirected and noncausal.
3. Concurrent, paired observed daily-change correlations across two
   distinct stations (exploratory co-fluctuation; NOT directed FCM edges).

No parameters are pooled or estimated in a regional predictive model.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
from math import isfinite, sqrt
from statistics import mean

from visuals.hierarchy import classify
from .m9_candidates import concept_checks

TRAINED_COLS=[
    "site_id","panel_id","primary_region","source_category","source_subcategory",
    "source_concept","target_category","target_subcategory","target_concept",
    "standardized_lag_one_weight","sign","edge_kind","cross_category",
    "above_display_threshold","model_status","interpretation",
]
BRIDGE_COLS=[
    "site_id","panel_id","primary_region","source_category",
    "target_category","n_all_directed_edges","n_visible_directed_edges",
    "n_visible_positive","n_visible_negative","evidence_status",
]
CONTRAST_COLS=[
    "pair_id","site_a","site_b","geographic_candidate",
    "n_common_one_day_transitions","source_concept","target_concept",
    "source_category","target_category","cross_category","edge_kind",
    "site_a_weight","site_b_weight","site_a_significant_for_display",
    "site_b_significant_for_display","sign_comparison","interpretation",
]
COFLUCTUATION_COLS=[
    "pair_id","site_a","site_b","concept_a","concept_b","category_a",
    "category_b","same_concept","n_aligned_daily_change_pairs",
    "concurrent_change_pearson_r","assessment","relationship_type",
    "interpretation",
]
SCOPE_COLS=[
    "primary_region","category","n_distinct_trained_station_panels",
    "n_distinct_measured_concepts","n_source_trained_edges",
    "n_cross_category_visible_edges_touching_category",
    "n_screened_site_pairs_touching_region",
    "regional_category_expert_status","interpretation",
]


def signed(value):
    v=float(value)
    if not isfinite(v) or not -1.000001<=v<=1.000001:
        raise ValueError("nonfinite or invalid standardized FCM coefficient")
    return v


def validate_trained_edges(model, raw_edges):
    """Verify rounded edge CSV against *the same model's* trained matrix.

    Fail closed on duplicates/omissions or a reordered/replaced result file.
    Edge values are rounded in the existing CSV, so allow 0.000001.
    """
    names=model["concepts"]
    if not 1<=len(names)<=24 or len(set(names))!=len(names):
        raise ValueError("bad fitted model concept order")
    matrix=model["matrix_source_to_target"]
    if len(matrix)!=len(names) or any(len(row)!=len(names) for row in matrix):
        raise ValueError("bad fitted source-to-target matrix shape")
    index={c:i for i,c in enumerate(names)}
    result={}
    for e in raw_edges:
        source,target=e["source_concept"],e["target_concept"]
        if source not in index or target not in index:
            raise ValueError("edge not present in fitted concept set")
        key=(source,target)
        if key in result:
            raise ValueError("duplicate fitted directed edge")
        val=signed(e["weight"])
        exact=signed(matrix[index[source]][index[target]])
        if abs(val-exact)>1.01e-6:
            raise ValueError("edge CSV weight differs from original fitted model")
        result[key]=val
    if len(result)!=len(names)**2:
        raise ValueError("missing fitted source-target edges")
    return result


def build_trained_edge_records(stations,minimum=0.08):
    if not 0<=minimum<=1:
        raise ValueError("invalid edge display cutoff")
    links=[];groups=defaultdict(list)
    for station in stations:
        edges=station["_edges"]
        for (a,b),w in sorted(edges.items()):
            sc,ss=classify(a);tc,ts=classify(b)
            row={
                "site_id":station["site_id"],
                "panel_id":station["panel_id"],
                "primary_region":station["region"],
                "source_category":sc,"source_subcategory":ss,
                "source_concept":a,
                "target_category":tc,"target_subcategory":ts,
                "target_concept":b,
                "standardized_lag_one_weight":w,
                "sign":"positive" if w>0 else "negative" if w<0 else "zero",
                "edge_kind":"self_memory" if a==b else "cross_concept",
                "cross_category":sc!=tc,
                "above_display_threshold":a==b or abs(w)>=minimum,
                "model_status":"trained_within_one_station_full_FCM",
                "interpretation":"trained standardized one-day predictive "
                                 "coefficient; NOT causality, NOT a "
                                 "cross-site or regional FCM edge",
            }
            links.append(row)
            groups[(station["site_id"],station["panel_id"],
                    station["region"],sc,tc)].append(row)
    bridges=[]
    for (site,panel,region,source,target),items in sorted(groups.items()):
        visible=[e for e in items if e["source_concept"]!=e["target_concept"]
                 and e["above_display_threshold"]]
        bridges.append({
            "site_id":site,"panel_id":panel,"primary_region":region,
            "source_category":source,"target_category":target,
            "n_all_directed_edges":len(items),
            "n_visible_directed_edges":len(visible),
            "n_visible_positive":sum(e["sign"]=="positive" for e in visible),
            "n_visible_negative":sum(e["sign"]=="negative" for e in visible),
            "evidence_status":"within_station_FCM_bridge_not_a_regional_model",
        })
    return links,bridges


def compare_site_coefficients(stations,site_pairs,cutoff=.08):
    if not 0<=cutoff<=1:
        raise ValueError("invalid comparison threshold")
    bysite={s["site_id"]:s for s in stations}
    rows=[]
    for pair in site_pairs:
        a,b=bysite[pair["site_a"]],bysite[pair["site_b"]]
        keys=sorted(set(a["_edges"]) & set(b["_edges"]))
        for source,target in keys:
            x=a["_edges"][(source,target)];y=b["_edges"][(source,target)]
            left=abs(x)>=cutoff;right=abs(y)>=cutoff
            if not left or not right:
                state="one_or_both_below_display_threshold"
            elif (x>0 and y>0) or (x<0 and y<0):
                state="both_above_threshold_same_sign"
            else:
                state="both_above_threshold_opposite_sign"
            sc,_=classify(source);tc,_=classify(target)
            rows.append({
                "pair_id":pair["pair_id"],
                "site_a":pair["site_a"],"site_b":pair["site_b"],
                "geographic_candidate":pair["geographic_candidate"],
                "n_common_one_day_transitions":
                    pair["n_common_one_day_transitions"],
                "source_concept":source,"target_concept":target,
                "source_category":sc,"target_category":tc,
                "cross_category":sc!=tc,
                "edge_kind":"self_memory" if source==target else "cross_concept",
                "site_a_weight":x,"site_b_weight":y,
                "site_a_significant_for_display":left,
                "site_b_significant_for_display":right,
                "sign_comparison":state,
                "interpretation":"two separately trained source-specific "
                    "FCM predictive weights, not pooled regional evidence; "
                    "display threshold is NOT a significance test",
            })
    return rows


def _pearson(x,y):
    if len(x)!=len(y) or len(x)<2:
        return None
    mx,my=mean(x),mean(y)
    dx=[v-mx for v in x];dy=[v-my for v in y]
    ssx=sum(v*v for v in dx);ssy=sum(v*v for v in dy)
    if ssx<=1e-16 or ssy<=1e-16:
        return None
    value=sum(i*j for i,j in zip(dx,dy))/sqrt(ssx*ssy)
    return min(1.0,max(-1.0,value))


def _daily_changes(site,concept,aligned_days):
    """Only t-1 and t jointly observed at both stations."""
    bydate=site["_observed"]
    result=[]
    for previous,today in aligned_days:
        u=float(bydate[today][concept])
        v=float(bydate[previous][concept])
        if not isfinite(u) or not isfinite(v):
            raise ValueError("nonfinite observed station change")
        result.append(u-v)
    return result


def observed_change_associations(stations,pairs,min_aligned=20):
    """Exploratory same-UTC-day changes across *geographically screened* sites.

    Both stations must observe t-1 and t; no offset correction, leakage,
    interpolation or causality. Separate station/variable pairs are a
    co-fluctuation screen, not supervised model validation.
    """
    if min_aligned<5:
        raise ValueError("minimum exploratory change count must be >=5")
    bysite={s["site_id"]:s for s in stations}
    result=[]
    for pair in pairs:
        if not pair["geographic_candidate"]:
            continue
        a,b=bysite[pair["site_a"]],bysite[pair["site_b"]]
        shared=sorted(a["_dates"] & b["_dates"])
        transitions=[(p,t) for p,t in zip(shared,shared[1:])
                     if (t-p).days==1]
        if len(transitions)!=pair["n_common_one_day_transitions"]:
            raise ValueError("source-observed transitions do not match pair audit")
        common=sorted(set(a["_concepts"]) & set(b["_concepts"]))
        valid,unclear,_,_=concept_checks(a,b,common)
        for ca in valid:
            for cb in valid:
                xa=_daily_changes(a,ca,transitions)
                yb=_daily_changes(b,cb,transitions)
                r=_pearson(xa,yb) if len(transitions)>=min_aligned else None
                category_a,_=classify(ca);category_b,_=classify(cb)
                result.append({
                    "pair_id":pair["pair_id"],
                    "site_a":a["site_id"],"site_b":b["site_id"],
                    "concept_a":ca,"concept_b":cb,
                    "category_a":category_a,"category_b":category_b,
                    "same_concept":ca==cb,
                    "n_aligned_daily_change_pairs":len(transitions),
                    "concurrent_change_pearson_r":r if r is not None else "",
                    "assessment":(
                        "not_scored_insufficient_aligned_transitions" if
                        len(transitions)<min_aligned else
                        "not_scored_zero_change_variance" if r is None else
                        "exploratory_correlated_changes_not_validated"),
                    "relationship_type":
                        "undirected_contemporaneous_observed_change_covariation",
                    "interpretation":
                        "coincident daily changes across station-variable "
                        "observations; shared rainfall/tides or autocorrelation "
                        "may explain association; NOT an interstation "
                        "predictive/causal FCM connection",
                })
    return result


def category_region_coverage(stations,pairs,edges):
    from .regions import REGIONS
    records=[]
    for region in REGIONS:
        for category in ("hydrology","water_quality","oceanography",
                         "ecology","socioeconomic"):
            in_region=[s for s in stations
                       if region in set(filter(None,
                        s["candidate_discovery_regions"].split(";")))]
            has_cat=[s for s in in_region
                     if any(classify(c)[0]==category for c in s["_concepts"])]
            touched=[e for e in edges if
                     e["site_id"] in {s["site_id"] for s in has_cat} and
                     e["cross_category"] and e["above_display_threshold"] and
                     (e["source_category"]==category or
                      e["target_category"]==category)]
            nearby={p["pair_id"] for p in pairs if
                    p["geographic_candidate"] and
                    (p["site_a"] in {s["site_id"] for s in in_region} or
                     p["site_b"] in {s["site_id"] for s in in_region})}
            records.append({
                "primary_region":region,"category":category,
                "n_distinct_trained_station_panels":len(has_cat),
                "n_distinct_measured_concepts":len({
                    c for s in has_cat for c in s["_concepts"]
                    if classify(c)[0]==category}),
                "n_source_trained_edges":sum(e["site_id"] in {
                    s["site_id"] for s in has_cat} and
                    e["source_category"]==category for e in edges),
                "n_cross_category_visible_edges_touching_category":len(touched),
                "n_screened_site_pairs_touching_region":len(nearby),
                "regional_category_expert_status":"NOT_TRAINED",
                "interpretation":"source-located station coverage in "
                    "overlapping discovery rectangle; not regional model "
                    "or independent region replication",
            })
    return records
