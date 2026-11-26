"""Milestone 8: STRICT between-station transfer and descriptive edge replication.

A source-trained model is evaluated on an entirely distinct target station
without refitting. Require identical ordered measurement concepts and
source-reported physical units/datums; no cross-site series pooling, scale
normalization fitted on target, or claims about regional generalization.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date,timedelta
from math import isfinite
from statistics import mean,median

from .fcm_model import predict
from .m8_validation import _numeric

TRANSFER_COLS=["level","scope","donor_panel","donor_site","target_panel",
               "target_site","concept","n_matched_test_days","donor_transfer_mae",
               "target_local_fcm_mae","target_persistence_mae",
               "transfer_skill_vs_persistence","transfer_skill_vs_local_fcm",
               "interpretation"]
TRANSFER_STATUS_COLS=["level","scope","donor_panel","target_panel",
                      "status","reason"]
EDGE_COLS=["level","scope","concept_set","source_concept","target_concept",
           "n_distinct_sites","n_positive","n_negative","n_zero",
           "sign_consistency","median_weight","status","interpretation"]


def exact_units(row,concepts):
    def entries(value):
        tokens=str(value or "").split(";")
        out={}
        for token in tokens:
            if not token:
                continue
            if "=" not in token:
                raise ValueError("malformed measurement unit/datum metadata")
            concept,unit=token.split("=",1)
            if concept in out:
                raise ValueError("duplicate measurement unit/datum metadata")
            out[concept]=unit
        return out
    units=entries(row.get("concept_units",""))
    datums=entries(row.get("concept_datums",""))
    if not all(c in units and units[c] for c in concepts):
        return None
    if not all(c in datums for c in concepts):
        return None
    return tuple((c,units[c],datums[c]) for c in sorted(concepts))


def transfer_to_target(source_model,target_rows,target_predictions,concepts):
    """Forecast target's predeclared held-out dates using DONOR-only scaler.

    Target panel supplies previous-day observations (necessary to compute
    one-day conditional forecasts), but neither target labels nor target
    training data alter donor weights, offsets, or scaling. Target model's
    original held-out dates define an unbiased target assessment set.
    """
    donor_concepts=source_model["concepts"]
    if set(donor_concepts)!=set(concepts) or len(donor_concepts)!=len(concepts):
        raise ValueError("transfer requires identical concept sets")
    means=source_model["normalization_mean"]
    scales=source_model["normalization_scale"]
    intercepts=source_model["intercepts"]
    matrix=source_model["matrix_source_to_target"]
    d=len(donor_concepts)
    if (len(means)!=d or len(scales)!=d or len(intercepts)!=d or
            len(matrix)!=d or any(len(row)!=d for row in matrix)):
        raise ValueError("donor FCM coefficient/scaler shape mismatch")
    if any(not isfinite(float(s)) or float(s)<=1e-10 for s in scales):
        raise ValueError("invalid donor standardization scale")
    weights=[[float(intercepts[j])]+[float(matrix[i][j]) for i in range(d)]
             for j in range(d)]
    # Only TARGET values that precede the target date are permitted inputs.
    observed={}
    for row in target_rows:
        day=date.fromisoformat(row["date"])
        if day in observed:
            raise ValueError("duplicate target panel date")
        observed[day]=row
    target_index={}
    for r in target_predictions:
        key=(r["date"],r["concept"])
        if key in target_index:
            raise ValueError("duplicate target heldout prediction")
        target_index[key]=r
    dates={date.fromisoformat(k[0]) for k in target_index}
    records=[]
    for day in sorted(dates):
        previous=day-timedelta(days=1)
        if previous not in observed or day not in observed:
            raise ValueError("nonconsecutive or missing target observation on heldout date")
        previous_state=observed[previous]
        today=observed[day]
        features=[_numeric(previous_state[c]) for c in donor_concepts]
        normalized=[(features[i]-float(means[i]))/float(scales[i])
                    for i in range(d)]
        zhat=predict(weights,normalized)
        for i,concept in enumerate(donor_concepts):
            key=(day.isoformat(),concept)
            if key not in target_index:
                raise ValueError("target model and donor concept sets differ")
            target=target_index[key]
            actual=_numeric(today[concept])
            if abs(actual-_numeric(target["actual"]))>max(1e-8,1e-9*abs(actual)):
                raise ValueError("source panel and heldout target values differ")
            transferred=zhat[i]*float(scales[i])+float(means[i])
            records.append(dict(
                date=day.isoformat(),concept=concept,actual=actual,
                transferred=transferred,
                persistence=features[i],
                target_local_fcm=_numeric(target["fcm"]),
            ))
    if len(records)!=len(target_predictions):
        raise ValueError("target test concept/date population mismatch")
    return records


def summarize_transfer(donor,target,records):
    def score(a,b):
        return None if b==0 else 1-a/b
    groups=defaultdict(list)
    for row in records:
        groups[row["concept"]].append(row)
    output=[]
    for concept,part in sorted(groups.items()):
        def err(key):
            return mean(abs(_numeric(row[key])-_numeric(row["actual"]))
                        for row in part)
        transferred=err("transferred")
        persistence=err("persistence")
        local=err("target_local_fcm")
        output.append({
            "level":donor["level"],"scope":donor["scope"],
            "donor_panel":donor["panel_id"],"donor_site":donor["site_id"],
            "target_panel":target["panel_id"],"target_site":target["site_id"],
            "concept":concept,"n_matched_test_days":len(part),
            "donor_transfer_mae":transferred,
            "target_local_fcm_mae":local,
            "target_persistence_mae":persistence,
            "transfer_skill_vs_persistence":score(transferred,persistence),
            "transfer_skill_vs_local_fcm":score(transferred,local),
            "interpretation":"donor-only training; distinct target station; "
                             "same concepts and raw units/datums; "
                             "conditional one-day heldout forecasting only",
        })
    return output


def source_edge_replication(models,min_sites=3):
    """Descriptive sign recurrence. Never average station FCM matrices.

    models: rows each containing level, scope, site_id, panel_id,
    concepts, source unit/datum signature and edge records. Require one
    fitted source per distinct station for a scope/concept-set signature.
    """
    if min_sites<2:
        raise ValueError("min_sites must be at least two")
    by_group=defaultdict(dict)
    for model in models:
        signature=(model["level"],model["scope"],
                   tuple(sorted(model["concepts"])),model["unit_signature"])
        key=model["site_id"]
        if key in by_group[signature]:
            raise ValueError("replicated station/scope duplicate must be quarantined")
        by_group[signature][key]=model
    result=[]
    for (level,scope,concept_set,units),sites in sorted(by_group.items()):
        pair_values=defaultdict(list)
        for site,model in sorted(sites.items()):
            seen=set()
            for edge in model["edges"]:
                pair=(edge["source_concept"],edge["target_concept"])
                if pair in seen:
                    raise ValueError("duplicate directed edge in site source")
                seen.add(pair)
                pair_values[pair].append(float(edge["weight"]))
        for (source,target),values in sorted(pair_values.items()):
            positives=sum(x>1e-9 for x in values)
            negatives=sum(x< -1e-9 for x in values)
            zeros=len(values)-positives-negatives
            nonzero=positives+negatives
            consistency=max(positives,negatives)/nonzero if nonzero else None
            result.append({
                "level":level,"scope":scope,
                "concept_set":";".join(concept_set),
                "source_concept":source,"target_concept":target,
                "n_distinct_sites":len(values),
                "n_positive":positives,"n_negative":negatives,"n_zero":zeros,
                "sign_consistency":consistency if consistency is not None else "",
                "median_weight":median(values),
                "status":"replication_candidate_not_causal" if len(values)>=min_sites
                         else "insufficient_independent_sites",
                "interpretation":"independent site fits and matched measurement schema "
                                 "only; sign frequency not regional causal evidence",
            })
    return result
