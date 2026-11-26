"""Explicit concept-to-subcategory taxonomy for descriptive FCM visual views.

These labels partition *concepts in already-trained station FCMs*; they do
NOT train distinct subcategory/category/overall FCMs, infer hydrological
connectivity, or pool edge weights across stations.

Unrecognized concepts stay unclassified until a reviewed taxonomy update.
"""
from collections import defaultdict
from statistics import median

TAXONOMY_VERSION = "visual_concept_hierarchy_v1"
CATEGORIES = ("hydrology", "water_quality", "oceanography", "ecology",
              "socioeconomic")
# Every concept has ONE primary display category. Model inputs can cross
# these boundaries: this is a reporting view, never a training constraint.
CONCEPT_TAXONOMY = {
    "discharge": ("hydrology", "surface_flow"),
    "gage_height": ("hydrology", "surface_flow"),
    "stream_stage_elevation": ("hydrology", "surface_flow"),
    "water_velocity": ("hydrology", "surface_flow"),
    "groundwater_elevation": ("hydrology", "groundwater"),
    "groundwater_depth_below_land_surface": ("hydrology", "groundwater"),
    "precipitation": ("hydrology", "meteorological_forcing"),
    "rainfall": ("hydrology", "meteorological_forcing"),
    "salinity": ("water_quality", "salinity_and_conductance"),
    "specific_conductance": ("water_quality", "salinity_and_conductance"),
    "conductivity": ("water_quality", "salinity_and_conductance"),
    "water_temperature": ("water_quality", "thermal_conditions"),
    "dissolved_oxygen": ("water_quality", "oxygen_conditions"),
    "ph": ("water_quality", "acid_base"),
    "turbidity": ("water_quality", "clarity_sediments"),
    "total_nitrogen": ("water_quality", "nutrients"),
    "total_phosphorus": ("water_quality", "nutrients"),
    "nitrate": ("water_quality", "nutrients"),
    "phosphorus_unspecified_fraction": ("water_quality", "nutrients"),
    "water_level": ("oceanography", "coastal_water_level"),
    "wind_speed": ("oceanography", "meteorological_forcing"),
    "wave_height": ("oceanography", "wave_conditions"),
    "sea_surface_temperature": ("oceanography", "thermal_conditions"),
    "coral_cover": ("ecology", "coral_condition"),
    "seagrass_cover": ("ecology", "seagrass_condition"),
    "fish_biomass": ("ecology", "fish_communities"),
    "fish_landings": ("socioeconomic", "fisheries_economy"),
}

COVERAGE_COLS = ["category", "subcategory", "n_distinct_concepts",
                 "n_panels", "concepts", "panel_ids", "status"]
EDGE_INDEX_COLS = ["panel_id", "source_concept", "target_concept",
                   "source_category", "source_subcategory",
                   "target_category", "target_subcategory",
                   "weight", "sign", "edge_kind", "view_type"]
STATUS_COLS = ["level", "scope", "status", "n_observed_concepts",
               "n_contributing_panels", "interpretation"]


def classify(concept):
    return CONCEPT_TAXONOMY.get(concept, ("unclassified", "unclassified"))


def concept_taxonomy_rows(panel_id, concepts):
    return [{"panel_id": panel_id, "concept": concept,
             "category": classify(concept)[0],
             "subcategory": classify(concept)[1],
             "status": "observed_in_station_panel_not_independently_trained"}
            for concept in concepts]


def edge_index_rows(panel_id, edges):
    rows = []
    for edge in edges:
        source, target = edge["source_concept"], edge["target_concept"]
        sc, ss = classify(source)
        tc, ts = classify(target)
        rows.append({
            "panel_id": panel_id, "source_concept": source, "target_concept": target,
            "source_category": sc, "source_subcategory": ss,
            "target_category": tc, "target_subcategory": ts,
            "weight": edge["weight"], "sign": edge["sign"],
            "edge_kind": edge["edge_kind"],
            "view_type": "projection_of_single_trained_panel_not_an_independent_expert",
        })
    return rows


def summarize_hierarchy(panel_concepts):
    """panel_concepts: mapping of panel_id -> iterable of real concept names."""
    by_group = defaultdict(lambda: {"panels": set(), "concepts": set()})
    all_concepts = set()
    for panel_id, concepts in panel_concepts.items():
        for c in concepts:
            category, subcategory = classify(c)
            all_concepts.add(c)
            group = by_group[(category, subcategory)]
            group["panels"].add(panel_id)
            group["concepts"].add(c)
    coverage = []
    for (cat, sub), item in sorted(by_group.items()):
        coverage.append({
            "category": cat, "subcategory": sub,
            "n_distinct_concepts": len(item["concepts"]),
            "n_panels": len(item["panels"]),
            "concepts": ";".join(sorted(item["concepts"])),
            "panel_ids": ";".join(sorted(item["panels"])),
            "status": "descriptive_concept_coverage_not_trained_subcategory_fcm",
        })

    statuses = [{
        "level": "dataset_panel", "scope": "individual_station_fcms",
        "status": "trained_preview" if panel_concepts else "not_trained",
        "n_observed_concepts": len(all_concepts),
        "n_contributing_panels": len(panel_concepts),
        "interpretation": "each panel model fitted and validated separately",
    }]
    for category in CATEGORIES:
        concepts = {c for c in all_concepts if classify(c)[0] == category}
        contributing = {pid for pid, values in panel_concepts.items()
                        if any(classify(c)[0] == category for c in values)}
        statuses.append({
            "level": "category", "scope": category, "status": "not_trained",
            "n_observed_concepts": len(concepts),
            "n_contributing_panels": len(contributing),
            "interpretation": "taxonomy coverage only; no category expert or mixture fitted",
        })
    for cat, sub in sorted(by_group):
        item = by_group[(cat, sub)]
        statuses.append({
            "level": "subcategory", "scope": f"{cat}/{sub}", "status": "not_trained",
            "n_observed_concepts": len(item["concepts"]),
            "n_contributing_panels": len(item["panels"]),
            "interpretation": "projection of station concepts, not a separately trained FCM",
        })
    statuses.append({
        "level": "overall", "scope": "south_florida",
        "status": "not_trained",
        "n_observed_concepts": len(all_concepts),
        "n_contributing_panels": len(panel_concepts),
        "interpretation": "overall ecosystem coupling/gating remains future work",
    })
    return coverage, statuses
