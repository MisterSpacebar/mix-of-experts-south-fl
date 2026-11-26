"""Observed-only daily panels for same-site USGS continuous source series.

No cross-site joins, interpolation, forward filling, unit conversions, or
source-datum assumptions. A panel is blocked if the selected source series
contains unexpected duplicates, units or time bases.
"""
from collections import defaultdict
from datetime import date
from math import isfinite
from statistics import mean
from .readiness import parse_timestamp

PANEL_SUMMARY_COLS=[
    "panel_id","region","site_id","concepts",
    "concept_units","concept_datums","source_series_ids","n_requested_days",
    "n_complete_days","n_consecutive_daily_pairs","n_dropped_partial_days",
    "n_excluded_source_values","first_complete_day","last_complete_day",
    "status","reason",
]


def numeric(value):
    try:
        n=float(value)
        return n if isfinite(n) else None
    except (ValueError,TypeError):
        return None


def build_daily_panels(rows,plan,min_samples_per_day=8,min_span_hours=8,
                       exclude_provisional=False):
    if not 1<=min_samples_per_day<=288 or not 0<=min_span_hours<=23.99:
        raise ValueError("invalid observation coverage threshold")
    panels=defaultdict(list)
    for t in plan:
        panels[t["panel_id"]].append(t)
    output,summary={},[]
    for pid,tasks in sorted(panels.items()):
        site_set={t["site_id"] for t in tasks}
        if len(site_set)!=1 or any(t["dataset_id"]!="usgs_water" for t in tasks):
            raise ValueError("panel can contain only one canonical USGS site")
        concepts=[t["concept"] for t in tasks]
        if len(set(concepts))!=len(concepts):
            raise ValueError("one series per concept per panel is required")
        by_key={(t["site_id"],t["series_id"]):t for t in tasks}
        days=defaultdict(list)
        excluded=0
        seen={}
        for r in rows:
            t=by_key.get((r.get("site_id",""),r.get("series_id","")))
            if t is None:
                continue
            if (r.get("dataset_id")!="usgs_water" or
                    r.get("concept")!=t["concept"] or
                    r.get("parameter_code")!=t["parameter_code"]):
                raise ValueError("unexpected source series parameter/concept")
            if r.get("time_basis")!="explicit_utc_datetime":
                raise ValueError("daily panel expects explicit UTC instants only")
            if t.get("unit") and r.get("unit")!=t["unit"]:
                raise ValueError("incompatible units in selected source series")
            if r.get("vertical_datum","")!=t.get("vertical_datum",""):
                raise ValueError("vertical datum mismatch in panel")
            ts=parse_timestamp(r.get("timestamp_utc",""))
            if ts is None or ts.date().isoformat()!=r.get("sample_date"):
                raise ValueError("missing or inconsistent source UTC timestamp")
            day=ts.date().isoformat()
            if not t["start_date"]<=day<=t["end_date"]:
                raise ValueError("source row outside plan bounds")
            ident=(t["series_id"],ts.isoformat())
            this=(r.get("value",""),r.get("original_value",""),r.get("unit",""))
            if ident in seen:
                if seen[ident]!=this:
                    raise ValueError("conflicting numeric values at same series timestamp")
                continue
            seen[ident]=this
            value=numeric(r.get("value"))
            bad_status=any(x in r.get("approval_status","").lower()
                           for x in ("rejected","invalid","bad"))
            if exclude_provisional and any(
                    x in r.get("approval_status","").lower()
                    for x in ("provisional","working")):
                bad_status=True
            if value is None or r.get("detection_condition") or bad_status:
                excluded+=1
                continue
            days[(day,t["concept"])].append((ts,value))
        start=min(t["start_date"] for t in tasks)
        end=max(t["end_date"] for t in tasks)
        dates=sorted({day for day,_ in days})
        aligned=[]
        for day in dates:
            measured={}
            samples={}
            for concept in concepts:
                records=days.get((day,concept),[])
                if len(records)<min_samples_per_day:
                    break
                records.sort()
                span=(records[-1][0]-records[0][0]).total_seconds()/3600
                if span<min_span_hours:
                    break
                measured[concept]=mean(x for _,x in records)
                samples[concept]=len(records)
            if len(measured)==len(concepts):
                aligned.append(dict(date=day,site_id=tasks[0]["site_id"],panel_id=pid,
                                    **measured,**{f"n_{c}":samples[c] for c in concepts}))
        from datetime import date as Date
        pairs=sum((Date.fromisoformat(b["date"])-Date.fromisoformat(a["date"])).days==1
                  for a,b in zip(aligned,aligned[1:]))
        n_requested=(Date.fromisoformat(end)-Date.fromisoformat(start)).days+1
        status=("candidate_for_held_out_evaluation" if pairs>=79 and len(concepts)>=2
                else "insufficient_consecutive_observation_days")
        output[pid]=(concepts,aligned)
        summary.append({
            "panel_id":pid,"region":tasks[0]["region"],
            "site_id":tasks[0]["site_id"],"concepts":";".join(concepts),
            "concept_units":";".join(f'{t["concept"]}={t.get("unit","")}' for t in tasks),
            "concept_datums":";".join(f'{t["concept"]}={t.get("vertical_datum","")}' for t in tasks),
            "source_series_ids":";".join(f'{t["concept"]}={t["series_id"]}' for t in tasks),
            "n_requested_days":n_requested,"n_complete_days":len(aligned),
            "n_consecutive_daily_pairs":pairs,
            "n_dropped_partial_days":len(dates)-len(aligned),
            "n_excluded_source_values":excluded,
            "first_complete_day":aligned[0]["date"] if aligned else "",
            "last_complete_day":aligned[-1]["date"] if aligned else "",
            "status":status,
            "reason":"metadata and observed daily means only; all values preserve source units/datum",
        })
    return output,summary
