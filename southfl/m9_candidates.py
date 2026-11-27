"""Milestone 9.1: spatial candidate screening, never a learned regional FCM.

Discovery envelopes may overlap and stations can be close while remaining
hydrologically disconnected. A pair receives exactly one canonical pair ID,
even if it belongs to several discovery rectangles. Consecutive one-day
transitions are accumulated across real gaps; gaps are never interpolated.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from itertools import combinations
from math import isfinite

from .regions import REGIONS, regions_for
from .m9_regions import (STAGE_CONCEPTS, haversine_km, longest_streak,
                         parse_semicolon_map, station_lookup)
from visuals.hierarchy import classify, CATEGORIES

PAIR_COLS = [
    "pair_id", "site_a", "site_b", "panel_a", "panel_b",
    "primary_region_a", "primary_region_b", "shared_discovery_regions",
    "n_shared_discovery_regions", "same_primary_region",
    "coordinate_status", "distance_km", "spatial_screening_basis",
    "geographic_candidate", "n_common_observed_days",
    "n_common_one_day_transitions", "longest_contiguous_common_days",
    "first_common_date", "last_common_date",
    "n_common_concepts", "common_concepts",
    "n_same_unit_concepts", "n_datum_unverified_concepts",
    "n_compatible_concepts", "compatible_concepts",
    "datum_unverified_concepts", "incompatible_concepts",
    "hydrological_connectivity", "regional_model_status",
]
SCOPE_COLS = [
    "pair_id", "scope_level", "scope", "site_a", "site_b",
    "shared_discovery_regions", "geographic_candidate",
    "n_scope_shared_concepts", "scope_shared_concepts",
    "n_scope_compatible_concepts", "scope_compatible_concepts",
    "n_common_observed_days", "n_common_one_day_transitions",
    "longest_contiguous_common_days", "n_unverified_stage_datums",
    "scope_unverified_stage_datums", "spatial_candidate_status",
    "regional_expert_status",
]
REGION_COLS = [
    "candidate_region", "n_distinct_observed_stations_in_envelope",
    "n_unique_screened_station_pairs", "n_pairs_with_two_compatible_concepts",
    "n_pairs_with_enough_one_day_transitions",
    "n_pairs_pending_connectivity_review", "n_overlapping_primary_region_pairs",
    "regional_fcm_trained", "interpretation",
]
INVENTORY_AUDIT_COLS = [
    "site_id", "dataset_id", "reason", "source_url",
]
SHORTLIST_COLS = [
    "rank", "target_region", "site_id", "site_name",
    "latitude", "longitude", "n_candidate_concepts",
    "candidate_concepts", "nearest_existing_site",
    "nearest_existing_site_distance_km", "n_concepts_matching_nearest",
    "reported_units_matching_nearest", "source_series_metadata_status",
    "geography_status", "physical_connectivity_status",
    "station_excluded_from_training", "review_note",
]


def dates_summary(a, b):
    """Count transitions for which BOTH stations observed day t-1 and t."""
    common = a & b
    ordered = sorted(common)
    transitions = sum((day-previous).days == 1
                      for previous, day in zip(ordered, ordered[1:]))
    return {
        "n_common_observed_days": len(common),
        "n_common_one_day_transitions": transitions,
        "longest_contiguous_common_days": longest_streak(common),
        "first_common_date": ordered[0].isoformat() if ordered else "",
        "last_common_date": ordered[-1].isoformat() if ordered else "",
    }


def candidate_regions(site):
    """Prefer only metadata-backed point-in-envelope locations."""
    if site["latitude"] == "" or site["longitude"] == "":
        return set()
    actual = set(regions_for(float(site["latitude"]), float(site["longitude"])))
    recorded = set(filter(None, site["candidate_discovery_regions"].split(";")))
    if recorded and recorded != actual:
        raise ValueError("saved region membership differs from verified point geometry")
    return actual


def pair_id(a, b):
    ids = sorted([a["site_id"], b["site_id"]])
    if ids[0] == ids[1]:
        raise ValueError("same station cannot form a spatial pair")
    return "__".join(ids)


def source_metadata(site, concept):
    meta = site["_metadata"]
    unit = parse_semicolon_map(meta.get("concept_units", "")).get(concept, "")
    datum = parse_semicolon_map(meta.get("concept_datums", "")).get(concept, "")
    return unit, datum


def concept_checks(a, b, concepts):
    compatible, datum_unknown, incompatible, unit_matched = [], [], [], []
    for concept in concepts:
        ua, da = source_metadata(a, concept)
        ub, db = source_metadata(b, concept)
        if not ua or not ub or ua != ub:
            incompatible.append(concept + ":incompatible_or_missing_units")
        else:
            unit_matched.append(concept)
            if concept in STAGE_CONCEPTS and (not da or not db):
                datum_unknown.append(concept)
            elif concept in STAGE_CONCEPTS and da != db:
                incompatible.append(concept + ":different_reported_datum")
            else:
                compatible.append(concept)
    return compatible, datum_unknown, incompatible, unit_matched


def assess_pair(a, b, max_distance_km=30):
    """All independent observed pairs are audited; geography is a filter.

    Distance and shared rectangles are screening evidence ONLY, neither
    watershed membership nor causal arrows nor implied transport direction.
    """
    if max_distance_km <= 0 or max_distance_km > 250:
        raise ValueError("distance screening bound must be (0,250] km")
    pid = pair_id(a, b)
    regions_a, regions_b = candidate_regions(a), candidate_regions(b)
    common_regions = sorted(regions_a & regions_b)
    coordinates = (a["latitude"] != "" and a["longitude"] != "" and
                   b["latitude"] != "" and b["longitude"] != "")
    if coordinates:
        dist = haversine_km((float(a["latitude"]), float(a["longitude"])),
                            (float(b["latitude"]), float(b["longitude"])))
        if not isfinite(dist):
            raise ValueError("non-finite station distance")
        basis = ("overlapping_discovery_rectangles" if common_regions else
                 "within_proximity_screen_only" if dist <= max_distance_km
                 else "distant_without_shared_discovery_rectangle")
    else:
        dist = ""
        basis = ("same_primary_region_coordinates_unverified" if
                 a["region"] == b["region"] else
                 "coordinates_missing_no_cross_region_screening")
    eligible = (bool(common_regions) or
                (coordinates and dist <= max_distance_km) or
                (not coordinates and a["region"] == b["region"]))
    concepts = sorted(set(a["_concepts"]) & set(b["_concepts"]))
    compatible, unverified, incompatible, same_unit = concept_checks(
        a, b, concepts)
    return {
        "pair_id": pid, "site_a": a["site_id"], "site_b": b["site_id"],
        "panel_a": a["panel_id"], "panel_b": b["panel_id"],
        "primary_region_a": a["region"], "primary_region_b": b["region"],
        "shared_discovery_regions": ";".join(common_regions),
        "n_shared_discovery_regions": len(common_regions),
        "same_primary_region": a["region"] == b["region"],
        "coordinate_status": ("both_source_inventory_points" if coordinates
                              else "one_or_both_coordinates_unverified"),
        "distance_km": dist,
        "spatial_screening_basis": basis,
        "geographic_candidate": eligible,
        **dates_summary(a["_dates"], b["_dates"]),
        "n_common_concepts": len(concepts),
        "common_concepts": ";".join(concepts),
        "n_same_unit_concepts": len(same_unit),
        "n_datum_unverified_concepts": len(unverified),
        "n_compatible_concepts": len(compatible),
        "compatible_concepts": ";".join(compatible),
        "datum_unverified_concepts": ";".join(unverified),
        "incompatible_concepts": ";".join(incompatible),
        "hydrological_connectivity": "NOT_VERIFIED",
        "regional_model_status": "NOT_TRAINED",
    }


def _scopes(common):
    groups = [("region", "all_environmental_categories")]
    cats = sorted({classify(c)[0] for c in common})
    groups.extend(("category", cat) for cat in cats)
    groups.extend(("subcategory", cat + "/" + sub) for cat, sub in
                  sorted({classify(c) for c in common}))
    return groups


def assess_scopes(pair, min_pairs=79, min_concepts=2):
    if min_pairs < 1 or min_concepts < 2:
        raise ValueError("minimum pair/concept eligibility must be positive")
    shared = set(filter(None, pair["common_concepts"].split(";")))
    compatible = set(filter(None, pair["compatible_concepts"].split(";")))
    unverified = set(filter(None, pair["datum_unverified_concepts"].split(";")))
    rows = []
    for level, scope in _scopes(shared):
        def belongs(concept):
            category, subcategory = classify(concept)
            return level == "region" or (
                category == scope if level == "category" else
                category + "/" + subcategory == scope
            )
        found = sorted(c for c in shared if belongs(c))
        valid = sorted(c for c in compatible if belongs(c))
        unclear = sorted(c for c in unverified if belongs(c))
        if not pair["geographic_candidate"]:
            status = "no_shared_screening_geometry_or_nearby_station"
        elif pair["coordinate_status"] != "both_source_inventory_points":
            status = "source_coordinates_required"
        elif len(valid) < min_concepts:
            status = "insufficient_verified_same_unit_concepts"
        elif pair["n_common_one_day_transitions"] < min_pairs:
            status = "insufficient_aligned_one_day_transitions"
        else:
            status = "candidate_only_pending_connectivity_and_spatial_validation"
        rows.append({
            "pair_id": pair["pair_id"], "scope_level": level, "scope": scope,
            "site_a": pair["site_a"], "site_b": pair["site_b"],
            "shared_discovery_regions": pair["shared_discovery_regions"],
            "geographic_candidate": pair["geographic_candidate"],
            "n_scope_shared_concepts": len(found),
            "scope_shared_concepts": ";".join(found),
            "n_scope_compatible_concepts": len(valid),
            "scope_compatible_concepts": ";".join(valid),
            "n_common_observed_days": pair["n_common_observed_days"],
            "n_common_one_day_transitions": pair["n_common_one_day_transitions"],
            "longest_contiguous_common_days":
                pair["longest_contiguous_common_days"],
            "n_unverified_stage_datums": len(unclear),
            "scope_unverified_stage_datums": ";".join(unclear),
            "spatial_candidate_status": status,
            "regional_expert_status": "NOT_TRAINED",
        })
    return rows


def summarize_discovery_regions(sites, pairs, scopes, min_pairs=79):
    """One row per discovery rectangle, but pair IDs are globally unique."""
    group_members = {reg: set() for reg in REGIONS}
    for station in sites:
        for reg in candidate_regions(station):
            group_members[reg].add(station["site_id"])
    rows = []
    for reg in REGIONS:
        in_region = [p for p in pairs
                     if reg in p["shared_discovery_regions"].split(";")]
        pids = {p["pair_id"] for p in in_region}
        region_scope = [s for s in scopes if s["pair_id"] in pids and
                        s["scope_level"] == "region"]
        rows.append({
            "candidate_region": reg,
            "n_distinct_observed_stations_in_envelope": len(group_members[reg]),
            "n_unique_screened_station_pairs": len(pids),
            "n_pairs_with_two_compatible_concepts": sum(
                int(p["n_compatible_concepts"]) >= 2 for p in in_region),
            "n_pairs_with_enough_one_day_transitions": sum(
                int(p["n_common_one_day_transitions"]) >= min_pairs
                for p in in_region),
            "n_pairs_pending_connectivity_review": sum(
                x["spatial_candidate_status"] ==
                "candidate_only_pending_connectivity_and_spatial_validation"
                for x in region_scope),
            "n_overlapping_primary_region_pairs": sum(
                p["primary_region_a"] != p["primary_region_b"]
                for p in in_region),
            "regional_fcm_trained": False,
            "interpretation": "overlapping metadata discovery rectangle; "
                "same station pair may appear in multiple rectangles, "
                "never an independent duplicate or confirmed water connection",
        })
    return rows


def inventory_audit(rows, required=None):
    """Audit alternate namespaces; skip safe but preserve the reason/number."""
    audit=[]
    for row in rows:
        if row.get("dataset_id") != "usgs_water":
            continue
        sid=row.get("site_id", "")
        if not sid.startswith("USGS-"):
            audit.append({
                "site_id": sid, "dataset_id": "usgs_water",
                "reason": "alternate_agency_prefixed_identifier_not_a_panel_key",
                "source_url": row.get("source_url", ""),
            })
        elif not row.get("latitude") or not row.get("longitude"):
            audit.append({
                "site_id": sid, "dataset_id": "usgs_water",
                "reason": "canonical_site_missing_coordinates",
                "source_url": row.get("source_url", ""),
            })
    lookup = station_lookup(rows)
    if required:
        for sid in sorted(set(required) - set(lookup)):
            audit.append({
                "site_id": sid, "dataset_id": "usgs_water",
                "reason": "modeled_station_not_resolved_in_coordinate_inventory",
                "source_url": "",
            })
    return lookup,audit
