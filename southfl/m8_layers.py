"""Milestone 8: independent within-station category/subcategory FCM fits.

These are newly fitted, train/validation/test evaluated *within-station*
restricted-concept models. They are not pooled regional category experts,
cross-site transferred models, or a learned mixture-of-experts gate.
"""
from collections import defaultdict
from math import isclose
from statistics import mean

from .fcm_model import NotReadyError, fit_preview
from visuals.hierarchy import classify

COMPARISON_COLS=[
    "panel_id","level","scope","concept","n_aligned_test_days",
    "specialist_fcm_mae","full_panel_fcm_mae","self_ar_mae",
    "persistence_mae","specialist_minus_full_mae",
    "specialist_skill_vs_full","specialist_skill_vs_self_ar",
    "specialist_skill_vs_persistence","interpretation",
]
STATUS_COLS=[
    "level","category","subcategory","panel_id","site_id","region",
    "concepts","n_concepts","n_complete_days","n_consecutive_daily_pairs",
    "status","reason","model_directory","panel_sha256",
]


def concept_scopes(concepts):
    """Only physically labeled concepts may define specialist training scope."""
    by_category=defaultdict(list)
    by_subcategory=defaultdict(list)
    for concept in concepts:
        cat,sub=classify(concept)
        if cat=="unclassified":
            continue
        by_category[cat].append(concept)
        by_subcategory[(cat,sub)].append(concept)
    entries=[]
    for cat in sorted(by_category):
        entries.append(("category",cat,"",by_category[cat]))
    for cat,sub in sorted(by_subcategory):
        entries.append(("subcategory",cat,sub,by_subcategory[(cat,sub)]))
    return entries


def fit_scoped(rows, concepts, min_pairs=79):
    """Use same chronological split/training policy as full dataset expert."""
    if len(concepts)<2:
        raise NotReadyError("a trainable specialist requires >=2 distinct concepts")
    return fit_preview(rows,concepts,min_pairs=min_pairs)


def _skill(model,baseline):
    if baseline<0 or model<0:
        raise ValueError("MAE cannot be negative")
    return None if baseline==0 else 1-model/baseline


def compare_matched(full_model, specialist_model, panel_id, level, scope):
    """Assess newly fitted specialist vs full FCM on EXACT SAME test examples.

    Reject mismatched dates or observed targets; otherwise cross-model
    skill comparisons could silently exploit different sampling periods.
    """
    full_index={(r["concept"],r["date"]):r
                for r in full_model["predictions"]}
    if len(full_index)!=len(full_model["predictions"]):
        raise ValueError("full FCM contains duplicate held-out concept/date pairs")
    specialist_index={(r["concept"],r["date"]) for r in specialist_model["predictions"]}
    if len(specialist_index)!=len(specialist_model["predictions"]):
        raise ValueError("specialist contains duplicate held-out concept/date pairs")
    output=[]
    for metric in specialist_model["evaluation"]:
        concept=metric["concept"]
        specialist_rows=[r for r in specialist_model["predictions"]
                         if r["concept"]==concept]
        if not specialist_rows:
            raise ValueError("specialist has no held-out predictions")
        full_rows=[]
        for r in specialist_rows:
            match=full_index.get((concept,r["date"]))
            if match is None:
                raise ValueError("specialist/full test dates do not match")
            if not isclose(float(match["actual"]),float(r["actual"]),
                           rel_tol=1e-9,abs_tol=1e-8):
                raise ValueError("specialist/full held-out actuals differ")
            full_rows.append(match)
        if len(full_rows) != len([r for r in full_model["predictions"]
                                 if r["concept"]==concept]):
            raise ValueError("full FCM used a different test date population")
        full_mae=mean(abs(float(r["fcm"])-float(r["actual"]))
                      for r in full_rows)
        special_mae=mean(abs(float(r["fcm"])-float(r["actual"]))
                         for r in specialist_rows)
        # Baselines could have been tuned independently; use the matched
        # specialist's own chronological baseline results.
        ar=float(metric["self_ar_mae"])
        persistence=float(metric["persistence_mae"])
        output.append({
            "panel_id":panel_id,"level":level,"scope":scope,"concept":concept,
            "n_aligned_test_days":len(specialist_rows),
            "specialist_fcm_mae":round(special_mae,6),
            "full_panel_fcm_mae":round(full_mae,6),
            "self_ar_mae":ar,"persistence_mae":persistence,
            "specialist_minus_full_mae":round(special_mae-full_mae,6),
            "specialist_skill_vs_full":_skill(special_mae,full_mae),
            "specialist_skill_vs_self_ar":_skill(special_mae,ar),
            "specialist_skill_vs_persistence":_skill(special_mae,persistence),
            "interpretation":"same-site and same held-out dates; descriptive comparison only",
        })
    return output
