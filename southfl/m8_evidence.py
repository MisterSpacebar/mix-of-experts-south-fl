"""Pure evidence diagnostics for frozen Milestone 8 station FCM artifacts.

No model fitting or pooling. A shared unit name does not establish matching
vertical reference datums, and a unanimous near-zero sign is not a robust
cross-site relationship. Transfer diagnostics recompute *the same* original
donor-only forecast, with the original donor model and target held-out inputs.
"""
from __future__ import annotations
from collections import defaultdict
from math import isfinite
from statistics import mean, median

STAGE_CONCEPTS = frozenset({
    "gage_height", "water_level", "stream_stage_elevation",
    "groundwater_elevation", "groundwater_depth_below_land_surface",
})
TRANSFER_DIAGNOSTIC_COLS = [
    "level", "scope", "donor_panel", "target_panel", "donor_site",
    "target_site", "concept", "n_test_days", "donor_transfer_mae",
    "target_persistence_mae", "mae_ratio_vs_persistence",
    "skill_vs_persistence", "donor_training_mean", "donor_training_scale",
    "target_previous_mean", "mean_target_offset_in_donor_sd",
    "fraction_target_states_outside_donor_3sd",
    "fraction_predictions_at_clip_boundary", "source_unit",
    "donor_datum", "target_datum", "datum_check",
    "physical_comparability", "interpretation",
]
EDGE_DIAGNOSTIC_COLS = [
    "level", "scope", "source_concept", "target_concept", "edge_kind",
    "n_sites", "n_positive", "n_negative", "sign_consistency",
    "median_signed_weight", "median_abs_weight", "min_abs_weight",
    "n_sites_above_threshold", "weight_threshold", "evidence_grade",
    "regional_model_trained", "interpretation",
]
UNCERTAINTY_AUDIT_COLS = [
    "panel_id", "level", "scope", "comparison", "concept", "n_test_days",
    "point_delta", "ci_lower", "ci_upper", "audit_status", "interpretation",
]


def _number(x):
    v = float(x)
    if not isfinite(v):
        raise ValueError("non-finite numerical evidence")
    return v


def _metadata(source, concept):
    def decode(s):
        result = {}
        for x in str(s or "").split(";"):
            if x:
                if "=" not in x:
                    raise ValueError("invalid source concept metadata")
                key, value = x.split("=", 1)
                if key in result:
                    raise ValueError("duplicate source concept metadata")
                result[key] = value
        return result
    units = decode(source.get("concept_units", ""))
    datums = decode(source.get("concept_datums", ""))
    return units.get(concept, ""), datums.get(concept, "")


def _datum_status(concept, donor, target):
    if concept not in STAGE_CONCEPTS:
        return "not_required_for_this_concept"
    if not donor or not target:
        return "reference_datum_unverified"
    return ("verified_same_reported_reference" if donor == target
            else "different_reported_reference")


def transfer_diagnostics(donor, target, donor_model, predictions, original):
    """Audit a previous transfer using the *exact* donor-only predictions.

    donor and target include panel_id, site_id, concept_units, concept_datums.
    original is a source transfer CSV row for each concept. Exact original
    MAEs must agree with the recomputation, otherwise fail closed.
    """
    concepts = donor_model["concepts"]
    index = {name: i for i, name in enumerate(concepts)}
    groups = defaultdict(list)
    for row in predictions:
        if row["concept"] not in index:
            raise ValueError("transfer refers to unknown donor concept")
        groups[row["concept"]].append(row)
    expected = {r["concept"]: r for r in original}
    if set(groups) != set(expected):
        raise ValueError("recomputed transfer concept set differs from source evidence")
    result = []
    for concept, values in sorted(groups.items()):
        j = index[concept]
        mu, scale = _number(donor_model["normalization_mean"][j]), _number(
            donor_model["normalization_scale"][j])
        if scale <= 1e-10:
            raise ValueError("invalid donor scale")
        raw_input = [_number(p["persistence"]) for p in values]
        raw_forecast = [_number(p["transferred"]) for p in values]
        actual = [_number(p["actual"]) for p in values]
        mae = mean(abs(x-y) for x,y in zip(raw_forecast, actual))
        persist = mean(abs(x-y) for x,y in zip(raw_input, actual))
        source = expected[concept]
        if (abs(mae-_number(source["donor_transfer_mae"])) > 1e-5 or
            abs(persist-_number(source["target_persistence_mae"])) > 1e-5 or
            int(source["n_matched_test_days"]) != len(values)):
            raise ValueError("stored transfer metrics do not match audited donor forecasts")
        unit_a, datum_a = _metadata(donor, concept)
        unit_b, datum_b = _metadata(target, concept)
        if not unit_a or unit_a != unit_b:
            raise ValueError("source units not identical for transfer")
        datum_check = _datum_status(concept,datum_a,datum_b)
        physical = ("reported_units_match;vertical_reference_unverified"
                    if datum_check=="reference_datum_unverified" else
                    "reported_units_and_reference_match" if
                    datum_check=="verified_same_reported_reference" else
                    "reported_units_match;datum_not_applicable" if
                    datum_check=="not_required_for_this_concept" else
                    "reported_vertical_reference_conflict")
        offsets = [abs((x-mu)/scale) for x in raw_input]
        normalized_output = [(x-mu)/scale for x in raw_forecast]
        result.append({
            "level": source["level"], "scope": source["scope"],
            "donor_panel":donor["panel_id"],
            "target_panel":target["panel_id"],
            "donor_site":donor["site_id"],
            "target_site":target["site_id"],"concept":concept,
            "n_test_days":len(values),
            "donor_transfer_mae":mae,
            "target_persistence_mae":persist,
            "mae_ratio_vs_persistence":mae/persist if persist>0 else "",
            "skill_vs_persistence":1-mae/persist if persist>0 else "",
            "donor_training_mean":mu,"donor_training_scale":scale,
            "target_previous_mean":mean(raw_input),
            "mean_target_offset_in_donor_sd":mean(offsets),
            "fraction_target_states_outside_donor_3sd":
                sum(x>3 for x in offsets)/len(offsets),
            "fraction_predictions_at_clip_boundary":
                sum(abs(abs(x)-3)<1e-7 for x in normalized_output)/len(values),
            "source_unit":unit_a,"donor_datum":datum_a,"target_datum":datum_b,
            "datum_check":datum_check,"physical_comparability":physical,
            "interpretation":"diagnostic for unchanged original donor-only "
                "one-day held-out forecast; donor mean/scale never fitted to target; "
                "does not establish station interchangeability",
        })
    return result


def edge_strength_diagnostics(recurrence, station_edges, min_abs=0.08):
    """Compare reported sign consistency against actual per-station weights.

    station_edges keys: (level, scope, source_concept, target_concept) ->
    iterable of (site_id, signed weight). Reject duplicates across sites.
    """
    if not 0<=min_abs<=1:
        raise ValueError("edge threshold must be in [0,1]")
    result=[]
    for entry in recurrence:
        key=(entry["level"],entry["scope"],
             entry["source_concept"],entry["target_concept"])
        weights=station_edges.get(key,[])
        sites={}
        for site,w in weights:
            if site in sites:
                raise ValueError("duplicate station in edge replication group")
            sites[site]=_number(w)
        count=int(entry["n_distinct_sites"])
        if count!=len(sites):
            raise ValueError("source edge count differs from recurrence CSV")
        vs=list(sites.values())
        np=sum(x>1e-9 for x in vs)
        nn=sum(x< -1e-9 for x in vs)
        if np!=int(entry["n_positive"]) or nn!=int(entry["n_negative"]):
            raise ValueError("edge sign counts differ from source model weights")
        magnitudes=[abs(x) for x in vs]
        nstrong=sum(x>=min_abs for x in magnitudes)
        unanimous=max(np,nn)==count
        if count<3:
            grade="insufficient_independent_sites"
        elif min_abs>0 and nstrong<count:
            grade="weak_weight_in_at_least_one_site"
        elif unanimous:
            grade="unanimous_sign_at_display_threshold"
        else:
            grade="mixed_sign_across_sites"
        result.append({
            "level":entry["level"],"scope":entry["scope"],
            "source_concept":entry["source_concept"],
            "target_concept":entry["target_concept"],
            "edge_kind":("self_memory" if
                         entry["source_concept"]==entry["target_concept"]
                         else "cross_concept"),
            "n_sites":count,"n_positive":np,"n_negative":nn,
            "sign_consistency":entry["sign_consistency"],
            "median_signed_weight":median(vs),
            "median_abs_weight":median(magnitudes),
            "min_abs_weight":min(magnitudes),
            "n_sites_above_threshold":nstrong,
            "weight_threshold":min_abs,
            "evidence_grade":grade,"regional_model_trained":False,
            "interpretation":"threshold-qualified sign screening only; "
                "weights are station-specific predictive coefficients, "
                "not pooled or causal regional relationships",
        })
    return result


def uncertainty_integrity(rows):
    """Flag percentile intervals excluding their own original point estimate.

    Possible with a strongly biased/disconnected-block resampling design.
    Such intervals need sensitivity review, not automatic significance claims.
    """
    output=[]
    for row in rows:
        estimate=_number(row["mae_delta_a_minus_b"])
        low=_number(row["delta_ci_2_5"])
        high=_number(row["delta_ci_97_5"])
        if low>high:
            raise ValueError("reversed bootstrap interval")
        status=("point_estimate_outside_bootstrap_interval"
                if estimate<low or estimate>high else
                "point_estimate_within_bootstrap_interval")
        output.append({
            "panel_id":row["panel_id"],"level":row["level"],
            "scope":row["scope"],"comparison":row["comparison"],
            "concept":row["concept"],
            "n_test_days":row["n_test_days"],
            "point_delta":estimate,"ci_lower":low,"ci_upper":high,
            "audit_status":status,
            "interpretation":"bootstrap percentile interval is exploratory; "
                "sampling only contiguous available blocks can distort "
                "representation when held-out dates contain gaps",
        })
    return output
