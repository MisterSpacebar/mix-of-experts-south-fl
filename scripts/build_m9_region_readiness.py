"""M9: geographic-region evidence browser and spatial modeling readiness.

This is an offline, read-only audit of verified daily panels and already
fitted station FCMs. Does not train/construct regional FCMs or assume
discovery rectangles are watersheds or transport routes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from itertools import combinations

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.regions import REGIONS
from southfl.m9_regions import (
    STATION_COLS,PAIR_COLS,SCOPE_COLS,COVERAGE_COLS,REGION_COLS,
    station_lookup,station_evidence,pair_evidence,summarize_scope,
    regional_scope_specs,parse_semicolon_map)
from visuals.hierarchy import classify, CATEGORIES
from visuals.m9_geography import (
    observed_concept_network, region_timeline,scope_counts,discovery_bbox)

READINESS_MIN_STATIONS=3


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _check_sha(path,expected):
    """Accept only same content, or Git's LF↔CRLF-only text normalization."""
    content=Path(path).read_bytes()
    variants=(content,
              content.replace(b"\r\n",b"\n"),
              content.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n"))
    if not any(hashlib.sha256(x).hexdigest()==expected for x in variants):
        raise ValueError("panel SHA256 mismatch (not line-ending-equivalent): "+
                         str(path))


def _relative_link(target,folder):
    return Path(os.path.relpath(Path(target),Path(folder))).as_posix()


def _validated_relative_path(s):
    p=Path(s)
    if p.is_absolute() or not p.parts or any(x in ("..",".") for x in p.parts):
        raise ValueError("unsafe trained model relative directory")
    if ":" in s or "\\" in s:
        raise ValueError("unsafe trained model directory format")
    return p


def _known_readiness(panels):
    matched={}
    for folder in map(Path,panels):
        manifest=json.loads((folder/"panels_manifest.json").read_text(encoding="utf-8"))
        if not manifest.get("observations_sha256"):
            raise ValueError("missing source observation lineage in daily panel manifest")
        rows=read_csv(folder/"panel_readiness.csv")
        for row in rows:
            pid=row["panel_id"]
            if pid in matched:
                raise ValueError("duplicate panel IDs; refuse silent snapshot reuse")
            file=folder/(pid+".csv")
            if not file.exists():
                raise ValueError("daily observed panel missing: "+str(file))
            matched[pid]=(row,file)
    return matched


def _trained_registry(models,source_panels):
    registry=read_csv(models/"model_registry.csv")
    full={}
    for r in registry:
        pid=r["panel_id"]
        if pid not in source_panels:
            raise ValueError("model registry panel missing from supplied sources: "+pid)
        readiness,file=source_panels[pid]
        if r["site_id"]!=readiness["site_id"] or r["region"]!=readiness["region"]:
            raise ValueError("trained registry/source site or region mismatch")
        if r.get("panel_sha256"):
            _check_sha(file,r["panel_sha256"])
        if r["level"]=="dataset":
            if pid in full:
                raise ValueError("duplicate dataset model for panel")
            full[pid]=r
        if r["status"].startswith("trained_"):
            directory=models/_validated_relative_path(r["model_directory"])
            if not (directory/"fcm_model.json").exists():
                raise ValueError("missing claimed station trained FCM: "+str(directory))
    if not full or set(full)!=set(source_panels):
        raise ValueError("dataset models and daily source panel set differ")
    return registry,full


def run(models,panels,out,stations=None,min_sites=3,min_overlap_days=79,dpi=140):
    models,out=Path(models),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new or empty output directory required")
    if not 2<=min_sites<=12 or not 2<=min_overlap_days<=366 or not 40<=dpi<=600:
        raise ValueError("invalid regional readiness limits")
    source=_known_readiness(panels)
    registry,full=_trained_registry(models,source)
    inventory=station_lookup(read_csv(stations)) if stations is not None else {}
    site_records=[]
    unique_site_ids=set()
    for pid,(readiness,file) in sorted(source.items()):
        if readiness["status"]!="candidate_for_held_out_evaluation":
            # Only station panels actually eligible for the M8 training
            # snapshot are given geographic evidence membership.
            if full[pid]["status"].startswith("trained_"):
                raise ValueError("trained station has inconsistent readiness")
        r=station_evidence(readiness,read_csv(file),inventory)
        r["panel_sha256"]=sha256(file)
        if r["site_id"] in unique_site_ids:
            raise ValueError("same canonical site in multiple panels; "
                             "not two independent spatial stations")
        unique_site_ids.add(r["site_id"])
        site_records.append(r)
    grouped=defaultdict(list)
    for row in site_records:
        grouped[row["region"]].append(row)
    out.mkdir(parents=True,exist_ok=True)
    clean_stations=[{k:r[k] for k in STATION_COLS} for r in site_records]
    write_csv(out/"station_assignments.csv",clean_stations,STATION_COLS)

    all_pairs=[];all_scopes=[];all_coverage=[];region_rows=[]
    index=["# Milestone 9 — geographic FCM evidence and readiness","",
           "**REGIONAL FCMs NOT TRAINED.** No station pooling, "
           "synthetic spatial edges or learned regional gating occurred.","",
           f"Observed station panels: {len(site_records)}; "
           f"distinct canonical sites: {len(unique_site_ids)}.",
           f"Discovery regions in registry: {len(REGIONS)}.",
           f"Required independent sites per regional design gate: {min_sites}.",
           f"Required consecutive shared complete UTC days: {min_overlap_days}.","",
           "## Geographic screening regions",""]
    for region in REGIONS:
        sites=sorted(grouped[region],key=lambda r:r["site_id"])
        region_dir=out/"regions"/region
        region_dir.mkdir(parents=True,exist_ok=True)
        sitepairs=[pair_evidence(a,b) for a,b in combinations(sites,2)]
        all_pairs.extend(sitepairs)
        scoped=[]
        for level,scope in regional_scope_specs(sites):
            s=summarize_scope(region,level,scope,sites,registry,sitepairs,
                              min_sites,min_overlap_days)
            scoped.append(s)
        all_scopes.extend(scoped)
        coverage=[]
        for site in sites:
            for c in site["_concepts"]:
                units=parse_semicolon_map(
                    site["_metadata"].get("concept_units",""))
                datum=parse_semicolon_map(
                    site["_metadata"].get("concept_datums",""))
                cat,sub=classify(c)
                coverage.append({
                    "region":region,"site_id":site["site_id"],
                    "panel_id":site["panel_id"],"concept":c,
                    "category":cat,"subcategory":sub,
                    "unit":units.get(c,""),"reported_vertical_datum":datum.get(c,""),
                    "n_observed_days":len(site["_dates"]),
                    "first_day":site["first_day"],"last_day":site["last_day"],
                })
        all_coverage.extend(coverage)
        write_csv(region_dir/"observed_stations.csv",
                  [{k:s[k] for k in STATION_COLS} for s in sites],STATION_COLS)
        write_csv(region_dir/"observed_concepts.csv",coverage,COVERAGE_COLS)
        write_csv(region_dir/"station_overlap_pairs.csv",sitepairs,PAIR_COLS)
        write_csv(region_dir/"regional_scope_readiness.csv",scoped,SCOPE_COLS)
        viz=region_dir/"visuals";viz.mkdir(parents=True,exist_ok=True)
        (viz/"observed_station_concept_graph.svg").write_text(
            observed_concept_network(sites,region),encoding="utf-8")
        region_timeline(sites,viz/"observed_daily_timeline.png",region,dpi)
        discovery_bbox(sites,region,viz/"discovery_rectangle.png",dpi)
        known_coords=sum(s["coordinates_status"]==
                   "verified_point_inside_discovery_rectangle" for s in sites)
        by_status=defaultdict(int)
        for r in registry:
            if (r["site_id"] in {x["site_id"] for x in sites} and
                    r["status"].startswith("trained_")):
                by_status[r["level"]]+=1
        main=next(s for s in scoped if s["level"]=="region")
        region_rows.append({
            "region":region,
            "n_observed_station_panels":len(sites),
            "n_distinct_stations":len({s["site_id"] for s in sites}),
            "n_observed_concepts":len({c for s in sites for c in s["_concepts"]}),
            "n_station_local_fcms":by_status["dataset"],
            "n_station_local_category_fcms":by_status["category"],
            "n_station_local_subcategory_fcms":by_status["subcategory"],
            "n_site_pairs":len(sitepairs),
            "n_pairs_with_required_overlap":main["n_pairs_with_required_overlap"],
            "n_physically_compatible_pairs":main["n_physically_compatible_pairs"],
            "n_verified_station_coordinates":known_coords,
            "geographic_region_fcm_status":"NOT_TRAINED",
            "region_readiness":main["readiness_status"],
        })
        notes=[
            "# "+region.replace("_"," ").title()+
            " — geographic evidence","",
            "**Geographic-region FCM: NOT TRAINED.**",
            "**Geographic status:** `"+main["readiness_status"]+"`.","",
            "This is an overlapping metadata discovery rectangle, "
            "not a verified hydrological region or water transport network.",
            f"Observed station panels: {len(sites)}; independent sites: "
            f"{len({s['site_id'] for s in sites})}.",
            f"Existing independently fitted station FCMs: {by_status['dataset']}.",
            f"Possible station pairs within this region: {len(sitepairs)}.",
            f"Pairs with >= {min_overlap_days} shared consecutive UTC days, "
            f"at least two matching native units, and no missing stage datum "
            f"among selected concepts: {main['n_physically_compatible_pairs']}.",
            f"Verified coordinates from optional inventory: {known_coords}/{len(sites)}.",
            "Hydrological connectivity or flow direction: **not evaluated**.","",
            "## Explore the evidence","",
            "- [Station→measured-concept diagram](visuals/observed_station_concept_graph.svg)"
            " (NOT an FCM node-edge network)",
            "- [Observed daily coverage](visuals/observed_daily_timeline.png)",
            "- [Discovery region envelope and verified station points]"
            "(visuals/discovery_rectangle.png)",
            "- [Stations and source coordinates](observed_stations.csv)",
            "- [Concepts, units and reported vertical datums](observed_concepts.csv)",
            "- [Independent-site overlap and compatibility ledger]"
            "(station_overlap_pairs.csv)",
            "- [Category and subcategory readiness](regional_scope_readiness.csv)","",
            "## Station FCMs already fitted elsewhere","",
        ]
        for site in sites:
            pid=site["panel_id"]
            record=full[pid]
            path=models/_validated_relative_path(record["model_directory"])
            notes += [
                "- **"+site["site_id"]+"** — station FCM "
                f"[node-link SVG]({_relative_link(path/'visuals/network.svg',region_dir)}) · "
                f"[Findings]({_relative_link(path/'FINDINGS.md',region_dir)}) · "
                f"[Source lineage]({_relative_link(path/'DATA.md',region_dir)})"
            ]
        if not sites:
            notes.append("No fitted station panel assigned to this screening region.")
        notes+=["","## Environmental subsystem evidence within region",""]
        for category in CATEGORIES:
            p=region_dir/"subsystems"/category
            p.mkdir(parents=True,exist_ok=True)
            catrow=next(x for x in scoped if x["level"]=="category"
                        and x["scope"]==category)
            subcatrows=[x for x in scoped if x["level"]=="subcategory" and
                        x["scope"].startswith(category+"/")]
            inner=[
                "# "+region+" / "+category+" — regional subsystem evidence","",
                "**REGIONAL SUBSYSTEM FCM: NOT TRAINED.**",
                f"Readiness: `{catrow['readiness_status']}`.",
                f"Independent observed sites: {catrow['n_distinct_stations']}.",
                f"Station-local category FCMs: {catrow['n_station_local_fitted_models']}.",
                f"Compatible multivariate/time-overlapping station pairs: "
                f"{catrow['n_physically_compatible_pairs']}.","",
                "These are station-specialist models, not a geographic "
                "region-specific integrated FCM.","",
                "## Subcategories","",
            ]
            for subrow in subcatrows:
                sub=subrow["scope"].split("/",1)[1]
                subdir=p/sub
                subdir.mkdir(parents=True,exist_ok=True)
                body=[
                    f"# {region} / {category} / {sub}","",
                    "**REGIONAL SUBCATEGORY FCM: NOT TRAINED.**",
                    f"Observed stations: {subrow['n_distinct_stations']}.",
                    f"Unique concepts: {subrow['n_distinct_observed_concepts']}.",
                    f"Existing station-local restricted fits: "
                    f"{subrow['n_station_local_fitted_models']}.",
                    f"Readiness: `{subrow['readiness_status']}`.","",
                    "No cross-station edges have been learned. "
                    "A single-concept subcategory is not mislabelled "
                    "as a trained multivariate station specialist.","",
                    f"[Parent subsystem](../FINDINGS.md) · "
                    f"[Region findings](../../../FINDINGS.md)",
                ]
                (subdir/"FINDINGS.md").write_text("\n".join(body)+"\n",
                                                   encoding="utf-8")
                inner.append(f"- [{sub}]({sub}/FINDINGS.md): "
                             f"{subrow['readiness_status']}")
            if not subcatrows:
                inner.append("No observed concepts currently assigned.")
            inner += ["","[Region findings](../../FINDINGS.md) · "
                      "[Regional data coverage](../../observed_concepts.csv)"]
            (p/"FINDINGS.md").write_text("\n".join(inner)+"\n",
                                        encoding="utf-8")
            notes.append(f"- [{category}](subsystems/{category}/FINDINGS.md): "
                         f"{catrow['readiness_status']}")
        notes+=["","## Geographic modeling gate","",
                "Regional model training must wait for independently "
                "verified station membership, physical connections, "
                "enough synchronized overlapping observations, "
                "measurement units/datums and spatially held-out validation.",
                "The assigned screening region is not proof of connectivity.",
                "No invented regional network weights or causal arrows are drawn."]
        (region_dir/"FINDINGS.md").write_text("\n".join(notes)+"\n",
                                             encoding="utf-8")
        index.append(
            f"- [{region.replace('_',' ').title()}](regions/{region}/FINDINGS.md)"
            f" — {len(sites)} station(s); {main['readiness_status']}")
    write_csv(out/"region_index.csv",region_rows,REGION_COLS)
    write_csv(out/"region_scope_readiness.csv",all_scopes,SCOPE_COLS)
    write_csv(out/"within_region_pairs.csv",all_pairs,PAIR_COLS)
    write_csv(out/"concept_observation_coverage.csv",all_coverage,COVERAGE_COLS)
    viz=out/"visuals";viz.mkdir(parents=True,exist_ok=True)
    scope_counts(region_rows,viz/"regional_station_coverage.png",dpi)
    index += ["","## Global evidence exports","",
        "- [Observed station coverage chart](visuals/regional_station_coverage.png)",
        "- [Region readiness summary](region_index.csv)",
        "- [Every region × environmental subsystem readiness]"
          "(region_scope_readiness.csv)",
        "- [Within-region observed date overlaps](within_region_pairs.csv)",
        "- [Measured concepts/units and datums](concept_observation_coverage.csv)",
        "- [Primary screening-region assignments](station_assignments.csv)","",
        "## Interpretation limits","",
        "Station identities are **not** determined by station-ID coordinate "
        "patterns; use optional verified station inventory for points.",
        "Primary region is the original one selected by the metadata planner. "
        "Multiple overlapping bounding rectangles are not used to make "
        "multiple independent stations or inferred flow edges.",
        "No currently fitted regional FCM, subsystem-in-region model, "
        "or overall South Florida model is asserted.",
        "",
        f"[Prior station-model findings]({_relative_link(models/'INDEX.md',out)})",
    ]
    (out/"INDEX.md").write_text("\n".join(index)+"\n",encoding="utf-8")
    manifest={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_model_manifest_sha256":sha256(models/"manifest.json"),
        "input_panel_folders":[str(Path(p)) for p in panels],
        "station_inventory_source":str(stations) if stations is not None else None,
        "n_screening_regions":len(REGIONS),
        "n_distinct_source_sites":len(unique_site_ids),
        "n_regions_with_an_observed_station":sum(bool(grouped[x]) for x in REGIONS),
        "n_within_region_independent_station_pairs":len(all_pairs),
        "n_trained_geographic_region_fcms":0,
        "n_trained_region_subsystem_fcms":0,
        "n_trained_regional_mixture_gates":0,
        "connected_hydrological_edges_verified":0,
        "region_type":"overlapping_metadata_discovery_rectangles_not_watersheds",
        "no_agency_requests":True,"source_files_modified":False,
        "min_distinct_sites_for_candidate":min_sites,
        "min_shared_consecutive_observation_days":min_overlap_days,
    }
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",
                                     encoding="utf-8")
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",type=Path,required=True,
                   help="Frozen M8 trained model directory")
    p.add_argument("--panels",action="append",type=Path,required=True,
                   help="Original verified daily panel directory; repeatable")
    p.add_argument("--stations",type=Path,default=None,
                   help="Optional local agency station inventory CSV for verified coordinates")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--min-sites",type=int,default=READINESS_MIN_STATIONS)
    p.add_argument("--min-overlap-days",type=int,default=79)
    p.add_argument("--dpi",type=int,default=140)
    a=p.parse_args()
    result=run(a.models,a.panels,a.out,a.stations,a.min_sites,
               a.min_overlap_days,a.dpi)
    print(f"{result['n_distinct_source_sites']} independent observed stations "
          f"across {result['n_regions_with_an_observed_station']} screening regions; "
          f"{result['n_within_region_independent_station_pairs']} within-region "
          "station pairs; 0 regional FCMs trained")
    print("Browse",a.out/"INDEX.md")


if __name__=="__main__":
    main()
