"""Preflight one USGS source series before any long historical download.

Ground a selected metadata ID in CURRENT official source metadata and actual
short-window observations. Never substitute a same-site parameter series
without an unequivocal matching source metadata record and observed ID.
"""
from collections import Counter
from datetime import date,timedelta
from .net import AcquisitionError
from .periods import usgs_site_parameter_periods
from .observations import usgs_observations

AUDIT_COLUMNS=[
    "panel_id","site_id","parameter_code","concept","old_series_id",
    "resolved_series_id","status","decision","candidate_metadata_ids",
    "probe_observed_ids","n_probe_observations","probe_start","probe_end",
    "metadata_unit","metadata_vertical_datum","metadata_statistic_id",
    "metadata_sublocation","metadata_primary","metadata_query_url","error",
]

def _qualifies(row,task):
    if row["dataset_id"]!="usgs_water" or row["site_id"]!=task["site_id"]:
        return False
    if row["parameter_code"]!=task["parameter_code"] or row["concept"]!=task["concept"]:
        return False
    if task.get("unit") and row["unit"]!=task["unit"]:
        return False
    if row.get("vertical_datum","")!=task.get("vertical_datum",""):
        return False
    # If the old snapshot supplied these identities, they MUST remain equal.
    for col in ("statistic_id","sublocation_identifier"):
        if task.get(col) and row.get(col,"")!=task[col]:
            return False
    if task.get("primary_status") and row.get("primary_status")!=task["primary_status"]:
        return False
    try:
        start=date.fromisoformat(task["start_date"])
        end=date.fromisoformat(task["end_date"])
        meta_start=date.fromisoformat(row["begin_utc"][:10])
        meta_end=date.fromisoformat(row["end_utc"][:10])
    except (ValueError,KeyError):
        return False
    return meta_start<=end and meta_end>=start

def resolve_one(task,metadata_fetch=usgs_site_parameter_periods,
                observations_fetch=usgs_observations,probe_days=2):
    if task.get("dataset_id")!="usgs_water" or task.get("mode")!="continuous":
        raise ValueError("preflight accepts USGS continuous history plans only")
    if not 1<=probe_days<=3:
        raise ValueError("probe must be 1 to 3 days")
    code=task["parameter_code"]
    site=task["site_id"]
    old=task["series_id"]
    finish=date.fromisoformat(task["end_date"])
    probe_begin=max(date.fromisoformat(task["start_date"]),
                    finish-timedelta(days=probe_days-1))
    started=probe_begin.isoformat()
    ended=finish.isoformat()
    meta=metadata_fetch(site,code)
    matching=[m for m in meta if _qualifies(m,task)]
    if not matching:
        raise AcquisitionError("no current metadata series matches original site, "
                               "parameter, unit, datum and historical window")
    ids=[m["series_id"] for m in matching]
    if len(ids)!=len(set(ids)):
        raise AcquisitionError("duplicate current metadata source-series ID")
    # Probe is small and deliberately unfiltered so the observed IDs can be
    # compared with *all* viable metadata candidates, not just the stale ID.
    rows,_=observations_fetch(site,code,started,ended,task["concept"],
                              mode="continuous",max_pages=3,page_size=1000,
                              max_records=3000)
    observed=Counter(row.get("series_id","") for row in rows)
    if not observed or "" in observed:
        raise AcquisitionError("short-window observation probe returned no verifiable IDs")
    available=[m for m in matching if m["series_id"] in observed]
    if not available:
        raise AcquisitionError("metadata series IDs have no observed match in probe")
    if old in {m["series_id"] for m in available}:
        winner=next(m for m in available if m["series_id"]==old)
        decision="original_id_correlated_with_live_metadata_and_observations"
    elif len(available)==1:
        winner=available[0]
        decision="metadata_property_id_verified_by_live_observations"
    else:
        raise AcquisitionError("ambiguous multiple viable current series IDs; "
                               "select source series manually after reviewing metadata")
    new=dict(task,series_id=winner["series_id"])
    report=dict(
        panel_id=task["panel_id"],site_id=site,parameter_code=code,
        concept=task["concept"],old_series_id=old,
        resolved_series_id=winner["series_id"],status="verified",
        decision=decision,
        candidate_metadata_ids=";".join(sorted(ids)),
        probe_observed_ids=";".join(f"{k}:{v}" for k,v in sorted(observed.items())),
        n_probe_observations=observed[winner["series_id"]],
        probe_start=started,probe_end=ended,metadata_unit=winner["unit"],
        metadata_vertical_datum=winner.get("vertical_datum",""),
        metadata_statistic_id=winner.get("statistic_id",""),
        metadata_sublocation=winner.get("sublocation_identifier",""),
        metadata_primary=winner.get("primary_status",""),
        metadata_query_url=winner.get("source_url",""),
        error="",
    )
    return new,report
