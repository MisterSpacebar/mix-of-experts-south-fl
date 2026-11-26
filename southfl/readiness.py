"""Source-preserving observation QA and same-site co-coverage diagnostics.

No percent completeness without a documented expected station schedule.
No pooled or fabricated measurements. Counts are observed records and dates.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from math import isfinite
from statistics import median

SERIES_COLS = ["dataset_id","site_id","series_id","concept","unit","vertical_datum",
               "fraction","depth","time_basis","n_rows","n_numeric","n_censored",
               "n_flagged","n_provisional","n_duplicate_ids","n_duplicate_times",
               "n_conflicting_times","n_dates","start_date","end_date",
               "observed_span_days","median_observed_gap_hours","readiness_note"]
PAIR_COLS = ["dataset_id","site_id","concept_a","concept_b","shared_observed_dates",
             "first_shared_date","last_shared_date","unit_datum_review","interpretation"]


def parse_timestamp(value):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError(f"malformed UTC timestamp: {value!r}") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("UTC timestamp is missing timezone")
    return stamp.astimezone(timezone.utc)


def _number(value):
    try:
        out = float(value)
        return out if isfinite(out) else None
    except (TypeError, ValueError):
        return None


def audit(rows):
    by_series, dates_by_concept = defaultdict(list), defaultdict(set)
    for r in rows:
        if not r.get("dataset_id") or not r.get("site_id") or not r.get("concept"):
            raise ValueError("source observation requires dataset, site and concept")
        if not r.get("sample_date"):
            raise ValueError("observation missing original sample date")
        day = date.fromisoformat(r["sample_date"])
        ts = parse_timestamp(r.get("timestamp_utc",""))
        basis = r.get("time_basis","")
        if basis == "explicit_utc_datetime":
            if ts is None or ts.date() != day:
                raise ValueError("explicit UTC observation date/timestamp mismatch")
        elif basis not in ("source_daily_calendar_date","source_local_date_not_utc"):
            raise ValueError("unsupported time basis")
        key = (r["dataset_id"],r["site_id"],r.get("series_id",""),r["concept"],
               r.get("unit",""),r.get("vertical_datum",""),r.get("fraction",""),
               r.get("sample_depth_value","")+" "+r.get("sample_depth_unit",""),basis)
        by_series[key].append((r, day, ts))
        if _number(r.get("value")) is not None and not r.get("detection_condition"):
            dates_by_concept[(r["dataset_id"],r["site_id"],r["concept"])].add(day)

    summaries = []
    for key, data in sorted(by_series.items()):
        rows_only = [item[0] for item in data]
        days = [item[1] for item in data]
        times = sorted(t for _,_,t in data if t is not None)
        gaps = [(b-a).total_seconds()/3600 for a,b in zip(times,times[1:]) if b>a]
        found_ids, id_dups, found_times, time_dups, time_conflicts = set(),0,{},0,0
        for r,day,ts in data:
            rid = r.get("result_id","")
            if rid:
                if rid in found_ids: id_dups+=1
                found_ids.add(rid)
            stamp = ts.isoformat() if ts else str(day)
            if stamp in found_times:
                time_dups+=1
                if found_times[stamp] != (r.get("original_value",""),r.get("unit",""),
                                         r.get("approval_status","")):
                    time_conflicts+=1
            else:
                found_times[stamp]=(r.get("original_value",""),r.get("unit",""),
                                    r.get("approval_status",""))
        n_numeric = sum(_number(r.get("value")) is not None and
                        not r.get("detection_condition") for r in rows_only)
        span = (max(days)-min(days)).days+1
        ready_note = ("different_values_same_instrument_time" if time_conflicts else
                      "too_few_observed_days_for_temporal_model" if len(set(days))<60 else
                      "candidate_only_verify_deployment_and_qc")
        summaries.append(dict(zip(SERIES_COLS,[
            *key,len(data),n_numeric,
            sum(bool(r.get("detection_condition")) for r in rows_only),
            sum(bool(r.get("qualifier")) for r in rows_only),
            sum("provisional" in r.get("approval_status","").lower()
                or "working" in r.get("approval_status","").lower()
                for r in rows_only),
            id_dups,time_dups,time_conflicts,len(set(days)),min(days).isoformat(),
            max(days).isoformat(),span,round(median(gaps),4) if gaps else "",
            ready_note,
        ])))
    sites = defaultdict(list)
    for (dataset,site,concept),days in dates_by_concept.items():
        sites[(dataset,site)].append((concept,days))
    pairs=[]
    for (dataset,site),concepts in sorted(sites.items()):
        for i,(ca,da) in enumerate(sorted(concepts)):
            for cb,db in sorted(concepts)[i+1:]:
                shared=sorted(da & db)
                if not shared:
                    continue
                pairs.append(dict(
                    dataset_id=dataset,site_id=site,concept_a=ca,concept_b=cb,
                    shared_observed_dates=len(shared),
                    first_shared_date=shared[0].isoformat(),
                    last_shared_date=shared[-1].isoformat(),
                    unit_datum_review="required_before_panel",
                    interpretation="same_site_dates_only_not_synchronous_or_trainable"))
    return summaries,pairs
