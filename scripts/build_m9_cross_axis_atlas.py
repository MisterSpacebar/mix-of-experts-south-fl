"""M9.2 — unified source-backed geography × category evidence atlas.

Read frozen M8 fitted station models, measured daily panels, source-located
M9 coordinate assignments and the M9.1 screened-pair ledger. The output
is an atlas of *different evidence types*, NOT a regional FCM retraining.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.m9_regions import station_evidence
from southfl.m9_candidates import assess_pair
from southfl.m9_atlas import (
    TRAINED_COLS,BRIDGE_COLS,CONTRAST_COLS,COFLUCTUATION_COLS,SCOPE_COLS,
    validate_trained_edges,build_trained_edge_records,
    compare_site_coefficients,observed_change_associations,
    category_region_coverage)
from scripts.build_m9_region_readiness import (
    _known_readiness,_trained_registry,_check_sha,sha256,
    _relative_link,_validated_relative_path)
from scripts.screen_m9_spatial_candidates import _load_coordinates
from visuals.hierarchy import CATEGORIES,classify
from visuals.m9_atlas_render import (
    atlas_svg,plot_change_matrix,plot_region_taxonomy_matrix,
    plot_weight_contrast)
from southfl.regions import REGIONS


def _safe_leaf(value):
    if not value or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                        for c in value):
        raise ValueError("unsafe station/pair output path identifier")
    return value


def _match_prior_screen(screen,models,assignments,stations):
    """M9.1 results cannot be quietly exchanged for a different model run."""
    manifest=json.loads((screen/"manifest.json").read_text(encoding="utf-8"))
    _check_sha(models/"manifest.json",manifest["source_model_manifest_sha256"])
    if manifest["coordinate_source_mode"]!="previous_source_verified_M9_assignment":
        raise ValueError("atlas requires verified M9 coordinate assignments in source screen")
    _check_sha(assignments,manifest["coordinate_source_sha256"])
    pairs=read_csv(screen/"candidate_station_pairs.csv")
    expected=set()
    checked=[]
    for i,a in enumerate(stations):
        for b in stations[i+1:]:
            estimate=assess_pair(
                a,b,float(manifest["max_distance_km_proximity_screen_only"]))
            expected.add(estimate["pair_id"])
            originals=[r for r in pairs if r["pair_id"]==estimate["pair_id"]]
            if len(originals)!=1:
                raise ValueError("missing or repeated canonical pair in frozen M9.1 audit")
            reference=originals[0]
            for key in (
                "site_a","site_b","shared_discovery_regions",
                "n_common_observed_days","n_common_one_day_transitions",
                "longest_contiguous_common_days","compatible_concepts",
                "datum_unverified_concepts","common_concepts",
            ):
                if str(estimate[key])!=reference[key]:
                    raise ValueError("M9.1 pair audit differs from verified observations: "+key)
            if float(reference["distance_km"]) and abs(
                    float(reference["distance_km"])-
                    float(estimate["distance_km"]))>1e-5:
                raise ValueError("M9.1 source point distance changed")
            if str(estimate["geographic_candidate"])!=reference["geographic_candidate"]:
                raise ValueError("geographic candidate status changed")
            checked.append(estimate)
    if expected!={r["pair_id"] for r in pairs}:
        raise ValueError("frozen M9.1 ledger contains unknown station pairs")
    return manifest,checked


def _mean_reproducible_str(v):
    return "" if v=="" else f"{float(v):+.3f}"


def run(models,panels,assignments,screen,out,min_weight=.08,
        min_aligned=20,dpi=150):
    models,assignments,screen,out=map(Path,(models,assignments,screen,out))
    if out.exists() and any(out.iterdir()):
        raise ValueError("new or empty atlas output directory required")
    if not 0<=min_weight<=1 or not 5<=min_aligned<=366 or not 40<=dpi<=600:
        raise ValueError("invalid evidence display/evaluation limits")
    sources=_known_readiness(panels)
    registry,full=_trained_registry(models,sources)
    inventory,_,provenance=_load_coordinates(sources,assignments=assignments)
    observed=[]
    for pid,(ready,filename) in sorted(sources.items()):
        if not full[pid]["status"].startswith("trained_"):
            continue
        raw=read_csv(filename)
        station=station_evidence(ready,raw,inventory)
        model_rec=full[pid]
        path=models/_validated_relative_path(model_rec["model_directory"])
        model=json.loads((path/"fcm_model.json").read_text(encoding="utf-8"))
        if set(model["concepts"])!=set(station["_concepts"]):
            raise ValueError("station model has different concept set from daily source")
        station["_model"]=model
        station["_model_dir"]=path
        station["_edges"]=validate_trained_edges(
            model,read_csv(path/"edge_weights.csv"))
        station["_observed"]={date.fromisoformat(r["date"]):r for r in raw}
        observed.append(station)
    observed.sort(key=lambda s:s["site_id"])
    if not observed:
        raise ValueError("no fitted station experts in frozen source run")
    previous,screen_pairs=_match_prior_screen(screen,models,assignments,observed)
    learned,bridges=build_trained_edge_records(observed,min_weight)
    contrasts=compare_site_coefficients(observed,screen_pairs,min_weight)
    cofluct=observed_change_associations(observed,screen_pairs,min_aligned)
    coverage=category_region_coverage(observed,screen_pairs,learned)
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"trained_station_edges_by_subsystem.csv",learned,TRAINED_COLS)
    write_csv(out/"within_station_category_bridges.csv",bridges,BRIDGE_COLS)
    write_csv(out/"cross_station_fcm_edge_contrasts.csv",contrasts,CONTRAST_COLS)
    write_csv(out/"screened_cross_site_daily_change_associations.csv",
              cofluct,COFLUCTUATION_COLS)
    write_csv(out/"region_category_coverage.csv",coverage,SCOPE_COLS)
    figdir=out/"visuals";figdir.mkdir(parents=True,exist_ok=True)
    (figdir/"geography_category_evidence_atlas.svg").write_text(
        atlas_svg(observed,screen_pairs,min_weight),encoding="utf-8")
    plot_region_taxonomy_matrix(
        coverage,figdir/"region_category_coverage.png",dpi)

    pairdir=out/"pairs"
    pair_links={}
    for pair in screen_pairs:
        key=_safe_leaf(pair["pair_id"])
        folder=pairdir/key
        folder.mkdir(parents=True,exist_ok=True)
        subset=[r for r in contrasts if r["pair_id"]==key]
        changes=[r for r in cofluct if r["pair_id"]==key]
        write_csv(folder/"edge_weight_contrast.csv",subset,CONTRAST_COLS)
        write_csv(folder/"observed_change_covariation.csv",
                  changes,COFLUCTUATION_COLS)
        plot_weight_contrast(pair,subset,folder/"visuals"/"station_fcm_contrast.png",dpi)
        plot_change_matrix(pair,changes,
                           folder/"visuals"/"aligned_change_correlations.png",dpi)
        screentype=("geographically_screened_only"
                    if pair["geographic_candidate"] else
                    "not_a_geographic_screening_candidate")
        notes=[
            "# "+pair["site_a"]+" / "+pair["site_b"]+" — evidence comparison","",
            "**REGIONAL AND CROSS-STATION FCM: NOT TRAINED.**",
            "Geographic pair status: `"+screentype+"`.",
            f"Overlap: {pair['n_common_observed_days']} jointly observed days; "
            f"{pair['n_common_one_day_transitions']} paired one-day transitions; "
            f"longest uninterrupted overlap "
            f"{pair['longest_contiguous_common_days']} days.",
            f"Shared discovery rectangles: "
            f"`{pair['shared_discovery_regions'] or 'none'}`.",
            f"Straight-line source-point distance: "
            f"{float(pair['distance_km']):.2f} km.",
            f"Recorded physical-compatibility screen: "
            f"{pair['compatible_concepts'] or 'none'}.",
            f"Unverified stage datums: "
            f"{pair['datum_unverified_concepts'] or 'none'}.","",
            "## Two SEPARATE evidence types","",
            "- [Contrast separately fitted station predictive weights]"
            "(visuals/station_fcm_contrast.png) — NOT pooled model parameters",
            "- [Comparison of all source-trained edges](edge_weight_contrast.csv)",
            "- [Concurrent UTC daily-change correlations]"
            "(visuals/aligned_change_correlations.png) — "
            "observational co-fluctuation only",
            "- [Numerical observed-change correlation table]"
            "(observed_change_covariation.csv)","",
        ]
        if not pair["geographic_candidate"]:
            notes += [
                "The pair did NOT pass the broad discovery/proximity "
                "screen. No cross-site change association was calculated.",
            ]
        else:
            notes += [
                f"Exploratory cross-site change correlations computed "
                f"for {len(changes)} compatible concept pairs, using "
                f"{pair['n_common_one_day_transitions']} aligned one-day "
                "changes; no temporal shifts, interpolation or partial "
                "station pseudo-replication.",
                "These correlations can arise from shared tides, rainfall "
                "or seasonal forcing; they are NOT learned spatial FCM "
                "links, forecasting skill or verified water transport.",
            ]
            notable=sorted(
                (r for r in changes if r["concurrent_change_pearson_r"]!=""),
                key=lambda r:-abs(float(r["concurrent_change_pearson_r"])))
            if notable:
                notes += ["","### Largest exploratory co-fluctuations",""]
                for r in notable[:5]:
                    notes.append(
                        f"- {r['concept_a']} at site A vs {r['concept_b']} "
                        f"at site B: same-day change r="
                        f"{float(r['concurrent_change_pearson_r']):+.2f} "
                        f"(n={r['n_aligned_daily_change_pairs']}); "
                        "**not a causal FCM edge**")
        notes+=["","## Original station FCMs (trained separately)",""]
        for sid in (pair["site_a"],pair["site_b"]):
            st=next(s for s in observed if s["site_id"]==sid)
            d=st["_model_dir"]
            notes.append(
                f"- **{sid}** — "
                f"[full directed FCM]({_relative_link(d/'visuals/network.svg',folder)})"
                f" · [station findings]({_relative_link(d/'FINDINGS.md',folder)})"
                f" · [source provenance]({_relative_link(d/'DATA.md',folder)})")
        notes+=["","## Reproducibility","",
            f"[M9.1 source screening record]"
            f"({_relative_link(screen/'regions',folder)}) (browse by region).",
            "Both site FCMs were independently fitted; any similarity in "
            "coefficients or observed daily changes is descriptive only."]
        (folder/"FINDINGS.md").write_text(
            "\n".join(notes)+"\n",encoding="utf-8")
        pair_links[key]=folder/"FINDINGS.md"

    # Environmental subsystem pages link to sites AND geography; do not
    # turn projected category edges into a regional category FCM.
    for cat in CATEGORIES:
        folder=out/"categories"/cat
        folder.mkdir(parents=True,exist_ok=True)
        touched=[e for e in learned if
                 e["cross_category"] and e["above_display_threshold"] and
                 (e["source_category"]==cat or e["target_category"]==cat)]
        member=[s for s in observed if
                any(classify(c)[0]==cat for c in s["_concepts"])]
        doc=[
            f"# {cat.replace('_',' ').title()} — geographic evidence","",
            "**Integrated geographic-category FCM: NOT TRAINED.**","",
            f"Station models with this category observed: {len(member)}.",
            f"Directed within-station edges connecting this category "
            f"to a different category (|w| ≥ {min_weight:g}): {len(touched)}.",
            "The edges connect environmental concepts **inside one "
            "independently trained station**. No location-to-location "
            "FCM or regional category matrix is fitted.","",
            "## Trained source-site FCMs","",
        ]
        for st in member:
            doc.append(
                f"- [{st['site_name'] or st['site_id']}]"
                f"({_relative_link(st['_model_dir']/'visuals/network.svg',folder)})"
                f" — {st['site_id']} · {st['region']}")
        if not member:
            doc.append("No trained source site measures this category "
                       "in the frozen snapshot.")
        doc+=["","[Combined atlas]"
              f"({_relative_link(figdir/'geography_category_evidence_atlas.svg',folder)})"
              " · [Regional coverage matrix]"
              f"({_relative_link(figdir/'region_category_coverage.png',folder)})"]
        (folder/"FINDINGS.md").write_text(
            "\n".join(doc)+"\n",encoding="utf-8")
    for region in REGIONS:
        folder=out/"regions"/region
        folder.mkdir(parents=True,exist_ok=True)
        local=[s for s in observed if region in
               s["candidate_discovery_regions"].split(";")]
        local_pairs=[p for p in screen_pairs if
                     region in p["shared_discovery_regions"].split(";")]
        doc=[
            f"# {region.replace('_',' ').title()} — coupled evidence view","",
            "**Regional FCM: NOT TRAINED.** "
            "This is a metadata discovery envelope, not a basin polygon.","",
            f"Source-located modeled stations in envelope: {len(local)}.",
            f"Unique geographic candidate pairs in envelope: "
            f"{len({p['pair_id'] for p in local_pairs})}.",
            "A station can appear in multiple discovery rectangles; "
            "it remains one fitted station, not multiple spatial samples.","",
            "## Station FCMs by environmental subsystem","",
        ]
        for st in local:
            d=st["_model_dir"]
            doc.append(
                f"- **{st['site_id']}** ({st['region']} primary): "
                f"[full directed within-station network]"
                f"({_relative_link(d/'visuals/network.svg',folder)})"
                f" · [finding summary]({_relative_link(d/'FINDINGS.md',folder)})")
        if not local:
            doc.append("No station FCM from the current measured snapshot. "
                       "This does not imply agency observations are absent.")
        doc+=["","## Spatial screening context",""]
        for p in local_pairs:
            doc.append(
                f"- [{p['site_a']} / {p['site_b']}]"
                f"({_relative_link(pair_links[p['pair_id']],folder)}): "
                f"{p['n_common_one_day_transitions']} observed transitions; "
                "screening only, not verified flow")
        if not local_pairs:
            doc.append("No trained-station pair shares this rectangle "
                       "within the present frozen input set.")
        doc+=["","## Environmental category pages",""]
        for cat in CATEGORIES:
            doc.append(
                "- ["
                +cat.replace("_"," ").title()
                +"]("
                +_relative_link(out/"categories"/cat/"FINDINGS.md",folder)
                +")")
        doc+=["","[Integrated cross-axis atlas]"
              f"({_relative_link(figdir/'geography_category_evidence_atlas.svg',folder)})"
              " · [Region × category station coverage]"
              f"({_relative_link(figdir/'region_category_coverage.png',folder)})"]
        (folder/"FINDINGS.md").write_text(
            "\n".join(doc)+"\n",encoding="utf-8")
    # Index is intentionally a linked narrative; do NOT suggest that
    # being in the same rectangle constitutes a regional expert.
    visible_bridge=[e for e in learned
                    if e["cross_category"] and e["above_display_threshold"]]
    scored=[r for r in cofluct if r["concurrent_change_pearson_r"]!=""]
    index=[
        "# M9.2 — Integrated geographic × environmental evidence atlas","",
        "**Not a regional FCM.** This combines independently trained "
        "station edges, metadata geographic screening, and exploratory "
        "observed change co-fluctuation WITHOUT pooling or learning "
        "interstation directed edges.","",
        f"Fitted independent full station FCMs: {len(observed)}.",
        f"Original directed station coefficients retained: {len(learned)}.",
        f"Within-station, cross-category arrows passing display threshold "
        f"(|w| ≥ {min_weight:g}): {len(visible_bridge)}.",
        f"Unique canonical source station pairs: {len(screen_pairs)}.",
        f"Geographically screened station pairs: "
        f"{sum(p['geographic_candidate'] for p in screen_pairs)}.",
        f"Exploratory cross-site daily-change variable combinations: "
        f"{len(cofluct)} (scored: {len(scored)}).",
        "**Geographic regional experts / cross-site FCM links / "
        "overall South Florida FCM: NOT TRAINED.**","",
        "## See the connected evidence","",
        "- [**Combined geography × environmental FCM atlas**]"
        "(visuals/geography_category_evidence_atlas.svg) "
        "— SOLID signed arrows are trained *inside station cards*; "
        "DASHED undirected rail is only geographic screening",
        "- [Regional × category coverage grid]"
        "(visuals/region_category_coverage.png) "
        "— number of independently fitted source stations, not region FCMs",
        "- [Full within-station directed concept edges]"
        "(trained_station_edges_by_subsystem.csv)",
        "- [Category-to-category bridge counts by source station]"
        "(within_station_category_bridges.csv)",
        "- [Cross-station contrast of independently trained FCM weights]"
        "(cross_station_fcm_edge_contrasts.csv)",
        "- [Observed cross-site concurrent daily-change covariation]"
        "(screened_cross_site_daily_change_associations.csv) "
        "— separate exploratory observational result, NOT learned arrows","",
        "## Browse each geographic region","",
    ]
    for region in REGIONS:
        index.append(
            "- ["
            +region.replace("_"," ").title()
            +"](regions/"+region+"/FINDINGS.md)")
    index+=["","## Browse environmental categories",""]
    for cat in CATEGORIES:
        index.append(
            "- ["+cat.replace("_"," ").title()
            +"](categories/"+cat+"/FINDINGS.md)")
    index+=["","## Compare independently measured station pairs",""]
    for pair in screen_pairs:
        status="geographic screen candidate" if pair["geographic_candidate"] else "distant comparison"
        index.append(
            f"- [{pair['site_a']} / {pair['site_b']}]"
            f"(pairs/{pair['pair_id']}/FINDINGS.md) — {status}")
    index+=["","## Scientific interpretation","",
        "FCM source → target direction represents day-t to day-t+1 "
        "conditional prediction at **one station**, not an intervention.",
        "Orange/blue signs and magnitudes may change with station, "
        "training period or model definition; do not merge these matrices.",
        "Geographic dashed lines indicate source-located screening. "
        "They are NOT proof of flow or connection.",
        "Observed cross-site daily-change Pearson correlations use the "
        "same actual matched one-day transitions at both sites and "
        "have no learned direction. Shared rainfall/tides/seasonality "
        "can explain covariation.",
        "Gage height is excluded from cross-site covariation without "
        "verified matching geodetic references. More data and verified "
        "connections are required for an integrated regional FCM.",
        "","## Source lineage","",
        f"- [M8 trained station model index]"
        f"({_relative_link(models/'INDEX.md',out)})",
        f"- [M9.1 geographic candidate-screening index]"
        f"({_relative_link(screen/'INDEX.md',out)})",
    ]
    (out/"INDEX.md").write_text("\n".join(index)+"\n",encoding="utf-8")
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_m8_manifest_sha256":sha256(models/"manifest.json"),
        "source_m9_1_screen_manifest_sha256":sha256(screen/"manifest.json"),
        "source_verified_coordinate_assignment_sha256":sha256(assignments),
        "input_observed_daily_panel_roots":[str(Path(x)) for x in panels],
        "n_fitted_full_station_fcms":len(observed),
        "n_unpooled_within_station_directed_edges":len(learned),
        "n_visible_cross_category_within_station_edges":len(visible_bridge),
        "n_unique_original_station_pairs":len(screen_pairs),
        "n_geographically_screened_station_pairs":sum(
            p["geographic_candidate"] for p in screen_pairs),
        "n_exploratory_daily_change_concept_pair_rows":len(cofluct),
        "n_scored_daily_change_correlations":len(scored),
        "min_abs_weight_for_display":min_weight,
        "min_aligned_transitions_for_change_correlation":min_aligned,
        "n_fitted_region_fcms":0,"n_fitted_region_category_fcms":0,
        "n_fitted_interstation_directed_edges":0,
        "n_fitted_overall_southfl_fcms":0,
        "spatial_hydrological_connectivity_verified":False,
        "all_sources_read_only":True,"network_used":False,
    }
    (out/"manifest.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",type=Path,required=True)
    p.add_argument("--panels",type=Path,action="append",required=True)
    p.add_argument("--assignments",type=Path,required=True)
    p.add_argument("--screen",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--min-edge",type=float,default=.08)
    p.add_argument("--min-aligned",type=int,default=20)
    p.add_argument("--dpi",type=int,default=150)
    a=p.parse_args()
    report=run(a.models,a.panels,a.assignments,a.screen,
               a.out,a.min_edge,a.min_aligned,a.dpi)
    print(f"{report['n_fitted_full_station_fcms']} independent station FCMs, "
          f"{report['n_visible_cross_category_within_station_edges']} "
          f"visible source-trained category bridge edges, "
          f"{report['n_scored_daily_change_correlations']} "
          "exploratory cross-site change correlations; "
          "0 regional or cross-station FCMs trained")
    print("Browse",a.out/"INDEX.md")


if __name__=="__main__":
    main()
