"""Bounded USGS continuous-history retrieval by selected canonical time series.

API requests are made only by the caller with --execute. Each selected
series is downloaded in <=14-calendar-day nonoverlapping windows, preserving
source timestamp/units/flags and rejecting mismatches. No interpolation.
"""
from datetime import date,timedelta
from .net import AcquisitionError
from .observations import usgs_observations

def windows(start,end,days=14):
    start,end=date.fromisoformat(start),date.fromisoformat(end)
    if not 1<=days<=21 or end<start:
        raise ValueError("bad historical window bounds or chunk length")
    cursor=start
    while cursor<=end:
        stop=min(end,cursor+timedelta(days=days-1))
        yield cursor.isoformat(),stop.isoformat()
        cursor=stop+timedelta(days=1)


def fetch_series(task,fetcher=usgs_observations,chunk_days=14):
    if task.get("dataset_id")!="usgs_water" or task.get("mode")!="continuous":
        raise ValueError("FCM history requires USGS continuous source data")
    if not task.get("series_id"):
        raise ValueError("a canonical source time_series_id is required")
    start,end=task["start_date"],task["end_date"]
    if (date.fromisoformat(end)-date.fromisoformat(start)).days+1>366:
        raise ValueError("history selection exceeds 366-day safety limit")
    queried,records,other_series=[],[],0
    for a,b in windows(start,end,chunk_days):
        result,urls=fetcher(task["site_id"],task["parameter_code"],a,b,
                            task["concept"],mode="continuous")
        queried.extend(urls)
        for row in result:
            if row["dataset_id"]!="usgs_water" or row["site_id"]!=task["site_id"]:
                raise AcquisitionError("source returned nonmatching dataset/site")
            if row["parameter_code"]!=task["parameter_code"] or row["concept"]!=task["concept"]:
                raise AcquisitionError("source returned nonmatching parameter/concept")
            if row["series_id"]!=task["series_id"]:
                other_series+=1
                continue
            if row["time_basis"]!="explicit_utc_datetime" or not row["timestamp_utc"]:
                raise AcquisitionError("continuous source missing UTC timestamp")
            # Same site could have multiple metrics with different physical units.
            # No inferred conversion or datum transform is permitted.
            if task.get("unit") and row["unit"] and row["unit"]!=task["unit"]:
                raise AcquisitionError("source unit changed; needs explicit unit conversion")
            if row["vertical_datum"]!=task.get("vertical_datum",""):
                raise AcquisitionError("source vertical datum changed")
            records.append(row)
    seen,conflicts,duplicates={},[],0
    for row in records:
        key=(row["series_id"],row["timestamp_utc"])
        old=seen.get(key)
        if old is not None:
            # Even an identical numeric value cannot be silently deduped if
            # source approval or censoring metadata disagree for that instant.
            compare_fields=("original_value","unit","vertical_datum",
                            "approval_status","qualifier","detection_condition")
            if any(old.get(field,"")!=row.get(field,"") for field in compare_fields):
                conflicts.append({"site_id":task["site_id"],"series_id":task["series_id"],
                                  "timestamp_utc":row["timestamp_utc"],
                                  "prior_value":old["original_value"],
                                  "second_value":row["original_value"]})
            else:
                duplicates+=1
        else:
            seen[key]=row
    if conflicts:
        raise AcquisitionError(f"{len(conflicts)} conflicting values for same source-series timestamp")
    return [seen[k] for k in sorted(seen)],queried,other_series,duplicates
