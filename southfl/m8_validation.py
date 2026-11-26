"""Milestone 8 replication diagnostics: temporal folds and paired uncertainty.

All evaluations here use observed held-out predictions. Contiguous moving
blocks preserve local date dependence; the intervals are exploratory
single-period uncertainty summaries, not calibrated causal confidence
intervals or independent station replications.
"""
from __future__ import annotations
from datetime import date,timedelta
from math import isfinite
from random import Random
from statistics import mean

from .fcm_model import NotReadyError,build_pairs,fit_preview

FOLD_COLS=["panel_id","level","scope","fold","n_pairs","train_pairs",
           "validation_pairs","test_pairs","train_end","validation_end",
           "test_start","test_end","concept","fcm_mae","self_ar_mae",
           "persistence_mae","skill_vs_self_ar","skill_vs_persistence"]
FOLD_EDGE_COLS=["panel_id","level","scope","fold","source_concept",
                "target_concept","weight","sign","test_start","test_end"]
PAIRED_COLS=["panel_id","level","scope","comparison","concept",
             "n_test_days","first_test_date","last_test_date",
             "block_length","n_bootstrap","mae_a","mae_b","mae_delta_a_minus_b",
             "delta_ci_2_5","delta_ci_97_5","bootstrap_fraction_a_better",
             "interpretation"]


def _numeric(value):
    try:
        x=float(value)
    except (ValueError,TypeError) as exc:
        raise ValueError("prediction contains nonnumeric value") from exc
    if not isfinite(x):
        raise ValueError("prediction contains nonfinite value")
    return x


def _percentile(sorted_values,percent):
    if not sorted_values:
        raise ValueError("percentile of empty bootstrap")
    pos=(len(sorted_values)-1)*percent
    lo=int(pos)
    hi=min(lo+1,len(sorted_values)-1)
    return sorted_values[lo]+(sorted_values[hi]-sorted_values[lo])*(pos-lo)


def _consecutive_blocks(days,length):
    starts=[]
    for start in range(len(days)-length+1):
        if (days[start+length-1]-days[start]).days==length-1:
            starts.append(start)
    return starts


def paired_block_interval(pred_rows,first,second,block_length=7,
                          replicates=400,seed=17):
    """Paired MAE difference A-B, one row per distinct UTC test day.

    The resampled unit is a contiguous block of paired errors. We never
    concatenate artificial days *within* a block, and resampled blocks
    may be repeated as in the moving-block bootstrap.
    """
    if not 2<=block_length<=30 or not 100<=replicates<=5000:
        raise ValueError("bootstrap bounds are 2..30 days, 100..5000 draws")
    ordered=sorted(pred_rows,key=lambda r:r["date"])
    days=[date.fromisoformat(row["date"]) for row in ordered]
    if len(days)<block_length*2 or len(set(days))!=len(days):
        raise NotReadyError("insufficient distinct held-out dates for block bootstrap")
    losses_a=[abs(_numeric(r[first])-_numeric(r["actual"])) for r in ordered]
    losses_b=[abs(_numeric(r[second])-_numeric(r["actual"])) for r in ordered]
    starts=_consecutive_blocks(days,block_length)
    if not starts:
        raise NotReadyError("no contiguous block of requested length in test dates")
    n=len(ordered)
    rng=Random(seed)
    delta=[a-b for a,b in zip(losses_a,losses_b)]
    samples=[]
    for _ in range(replicates):
        taken=[]
        while len(taken)<n:
            start=rng.choice(starts)
            taken.extend(range(start,start+block_length))
        taken=taken[:n]
        samples.append(mean(delta[i] for i in taken))
    samples.sort()
    return {
        "n_test_days":n,
        "first_test_date":days[0].isoformat(),
        "last_test_date":days[-1].isoformat(),
        "block_length":block_length,"n_bootstrap":replicates,
        "mae_a":mean(losses_a),"mae_b":mean(losses_b),
        "mae_delta_a_minus_b":mean(delta),
        "delta_ci_2_5":_percentile(samples,.025),
        "delta_ci_97_5":_percentile(samples,.975),
        "bootstrap_fraction_a_better":sum(x<0 for x in samples)/len(samples),
        "interpretation":"exploratory paired moving-block bootstrap; "
                         "one held-out period, serial dependence, not causal",
    }


def matched_rows(a_rows,b_rows,a_key="fcm",b_key="fcm"):
    """Exact matched dates/concepts/targets, rejecting silent sample shifts."""
    a={(r["date"],r["concept"]):r for r in a_rows}
    b={(r["date"],r["concept"]):r for r in b_rows}
    if len(a)!=len(a_rows) or len(b)!=len(b_rows):
        raise ValueError("duplicate concept/date prediction rows")
    if a.keys()!=b.keys():
        raise ValueError("prediction dates or concept sets differ across models")
    result=[]
    for date_concept in sorted(a):
        left,right=a[date_concept],b[date_concept]
        actual=_numeric(left["actual"])
        if abs(actual-_numeric(right["actual"]))>max(1e-8,1e-9*abs(actual)):
            raise ValueError("paired observed targets differ")
        result.append({
            "date":date_concept[0],"concept":date_concept[1],"actual":actual,
            "a":_numeric(left[a_key]),"b":_numeric(right[b_key]),
        })
    return result


def expanding_folds(rows,concepts,min_pairs=79,max_folds=3):
    """Backward-select expanding-origin fits with NON-overlapping test dates.

    Earlier folds may later enter a newer fold's training data, which is
    valid in a prospective expanding-window evaluation. Different folds
    are not statistically independent because training histories overlap.
    """
    if not 1<=max_folds<=8:
        raise ValueError("max_folds must be 1..8")
    ordered=sorted(rows,key=lambda r:r["date"])
    seen_dates=set()
    for row in ordered:
        if row["date"] in seen_dates:
            raise NotReadyError("duplicate observed daily panel date")
        seen_dates.add(row["date"])
    selected=[]
    earliest_later_test=None
    for end in range(len(ordered),79,-1):
        subset=ordered[:end]
        pairs=build_pairs(subset,concepts)
        n=len(pairs)
        ntrain=int(n*.6)
        nval=int(n*.2)
        ntest=n-ntrain-nval
        if n<min_pairs or ntrain<35 or nval<15 or ntest<15:
            continue
        test_start=pairs[ntrain+nval][0]
        test_end=pairs[-1][0]
        if earliest_later_test is not None and test_end>=earliest_later_test:
            continue
        try:
            model=fit_preview(subset,concepts,min_pairs=min_pairs)
        except NotReadyError:
            continue
        selected.append(model)
        earliest_later_test=test_start
        if len(selected)>=max_folds:
            break
    selected.reverse()
    # Exact, not merely assumed, disjoint heldout dates.
    seen=set()
    for model in selected:
        here={r["date"] for r in model["predictions"]}
        if seen.intersection(here):
            raise RuntimeError("expanding-origin tests overlap unexpectedly")
        seen.update(here)
    return selected


def model_scores(panel_id,level,scope,models):
    folds,edges=[],[]
    for i,model in enumerate(models,1):
        for m in model["evaluation"]:
            def skill(reference):
                return None if reference==0 else 1-m["fcm_mae"]/reference
            folds.append(dict(
                panel_id=panel_id,level=level,scope=scope,fold=i,
                n_pairs=model["n_pairs"],train_pairs=model["train_pairs"],
                validation_pairs=model["validation_pairs"],
                test_pairs=model["test_pairs"],train_end=model["train_end"],
                validation_end=model["validation_end"],
                test_start=model["test_start"],test_end=model["test_end"],
                concept=m["concept"],fcm_mae=m["fcm_mae"],
                self_ar_mae=m["self_ar_mae"],
                persistence_mae=m["persistence_mae"],
                skill_vs_self_ar=skill(m["self_ar_mae"]),
                skill_vs_persistence=skill(m["persistence_mae"]),
            ))
        for e in model["edges"]:
            edges.append(dict(
                panel_id=panel_id,level=level,scope=scope,fold=i,
                source_concept=e["source_concept"],
                target_concept=e["target_concept"],
                weight=e["weight"],sign=e["sign"],
                test_start=model["test_start"],test_end=model["test_end"],
            ))
    return folds,edges
