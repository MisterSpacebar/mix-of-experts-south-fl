"""Milestone 9: conservative geographic-region evidence and training readiness.

Regions are overlapping *metadata discovery rectangles*, not watershed
boundaries. This module does NOT train a regional FCM, fit spatial
coefficients, infer flow connections, or pool station matrices.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import radians, sin, cos, asin, sqrt, isfinite

from .regions import REGIONS, regions_for
from visuals.hierarchy import classify, CATEGORIES

MODEL_LEVELS = ("dataset", "subcategory", "category", "region", "overall")
STAGE_CONCEPTS = frozenset({
    "gage_height", "water_level", "stream_stage_elevation",
    "groundwater_elevation", "groundwater_depth_below_land_surface",
})
STATION_COLS = [
    "region","site_id","panel_id","status","screening_region_basis",
    "candidate_discovery_regions","coordinates_status",
    "latitude","longitude","site_name","source_url","concepts",
    "n_concepts","n_complete_days","first_day","last_day",
    "n_consecutive_pairs","panel_sha256","source_approval_status",
]
PAIR_COLS = [
    "region","site_a","site_b","panel_a","panel_b",
    "n_common_observed_days","longest_consecutive_overlap_days",
    "first_common_day","last_common_day",
    "common_concepts","n_common_concepts","compatible_concepts",
    "n_compatible_concepts","unverified_datum_concepts",
    "incompatible_concepts","coordinate_pair_status",
    "distance_km_if_verified","connectivity_status","assessment",
]
SCOPE_COLS = [
    "region","level","scope","n_station_panels","n_distinct_stations",
    "n_distinct_observed_concepts","n_multistation_shared_concepts",
    "n_potential_site_pairs","n_pairs_with_required_overlap",
    "n_physically_compatible_pairs","largest_pair_overlap_days",
    "n_station_local_fitted_models","n_verified_coordinates",
    "has_verified_hydrological_connectivity",
    "readiness_status","regional_fcm_status","interpretation",
]
COVERAGE_COLS = [
    "region","site_id","panel_id","concept","category","subcategory",
    "unit","reported_vertical_datum","n_observed_days","first_day","last_day",
]
REGION_COLS=[
    "region","n_observed_station_panels","n_distinct_stations",
    "n_observed_concepts","n_station_local_fcms",
    "n_station_local_category_fcms","n_station_local_subcategory_fcms",
    "n_site_pairs","n_pairs_with_required_overlap",
    "n_physically_compatible_pairs","n_verified_station_coordinates",
    "geographic_region_fcm_status","region_readiness",
]


def parse_semicolon_map(value):
    result={}
    for part in str(value or "").split(";"):
        if not part:
            continue
        if "=" not in part:
            raise ValueError("invalid concept metadata: expected name=value")
        key,val=part.split("=",1)
        if not key or key in result:
            raise ValueError("duplicate or empty concept metadata key")
        result[key]=val
    return result


def _reported_metadata(row,concept):
    return (
        parse_semicolon_map(row.get("concept_units","")).get(concept,""),
        parse_semicolon_map(row.get("concept_datums","")).get(concept,""),
    )


def _finite_coord(item):
    try:
        lat=float(item["latitude"])
        lon=float(item["longitude"])
    except (ValueError,KeyError,TypeError):
        return None
    if not (isfinite(lat) and isfinite(lon)
            and -90<=lat<=90 and -180<=lon<=180):
        raise ValueError("invalid station WGS84 coordinate")
    return lat,lon


def station_lookup(stations):
    """Review canonical agency-qualified station coordinates, if supplied.

    Inventory rows are optional because inventory/ is gitignored. Never
    fabricate point locations from region rectangles or parse ID digits
    into an unverified geolocation.
    """
    by_site={}
    for item in stations:
        if item.get("dataset_id")!="usgs_water":
            continue
        sid=item.get("site_id","")
        if not sid.startswith("USGS-"):
            raise ValueError("station inventory requires canonical USGS ID")
        coord=_finite_coord(item)
        if coord is None:
            continue
        if sid in by_site and _finite_coord(by_site[sid])!=coord:
            raise ValueError("conflicting canonical USGS coordinates")
        by_site[sid]=item
    return by_site


def station_evidence(readiness,observed_rows,inventory=None):
    """Build observed-date evidence without silently combining snapshots."""
    site_id=readiness["site_id"]
    pid=readiness["panel_id"]
    region=readiness["region"]
    if region not in REGIONS:
        raise ValueError(f"unknown geographic screening region: {region}")
    if not site_id.startswith("USGS-"):
        raise ValueError("requires canonical USGS station ID")
    concepts=[c for c in readiness["concepts"].split(";") if c]
    if len(set(concepts))!=len(concepts) or len(concepts)<1:
        raise ValueError("duplicate/missing measured concepts")
    dates=set()
    for record in observed_rows:
        if record.get("site_id")!=site_id or record.get("panel_id")!=pid:
            raise ValueError("daily observations contain mismatched station/panel")
        day=date.fromisoformat(record["date"])
        if day in dates:
            raise ValueError("duplicate observed UTC day")
        dates.add(day)
        for c in concepts:
            try:
                val=float(record[c])
            except (ValueError,KeyError,TypeError) as exc:
                raise ValueError("missing station daily measurement") from exc
            if not isfinite(val):
                raise ValueError("nonfinite station daily measurement")
    if len(dates)!=int(readiness["n_complete_days"]):
        raise ValueError("observed daily rows disagree with panel readiness")
    info=(inventory or {}).get(site_id)
    coords=_finite_coord(info) if info else None
    candidates=regions_for(*coords) if coords else []
    coordinate_status=(
        "not_supplied" if not coords else
        "screened_region_not_in_coordinate_discovery_rectangles"
        if region not in candidates else
        "verified_point_inside_discovery_rectangle"
    )
    return {
        "region":region,"site_id":site_id,"panel_id":pid,
        "status":readiness["status"],
        "screening_region_basis":"existing_panel_plan_discovery_region_not_watershed",
        "candidate_discovery_regions":";".join(candidates),
        "coordinates_status":coordinate_status,
        "latitude":coords[0] if coords else "",
        "longitude":coords[1] if coords else "",
        "site_name":(info or {}).get("site_name",""),
        "source_url":(info or {}).get("source_url",""),
        "concepts":";".join(concepts),"n_concepts":len(concepts),
        "n_complete_days":len(dates),
        "first_day":min(dates).isoformat() if dates else "",
        "last_day":max(dates).isoformat() if dates else "",
        "n_consecutive_pairs":int(readiness["n_consecutive_daily_pairs"]),
        "panel_sha256":"","source_approval_status":
            "provisional_and_approved_values_may_be_included",
        "_dates":dates,"_metadata":readiness,"_concepts":concepts,
    }


def longest_streak(days):
    longest=run=0
    last=None
    for d in sorted(days):
        if last is not None and (d-last).days==1:
            run+=1
        else:
            run=1
        longest=max(longest,run)
        last=d
    return longest


def haversine_km(a,b):
    lat1,lon1=map(radians,a)
    lat2,lon2=map(radians,b)
    dl=lat2-lat1
    dn=lon2-lon1
    q=sin(dl/2)**2+cos(lat1)*cos(lat2)*sin(dn/2)**2
    return 6371.0088*2*asin(min(1,sqrt(q)))


def pair_evidence(a,b,concept_filter=None):
    if a["region"]!=b["region"]:
        raise ValueError("only within same selected screening region may be paired")
    if a["site_id"]==b["site_id"]:
        raise ValueError("same site is not independent spatial replication")
    concepts=sorted(set(a["_concepts"]) & set(b["_concepts"]))
    if concept_filter is not None:
        concepts=[c for c in concepts if c in concept_filter]
    compatible=[];unverified=[];incompatible=[]
    for c in concepts:
        ua,da=_reported_metadata(a["_metadata"],c)
        ub,db=_reported_metadata(b["_metadata"],c)
        if not ua or ua!=ub:
            incompatible.append(c+":incompatible_or_missing_units")
        elif c in STAGE_CONCEPTS and (not da or not db):
            unverified.append(c)
        elif c in STAGE_CONCEPTS and da!=db:
            incompatible.append(c+":different_vertical_reference")
        else:
            compatible.append(c)
    shared=a["_dates"] & b["_dates"]
    x=a["latitude"];y=b["latitude"]
    coords_ok=x!="" and y!="" and a["longitude"]!="" and b["longitude"]!=""
    if coords_ok:
        distance=haversine_km((float(x),float(a["longitude"])),
                              (float(y),float(b["longitude"])))
    else:
        distance=""
    return {
        "region":a["region"],"site_a":a["site_id"],"site_b":b["site_id"],
        "panel_a":a["panel_id"],"panel_b":b["panel_id"],
        "n_common_observed_days":len(shared),
        "longest_consecutive_overlap_days":longest_streak(shared),
        "first_common_day":min(shared).isoformat() if shared else "",
        "last_common_day":max(shared).isoformat() if shared else "",
        "common_concepts":";".join(concepts),
        "n_common_concepts":len(concepts),
        "compatible_concepts":";".join(compatible),
        "n_compatible_concepts":len(compatible),
        "unverified_datum_concepts":";".join(unverified),
        "incompatible_concepts":";".join(incompatible),
        "coordinate_pair_status":("both_metadata_coordinates_available"
                                  if coords_ok else "station_coordinates_missing"),
        "distance_km_if_verified":distance,
        "connectivity_status":"not_assessed_by_bbox_or_station_distance",
        "assessment":("not_suitable_for_spatial_training_without_connectivity_and_holdout_review"),
    }


def scope_spec(stations,level,scope):
    if level=="region":
        return set(c for s in stations for c in s["_concepts"])
    if level=="category":
        return {c for s in stations for c in s["_concepts"]
                if classify(c)[0]==scope}
    if level=="subcategory":
        cat,sub=scope.split("/",1)
        return {c for s in stations for c in s["_concepts"]
                if classify(c)==(cat,sub)}
    raise ValueError("unsupported regional scope")


def summarize_scope(region,level,scope,stations,models,pairs,min_sites=3,
                    min_overlap_days=79):
    concepts=scope_spec(stations,level,scope)
    members=[s for s in stations if set(s["_concepts"]) & concepts]
    pairs_here=[]
    for p in pairs:
        sub=set(p["common_concepts"].split(";")) & concepts
        valid=set(p["compatible_concepts"].split(";")) & concepts
        # Require TWO mutually compatible observed variables within scope,
        # not merely two individual stations with one shared variable.
        if sub:
            pairs_here.append((p,valid))
    # Qualified pair needs same-scope >=2 concepts, common overlap and
    # 2+ stations; still does NOT verify hydrological connectivity.
    qualified=[p for p,v in pairs_here if
               len(v)>=2 and
               int(p["longest_consecutive_overlap_days"])>=min_overlap_days]
    nsite=len({s["site_id"] for s in members})
    verified=sum(s["coordinates_status"]==
                 "verified_point_inside_discovery_rectangle" for s in members)
    shared_concepts=set()
    counts=defaultdict(int)
    for s in members:
        for c in set(s["_concepts"]) & concepts:
            counts[c]+=1
    shared_concepts={c for c,n in counts.items() if n>=2}
    fitted=[m for m in models if
            m["site_id"] in {s["site_id"] for s in members}
            and ((level=="region" and m["level"]=="dataset") or
                 (level=="category" and m["level"]=="category"
                  and m["category"]==scope) or
                 (level=="subcategory" and m["level"]=="subcategory"
                  and m["category"]+"/"+m["subcategory"]==scope))
            and m["status"].startswith("trained_")]
    if nsite==0:
        status="no_observed_station_panels"
    elif nsite==1:
        status="one_station_only_no_regional_model"
    elif len(shared_concepts)<2:
        status="insufficient_shared_multivariate_concepts"
    elif not qualified:
        status="no_verified_compatible_two_concept_overlap"
    elif nsite<min_sites:
        status="insufficient_independent_stations_for_regional_design"
    elif verified<nsite:
        status="coordinate_verification_required"
    else:
        status="candidate_for_connectivity_and_spatial_holdout_review"
    return {
        "region":region,"level":level,"scope":scope,
        "n_station_panels":len(members),"n_distinct_stations":nsite,
        "n_distinct_observed_concepts":len(concepts),
        "n_multistation_shared_concepts":len(shared_concepts),
        "n_potential_site_pairs":len(pairs_here),
        "n_pairs_with_required_overlap":sum(
            int(p["longest_consecutive_overlap_days"])>=min_overlap_days
            for p,_ in pairs_here),
        "n_physically_compatible_pairs":len(qualified),
        "largest_pair_overlap_days":max(
            (int(p["longest_consecutive_overlap_days"]) for p,_ in pairs_here),
            default=0),
        "n_station_local_fitted_models":len(fitted),
        "n_verified_coordinates":verified,
        "has_verified_hydrological_connectivity":False,
        "readiness_status":status,"regional_fcm_status":"NOT_TRAINED",
        "interpretation":"discovery-region evidence only; station FCMs "
            "are not region FCMs; no verified water transport, pooling, "
            "spatially heldout validation or regional trained network",
    }


def regional_scope_specs(stations):
    groups={("region","all_environmental_categories")}
    groups.update(("category",cat) for cat in CATEGORIES)
    subgroups={classify(c) for s in stations for c in s["_concepts"]}
    groups.update(("subcategory",cat+"/"+sub) for cat,sub in subgroups)
    return sorted(groups)
