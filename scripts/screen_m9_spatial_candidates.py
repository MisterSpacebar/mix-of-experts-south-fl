"""M9.1: audit candidate geography and temporal readiness across stations.

Reads frozen M8 station models, original observed daily panel CSVs and
either an M9 coordinate-certified assignment snapshot or the local USGS
inventory. Outputs are screening evidence ONLY, never a trained region FCM.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime,timezone
from itertools import combinations
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.regions import REGIONS
from southfl.m9_regions import station_evidence
from southfl.m9_candidates import (
    PAIR_COLS,SCOPE_COLS,REGION_COLS,INVENTORY_AUDIT_COLS,
    inventory_audit,assess_pair,assess_scopes,summarize_discovery_regions,
    candidate_regions)
from scripts.build_m9_region_readiness import (
    _known_readiness,_trained_registry,_check_sha,sha256,_relative_link,
    _validated_relative_path)
from visuals.hierarchy import CATEGORIES
from visuals.m9_candidate_figures import (
    candidate_pair_network,temporal_pair_bars,region_candidate_counts)


def _load_coordinates(sources, assignments=None, stations=None):
    """One coordinate source, always checked against original panel keys."""
    if assignments and stations:
        raise ValueError("supply saved assignments OR raw station inventory")
    if assignments:
        assignments=Path(assignments)
        rows=read_csv(assignments)
        by_pid={}
        inventory={}
        for row in rows:
            pid=row["panel_id"]
            if pid in by_pid:
                raise ValueError("duplicate saved coordinate panel assignment")
            if pid not in sources:
                raise ValueError("saved coordinate assignment not in frozen models")
            original,fp=sources[pid]
            if (row["site_id"]!=original["site_id"] or
                    row["region"]!=original["region"]):
                raise ValueError("coordinate source disagrees with model panel assignment")
            _check_sha(fp,row["panel_sha256"])
            by_pid[pid]=row
            if row.get("coordinates_status")=="verified_point_inside_discovery_rectangle":
                if not row.get("source_url"):
                    raise ValueError("source point lacks recorded metadata provenance")
                inventory[row["site_id"]]=dict(
                    dataset_id="usgs_water",site_id=row["site_id"],
                    latitude=row["latitude"],longitude=row["longitude"],
                    site_name=row["site_name"],source_url=row["source_url"],
                )
        if set(by_pid)!=set(sources):
            raise ValueError("incomplete coordinate assignment snapshot")
        return inventory,[],{
            "coordinate_source_mode":"previous_source_verified_M9_assignment",
            "coordinate_source_sha256":sha256(assignments),
            "alternate_namespace_ids_audited":False,
        }
    if stations:
        stations=Path(stations)
        inventory,audit=inventory_audit(
            read_csv(stations),
            required={row["site_id"] for row,_ in sources.values()})
        return inventory,audit,{
            "coordinate_source_mode":"local_canonical_agency_inventory",
            "coordinate_source_sha256":sha256(stations),
            "alternate_namespace_ids_audited":True,
        }
    return {},[],{
        "coordinate_source_mode":"not_supplied",
        "coordinate_source_sha256":None,
        "alternate_namespace_ids_audited":False,
    }


def run(models,panels,out,assignments=None,stations=None,
        max_distance_km=30,min_pairs=79,min_concepts=2,dpi=140):
    models,out=Path(models),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new or empty output directory required")
    if not 0<max_distance_km<=250 or not 1<=min_pairs<=366:
        raise ValueError("invalid geographic or temporal gate")
    if not 2<=min_concepts<=8 or not 40<=dpi<=600:
        raise ValueError("invalid concept or plotting cap")
    sources=_known_readiness(panels)
    registry,full=_trained_registry(models,sources)
    inventory,audit,coord_provenance=_load_coordinates(
        sources,assignments,stations)
    site_rows=[]
    unique_sites=set()
    for pid,(readiness,fp) in sorted(sources.items()):
        if readiness["site_id"] in unique_sites:
            raise ValueError("duplicate modeled canonical station ID")
        unique_sites.add(readiness["site_id"])
        data=station_evidence(readiness,read_csv(fp),inventory)
        data["panel_sha256"]=sha256(fp)
        site_rows.append(data)
    site_rows.sort(key=lambda x:x["site_id"])
    candidate_pairs=[
        assess_pair(a,b,max_distance_km)
        for a,b in combinations(site_rows,2)]
    scopes=[s for p in candidate_pairs
            for s in assess_scopes(p,min_pairs,min_concepts)]
    regions=summarize_discovery_regions(
        site_rows,candidate_pairs,scopes,min_pairs)
    region_pair_rows=[]
    for r in regions:
        name=r["candidate_region"]
        for pair in candidate_pairs:
            if name in pair["shared_discovery_regions"].split(";"):
                region_pair_rows.append({
                    **pair,"candidate_region":name,
                    "single_global_pair_id_even_if_repeated_in_another_envelope":
                        pair["pair_id"],
                })
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"candidate_station_pairs.csv",candidate_pairs,PAIR_COLS)
    write_csv(out/"candidate_pair_subsystems.csv",scopes,SCOPE_COLS)
    write_csv(out/"discovery_region_summary.csv",regions,REGION_COLS)
    write_csv(out/"cross_rectangle_pair_memberships.csv",region_pair_rows,
              ["candidate_region"]+PAIR_COLS+[
                  "single_global_pair_id_even_if_repeated_in_another_envelope"])
    write_csv(out/"coordinate_inventory_exclusions.csv",
              audit,INVENTORY_AUDIT_COLS)
    write_csv(out/"source_station_provenance.csv",[
        {k:s.get(k,"") for k in (
            "site_id","panel_id","region","candidate_discovery_regions",
            "coordinates_status","latitude","longitude","site_name",
            "source_url","panel_sha256")}
        for s in site_rows],
        ["site_id","panel_id","region","candidate_discovery_regions",
         "coordinates_status","latitude","longitude","site_name",
         "source_url","panel_sha256"])
    visuals=out/"visuals"
    visuals.mkdir(parents=True,exist_ok=True)
    (visuals/"candidate_station_graph.svg").write_text(
        candidate_pair_network(
            site_rows,candidate_pairs,"South Florida candidate station pairs"),
        encoding="utf-8")
    region_candidate_counts(
        regions,visuals/"candidate_rectangle_counts.png",dpi)
    temporal_pair_bars(
        [p for p in candidate_pairs if p["geographic_candidate"]],
        "Selected geographic candidates: observed days vs one-day transitions",
        visuals/"temporal_readiness_comparison.png",dpi)
    index=[
        "# Milestone 9.1 — geographic candidate pairs and temporal readiness","",
        "**REGIONAL / SUBSYSTEM FCMs: NOT TRAINED.** "
        "This is a geographic screening and observation-evidence report.",
        f"Independent observed modeled sites: {len(site_rows)}.",
        f"Unique distinct-station pairs reviewed: {len(candidate_pairs)}.",
        f"Pairs meeting discovery/proximity screening: "
        f"{sum(p['geographic_candidate'] for p in candidate_pairs)}.",
        f"One-day transition screening reference: {min_pairs} "
        "(accumulated across real observation gaps; no interpolation).","",
        "## Visuals and evidence","",
        "- [Candidate station-pair diagram](visuals/candidate_station_graph.svg) "
        "— dashed, undirected screening-only associations",
        "- [Observed days and valid one-day transitions]"
        "(visuals/temporal_readiness_comparison.png)",
        "- [Discovery rectangle pair counts]"
        "(visuals/candidate_rectangle_counts.png)",
        "- [Pair assessment ledger](candidate_station_pairs.csv)",
        "- [Region / hydrology / water quality / subcategory gates]"
        "(candidate_pair_subsystems.csv)",
        "- [Per-rectangle candidate summary](discovery_region_summary.csv)",
        "- [Repeated rectangle memberships — shared pair IDs, not replications]"
        "(cross_rectangle_pair_memberships.csv)",
        "- [Station source coordinates and hash provenance]"
        "(source_station_provenance.csv)",
        "- [Station identifier exclusions](coordinate_inventory_exclusions.csv)","",
        "## Screening regions","",
    ]
    for row in regions:
        region=row["candidate_region"]
        root=out/"regions"/region
        root.mkdir(parents=True,exist_ok=True)
        members=[s for s in site_rows if region in candidate_regions(s)]
        pairs=[p for p in candidate_pairs
               if region in p["shared_discovery_regions"].split(";")]
        pair_ids={p["pair_id"] for p in pairs}
        scoped=[s for s in scopes if s["pair_id"] in pair_ids]
        write_csv(root/"candidate_pairs.csv",pairs,PAIR_COLS)
        write_csv(root/"candidate_scope_evidence.csv",scoped,SCOPE_COLS)
        (root/"visuals").mkdir(parents=True,exist_ok=True)
        (root/"visuals"/"candidate_station_graph.svg").write_text(
            candidate_pair_network(members,pairs,
                region.replace("_"," ").title()+" · observed screening pairs",
                region),
            encoding="utf-8")
        temporal_pair_bars(
            pairs,region.replace("_"," ").title()+
                  " · temporal pair evidence",
            root/"visuals"/"temporal_overlap.png",dpi)
        notes=[
            "# "+region.replace("_"," ").title()+" — candidate geography","",
            "**GEOGRAPHIC REGION FCM: NOT TRAINED.**",
            "Discovery rectangle only: region membership is not a "
            "watershed, verified transport connection or flow direction.","",
            f"Unique sites with verified coordinates in envelope: "
            f"{len(members)}.",
            f"Unique screened source station pairs: {len(pair_ids)}.",
            f"Pairs meeting accumulated {min_pairs}-transition criterion: "
            f"{row['n_pairs_with_enough_one_day_transitions']}.",
            "Pairs are counted by their global pair ID; they may appear "
            "in more than one rectangle without representing additional "
            "independent data.","",
            "## Evidence and figures","",
            "- [Dashed candidate node graph](visuals/candidate_station_graph.svg)"
            " — not a learned FCM",
            "- [Shared-days vs one-day transitions](visuals/temporal_overlap.png)",
            "- [Candidate pair ledger](candidate_pairs.csv)",
            "- [Concept/subsystem readiness](candidate_scope_evidence.csv)","",
            "## Candidate pairs and modeling gates","",
        ]
        for p in pairs:
            ps=[s for s in scoped if s["pair_id"]==p["pair_id"]
                and s["scope_level"]=="region"]
            status=ps[0]["spatial_candidate_status"] if ps else "unassessed"
            notes.append(
                f"- **{p['site_a']} / {p['site_b']}**: "
                f"{p['n_common_observed_days']} overlapping observed days; "
                f"{p['n_common_one_day_transitions']} valid 1-day transitions; "
                f"{p['longest_contiguous_common_days']} longest uninterrupted days; "
                f"{p['n_compatible_concepts']} measured, same-unit/datum-eligible "
                f"concepts; status `{status}`")
        if not pairs:
            notes.append("No independently observed station pair shares "
                         "this discovery rectangle in the supplied snapshot.")
        notes += ["","## Original trained station FCMs",""]
        for s in members:
            model=full[s["panel_id"]]
            if not model["status"].startswith("trained_"):
                notes.append("- "+s["site_id"]+": no trained FCM")
                continue
            folder=models/_validated_relative_path(model["model_directory"])
            notes.append(
                f"- **{s['site_id']}**: "
                f"[station FCM SVG]({_relative_link(folder/'visuals/network.svg',root)}) · "
                f"[FINDINGS]({_relative_link(folder/'FINDINGS.md',root)}) · "
                f"[source lineage]({_relative_link(folder/'DATA.md',root)})")
        notes += ["","## Subsystems (screening only)",""]
        for cat in CATEGORIES:
            cat_dir=root/"subsystems"/cat
            cat_dir.mkdir(parents=True,exist_ok=True)
            subset=[s for s in scoped if s["scope_level"]=="category"
                    and s["scope"]==cat]
            subscopes=sorted({s["scope"] for s in scoped
                              if s["scope_level"]=="subcategory"
                              and s["scope"].startswith(cat+"/")})
            text=[
                f"# {region} / {cat} — spatial concept screening","",
                "**REGION-SUBSYSTEM FCM NOT TRAINED.**","",
                "Observed candidate pairs: "+
                str(len({s["pair_id"] for s in subset}))+".",
                "These are compatible input checks, not fitted cross-station "
                "edge weights or causal water connections.","",
                "## Candidate pair statuses","",
            ]
            for item in subset:
                text.append(f"- {item['site_a']} / {item['site_b']}: "
                            f"{item['n_scope_compatible_concepts']} "
                            f"compatible concepts, "
                            f"{item['n_common_one_day_transitions']} "
                            f"shared one-day transitions; "
                            f"`{item['spatial_candidate_status']}`")
            if not subset:
                text.append("No observed pair for this subsystem in this rectangle.")
            text += ["","## Observed subcategories",""]
            for scope in subscopes:
                sub=scope.split("/",1)[1]
                dest=cat_dir/sub
                dest.mkdir(parents=True,exist_ok=True)
                lines=[f"# {region} / {cat} / {sub}","",
                    "**REGIONAL SUBCATEGORY FCM NOT TRAINED.**","",
                    "Only measured station-relationship eligibility is "
                    "documented; no trained interstation arrows.",""]
                for item in scoped:
                    if item["scope_level"]=="subcategory" and item["scope"]==scope:
                        lines.append(
                            f"- Pair {item['pair_id']}: "
                            f"{item['n_scope_compatible_concepts']} compatible "
                            f"concepts, status "
                            f"`{item['spatial_candidate_status']}`")
                (dest/"FINDINGS.md").write_text(
                    "\n".join(lines)+"\n",encoding="utf-8")
                text.append(f"- [{sub}]({sub}/FINDINGS.md)")
            if not subscopes:
                text.append("No observed shared-concept subcategory pairs.")
            (cat_dir/"FINDINGS.md").write_text(
                "\n".join(text)+"\n",encoding="utf-8")
            notes.append(f"- [{cat}](subsystems/{cat}/FINDINGS.md)")
        (root/"FINDINGS.md").write_text(
            "\n".join(notes)+"\n",encoding="utf-8")
        index.append(
            f"- [{region.replace('_',' ').title()}](regions/{region}/FINDINGS.md)"
            f" — {row['n_distinct_observed_stations_in_envelope']} "
            f"source-located site(s); {row['n_unique_screened_station_pairs']} "
            "unique pair(s)")
    index += [
        "","## Scientific constraints","",
        "The same pair can be described in multiple overlapping discovery "
        "rectangles but only once in the global independent-station ledger.",
        "Geographic proximity and simultaneous measurements are NOT "
        "hydrological connectivity or a trained regional FCM.",
        "Gage height without a documented common geodetic datum is "
        "not physically comparable across stations.",
        "Region readiness depends on accumulated day-to-day aligned "
        "transitions; longest unbroken run is a separate reported metric.",
        "At least three independent stations, source QA, reviewed "
        "connectivity and spatial holdouts are still required for "
        "regional FCM research.",
        "","[Earlier M9 region readiness]"
        f"({_relative_link(models.parent.parent/'m9/regional_readiness_v1_with_coords/INDEX.md',out)}) "
        "(when that artifact is available).",
    ]
    (out/"INDEX.md").write_text(
        "\n".join(index)+"\n",encoding="utf-8")
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_model_manifest_sha256":sha256(models/"manifest.json"),
        "input_panel_roots":[str(Path(p)) for p in panels],
        **coord_provenance,
        "n_original_sites":len(site_rows),
        "n_unique_independent_station_pairs":len(candidate_pairs),
        "n_geographic_screening_candidates":sum(
            p["geographic_candidate"] for p in candidate_pairs),
        "n_unique_pairs_in_shared_rectangles":sum(
            bool(p["shared_discovery_regions"]) for p in candidate_pairs),
        "n_alternate_inventory_identifiers_skipped":sum(
            x["reason"]=="alternate_agency_prefixed_identifier_not_a_panel_key"
            for x in audit) if stations else None,
        "max_distance_km_proximity_screen_only":max_distance_km,
        "min_accumulated_aligned_one_day_transitions":min_pairs,
        "min_verified_compatible_concepts":min_concepts,
        "n_regional_fcms_trained":0,
        "n_regional_subsystem_fcms_trained":0,
        "n_confirmed_hydrological_connectivity_edges":0,
        "no_new_agency_requests":True,
        "source_files_untouched":True,
    }
    (out/"manifest.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",type=Path,required=True)
    p.add_argument("--panels",type=Path,action="append",required=True)
    p.add_argument("--assignments",type=Path,
                   help="Prior source-verified M9 station_assignments.csv")
    p.add_argument("--stations",type=Path,
                   help="Local full agency station inventory; alternative to --assignments")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-distance-km",type=float,default=30)
    p.add_argument("--min-pairs",type=int,default=79)
    p.add_argument("--min-concepts",type=int,default=2)
    p.add_argument("--dpi",type=int,default=140)
    a=p.parse_args()
    result=run(a.models,a.panels,a.out,a.assignments,a.stations,
               a.max_distance_km,a.min_pairs,a.min_concepts,a.dpi)
    print(f"{result['n_unique_independent_station_pairs']} unique site pairs; "
          f"{result['n_geographic_screening_candidates']} screened geographic "
          "candidates; 0 regional FCMs trained.")
    print("Browse",a.out/"INDEX.md")


if __name__=="__main__":
    main()
