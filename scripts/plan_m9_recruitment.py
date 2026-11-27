"""Plan bounded, metadata-only recruitment around M9 source-located sites.

Candidate metadata period-of-record is NOT observed daily coverage.
Proximity to a monitoring station is NOT hydrological connection.
Produces an existing-schema history_plan.csv usable by M8 batch planning;
live exact-series preflight remains mandatory before any download.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date,timedelta,datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.regions import REGIONS,regions_for
from southfl.history_selection import PLAN_COLS,CONCEPT_ORDER,select_panels
from southfl.m9_regions import haversine_km,parse_semicolon_map,STAGE_CONCEPTS
from southfl.m9_candidates import inventory_audit,INVENTORY_AUDIT_COLS
from scripts.build_m9_region_readiness import _known_readiness,_check_sha

SHORTLIST_COLS=[
    "rank","site_id","site_name","target_discovery_region",
    "latitude","longitude","nearest_existing_modeled_site",
    "nearest_distance_km","metadata_covered_concepts",
    "n_metadata_covered_concepts","n_common_reported_unit_concepts",
    "n_common_with_verified_stage_reference",
    "n_missing_stage_datum_concepts","source_metadata_window_start",
    "source_metadata_window_end","selected_into_history_plan",
    "review_status",
]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shortlist(periods,stations,assignments,region,end,days=180,
              max_distance_km=60,min_concepts=3,reference_readiness=None):
    if region not in REGIONS:
        raise ValueError("unknown target discovery region")
    if not 60<=days<=366 or not 0<max_distance_km<=250:
        raise ValueError("bad observation planning window or proximity limit")
    start=date.fromisoformat(end)-timedelta(days=days-1)
    enddate=date.fromisoformat(end)
    known={}
    for row in assignments:
        site=row["site_id"]
        if site in known:
            raise ValueError("duplicate modeled source station in M9 assignment")
        if not site.startswith("USGS-"):
            raise ValueError("modeled reference station must use canonical USGS ID")
        if reference_readiness is not None:
            if row["panel_id"] not in reference_readiness:
                raise ValueError("reference coordinate assignment lacks original panel")
            observed=reference_readiness[row["panel_id"]]
            if (observed["site_id"]!=site or observed["region"]!=row["region"]):
                raise ValueError("reference coordinate assignment/site mismatch")
            row=dict(row,concept_units=observed["concept_units"],
                     concept_datums=observed["concept_datums"])
        known[site]=row
    reference=[]
    for row in known.values():
        if row.get("coordinates_status")!="verified_point_inside_discovery_rectangle":
            continue
        if not row.get("latitude") or not row.get("longitude"):
            continue
        at=set(regions_for(row["latitude"],row["longitude"]))
        if region in at:
            reference.append(row)
    if not reference:
        raise ValueError("no source-located modeled reference station in target "
                         "discovery region; cannot compute proximity shortlist")
    inventory,audit=inventory_audit(stations,required=set(known))
    # Restrict by source coordinates, not merely a stale inventory
    # list of coarse discovery labels. No fabricated location.
    eligible={}
    for sid,row in inventory.items():
        if sid in known:
            continue
        if region not in regions_for(row["latitude"],row["longitude"]):
            continue
        nearest=min(reference,key=lambda r:haversine_km(
            (float(row["latitude"]),float(row["longitude"])),
            (float(r["latitude"]),float(r["longitude"]))))
        distance=haversine_km(
            (float(row["latitude"]),float(row["longitude"])),
            (float(nearest["latitude"]),float(nearest["longitude"])))
        if distance>max_distance_km:
            continue
        eligible[sid]=(row,nearest,distance)
    options=defaultdict(lambda:defaultdict(list))
    for record in periods:
        sid=record.get("site_id")
        if (record.get("dataset_id")!="usgs_water" or sid not in eligible or
                record.get("concept") not in CONCEPT_ORDER or
                record.get("evidence")!="time_series_first_last_metadata"):
            continue
        code=record.get("parameter_code","")
        if len(code)!=5 or not code.isdigit() or not record.get("series_id"):
            continue
        try:
            left=date.fromisoformat(record["begin_utc"][:10])
            right=date.fromisoformat(record["end_utc"][:10])
        except (KeyError,ValueError):
            continue
        if left<=start and right>=enddate:
            options[sid][record["concept"]].append(record)
    rows=[]
    for sid,concept_options in sorted(options.items()):
        if len(concept_options)<min_concepts:
            continue
        original,reference,dist=eligible[sid]
        units=parse_semicolon_map(reference.get("concept_units",""))
        datums=parse_semicolon_map(reference.get("concept_datums",""))
        shared=[];verified=[];missing=[]
        for concept,items in sorted(concept_options.items()):
            # Same deterministic primary/longest selection rule as
            # the existing metadata-only plan, never observation data.
            source=sorted(items,key=lambda r:(
                str(r.get("primary_status","")).lower()
                    not in ("primary","true","1"),
                r.get("sublocation_identifier","") not in ("","main"),
                r["begin_utc"],r["series_id"]))[0]
            if source.get("unit","") and source["unit"]==units.get(concept):
                shared.append(concept)
                if concept in STAGE_CONCEPTS and (
                        not source.get("vertical_datum") or
                        not datums.get(concept)):
                    missing.append(concept)
                elif concept in STAGE_CONCEPTS and (
                        source["vertical_datum"]!=datums[concept]):
                    continue
                else:
                    verified.append(concept)
        rows.append({
            "rank":0,"site_id":sid,
            "site_name":original.get("site_name",""),
            "target_discovery_region":region,
            "latitude":original["latitude"],"longitude":original["longitude"],
            "nearest_existing_modeled_site":reference["site_id"],
            "nearest_distance_km":dist,
            "metadata_covered_concepts":";".join(sorted(concept_options)),
            "n_metadata_covered_concepts":len(concept_options),
            "n_common_reported_unit_concepts":len(shared),
            "n_common_with_verified_stage_reference":len(verified),
            "n_missing_stage_datum_concepts":len(missing),
            "source_metadata_window_start":start.isoformat(),
            "source_metadata_window_end":enddate.isoformat(),
            "selected_into_history_plan":False,
            "review_status":"metadata_only_requires_live_series_identity_and_observed_QA",
        })
    rows.sort(key=lambda r:(
        -r["n_common_with_verified_stage_reference"],
        r["nearest_distance_km"],
        -r["n_metadata_covered_concepts"],r["site_id"]))
    for i,row in enumerate(rows,1):
        row["rank"]=i
    return rows,audit


def run(periods,stations,assignments,panels,region,end,days,out,max_panels=6,
        max_concepts=4,max_distance_km=60,min_concepts=3):
    periods,stations,assignments,out=map(
        Path,(periods,stations,assignments,out))
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty recruitment output required")
    if not 1<=max_panels<=8 or not 2<=min_concepts<=max_concepts<=8:
        raise ValueError("invalid panel/concept quotas")
    observed_assignments=read_csv(assignments)
    originals=_known_readiness(panels)
    reference_readiness={key:value[0] for key,value in originals.items()}
    for row in observed_assignments:
        original=originals.get(row["panel_id"])
        if original is None:
            raise ValueError("saved coordinate assignment missing observed source")
        _check_sha(original[1],row["panel_sha256"])
    if len(observed_assignments)!=len(originals):
        raise ValueError("reference assignment and observed snapshot set differ")
    source_stations=read_csv(stations)
    source_periods=read_csv(periods)
    ranked,audit=shortlist(
        source_periods,source_stations,observed_assignments,
        region,end,days,max_distance_km,min_concepts,reference_readiness)
    if not ranked:
        raise ValueError("no metadata-eligible nearby new station candidates")
    sites={r["site_id"] for r in ranked[:max_panels]}
    # Uses the existing exact-source metadata history planner and schema.
    # Reconcile IDs, then download observed-only history in bounded batches.
    selected=select_panels(
        source_periods,source_stations,end,days,
        max_panels=max_panels,max_concepts=max_concepts,
        min_concepts=min_concepts,site_filter=sites,
        exclude_sites={r["site_id"] for r in observed_assignments},
        region_filter={region})
    if not selected:
        raise ValueError("site shortlist produced no valid history plan")
    chosen={r["site_id"] for r in selected}
    for r in ranked:
        r["selected_into_history_plan"]=r["site_id"] in chosen
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"metadata_recruitment_shortlist.csv",ranked,SHORTLIST_COLS)
    write_csv(out/"history_plan.csv",selected,PLAN_COLS)
    write_csv(out/"inventory_identifier_exclusions.csv",
              audit,INVENTORY_AUDIT_COLS)
    report={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "target_discovery_region":region,"start":ranked[0]["source_metadata_window_start"],
        "end":end,"days":days,
        "n_metadata_eligible_nearby_station_candidates":len(ranked),
        "n_selected_new_panel_candidates":len(chosen),
        "n_candidate_source_series":len(selected),
        "source_reference_assignments_sha256":_sha(assignments),
        "source_observed_panel_roots":[str(Path(p)) for p in panels],
        "source_inventory_sha256":_sha(stations),
        "source_parameter_periods_sha256":_sha(periods),
        "n_alt_agency_namespace_inventory_exclusions":sum(
            r["reason"]=="alternate_agency_prefixed_identifier_not_a_panel_key"
            for r in audit),
        "max_straight_line_distance_km_screening_only":max_distance_km,
        "station_coordinates_are_from_source_inventory":True,
        "hydrological_connectivity_verified":False,
        "period_of_record_not_observed_coverage":True,
        "identity_preflight_complete":False,
        "observations_downloaded":False,
        "regional_fcms_trained":0,
    }
    (out/"manifest.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    docs=[
        "# Milestone 9.1 — bounded geographic station recruitment","",
        "**Metadata-only plan. No live observations or regional FCMs.**","",
        f"Target discovery rectangle: {region}. "
        f"Period-of-record window: {report['start']} to {end}.",
        f"Existing modeled source-located stations are excluded: "
        f"{len(observed_assignments)}.",
        f"Nearby period-metadata candidates: {len(ranked)}.",
        f"Selected new station panels: {len(chosen)}.","",
        "## Audit/next steps","",
        "- [Ranked local candidates](metadata_recruitment_shortlist.csv)",
        "- [Bounded acquisition-ready metadata plan](history_plan.csv)",
        "- [Excluded legacy/alternate station namespace entries]"
        "(inventory_identifier_exclusions.csv)","",
        "1. Review location, reported units, metadata period dates and "
        "hydrological plausibility of each selected station.",
        "2. Split the history_plan.csv into bounded whole-station requests "
        "with scripts/plan_m8_batches.py.",
        "3. Run scripts/reconcile_fcm_series.py --execute on each batch and "
        "inspect ID/source audit before data retrieval.",
        "4. Use scripts/fetch_fcm_history.py --execute with bounded pacing, "
        "then scripts/build_fcm_panels.py for observed-only QA.",
        "5. Re-run the M8 station-specific model trainer and this M9 "
        "spatial screening before any proposed multistation model.",
        "",
        "Straight-line proximity and coarse discovery envelopes are not "
        "watershed boundaries, flow pathways or evidence of transfer.",
        "The metadata beginning and ending dates DO NOT certify that "
        "observations actually exist for all dates in between.",
    ]
    (out/"README.md").write_text("\n".join(docs)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--periods",type=Path,required=True)
    p.add_argument("--stations",type=Path,required=True)
    p.add_argument("--assignments",type=Path,required=True)
    p.add_argument("--panels",type=Path,action="append",required=True,
                   help="original observed daily panel dirs supplying reference unit/datum metadata")
    p.add_argument("--region",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--days",type=int,default=180)
    p.add_argument("--max-panels",type=int,default=6)
    p.add_argument("--max-concepts",type=int,default=4)
    p.add_argument("--min-concepts",type=int,default=3)
    p.add_argument("--max-distance-km",type=float,default=60)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=run(a.periods,a.stations,a.assignments,a.panels,
               a.region,a.end,a.days,a.out,
               a.max_panels,a.max_concepts,a.max_distance_km,
               a.min_concepts)
    print(f"{result['n_selected_new_panel_candidates']} metadata-only "
          "station acquisition candidates; NO agency requests or FCM fits")
    print("Browse",a.out/"README.md")


if __name__=="__main__":
    main()
