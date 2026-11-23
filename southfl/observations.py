"""Bounded observed-data acquisition; no imputation and no temporal alignment.

Each record retains the source unit, method, status, and time basis. The
downloaders validate agency site/parameter identity rather than silently
discarding unexpected records.
"""
from datetime import date, datetime, timezone
from urllib.parse import urljoin
from .net import AcquisitionError, get_csv, get_json, url_with_params
from .parameters import usgs_concept, wqp_concept

USGS_BASE = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
WQP_RESULT = "https://waterqualitydata.us/data/Result/search"
COLS = [
    "dataset_id", "site_id", "series_id", "concept", "parameter_code",
    "parameter_name", "measurement_type", "timestamp_utc", "sample_date",
    "time_basis", "value", "original_value", "unit", "approval_status",
    "qualifier", "detection_condition", "activity_id", "result_id",
    "fraction", "sample_depth_value", "sample_depth_unit", "method",
    "vertical_datum", "source_url",
]


def _numeric(value):
    """Preserve reported raw strings; do not turn censored values into zero."""
    if value is None or str(value).strip() == "":
        return ""
    try:
        n = float(str(value))
    except ValueError:
        return ""
    from math import isfinite
    return str(value) if isfinite(n) else ""


def _row(**kwargs):
    record = {column: "" for column in COLS}
    record.update(kwargs)
    unknown = set(kwargs) - set(COLS)
    if unknown:
        raise ValueError(f"unrecognized normalized observation fields: {unknown}")
    return record


def _utc_timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise AcquisitionError(f"invalid source timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise AcquisitionError(f"source timestamp lacks timezone: {value!r}")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise AcquisitionError(f"invalid source sample date: {value!r}") from exc


def usgs_observations(site, code, start, end, concept, mode="daily",
                      max_pages=15, page_size=1000, max_records=15000):
    if mode not in ("daily", "continuous"):
        raise ValueError("USGS mode must be daily or continuous")
    if not site or not str(code).isdigit() or len(str(code)) != 5:
        raise ValueError("USGS requires a site and five-character parameter code")
    base = f"{USGS_BASE}/{mode}/items"
    url = url_with_params(base, {
        "f": "json", "monitoring_location_id": site,
        "parameter_code": code, "time": start + "/" + end,
        "limit": page_size,
    })
    data, links, visited = [], [], set()
    for _ in range(max_pages):
        if url in visited:
            raise AcquisitionError("USGS observation pagination cycle")
        visited.add(url)
        response = get_json(url)
        if not isinstance(response.get("features"), list):
            raise AcquisitionError("USGS observation schema missing features")
        for f in response["features"]:
            p = f.get("properties") or {}
            # Fail if query was ignored by API rather than accepting network-wide data.
            if str(p.get("monitoring_location_id")) != site or str(
                    p.get("parameter_code")).zfill(5) != code:
                raise AcquisitionError("USGS observation site/parameter query mismatch")
            raw_time = str(p.get("time") or "")
            if mode == "daily":
                day = _date(raw_time[:10])
                when, time_basis = "", "source_daily_calendar_date"
            else:
                when = _utc_timestamp(raw_time)
                day, time_basis = when[:10], "explicit_utc_datetime"
            if not (date.fromisoformat(start) <= date.fromisoformat(day) <= date.fromisoformat(end)):
                raise AcquisitionError("USGS returned observation outside requested time window")
            raw = p.get("value")
            approvals = p.get("approval_status", p.get("approvals_status", ""))
            if isinstance(approvals, list):
                approvals = ";".join(map(str, approvals))
            qualifier = p.get("qualifier") or ""
            if isinstance(qualifier, list):
                qualifier = ";".join(map(str, qualifier))
            data.append(_row(
                dataset_id="usgs_water", site_id=site,
                series_id=str(p.get("time_series_id") or p.get("timeseries_id") or ""),
                concept=concept, parameter_code=code,
                parameter_name=str(p.get("parameter_name") or ""),
                measurement_type="daily_statistic" if mode == "daily" else "instantaneous",
                timestamp_utc=when, sample_date=day, time_basis=time_basis,
                value=_numeric(raw), original_value=str(raw if raw is not None else ""),
                unit=str(p.get("unit_of_measure") or ""),
                approval_status=str(approvals or ""), qualifier=str(qualifier),
                result_id=str(f.get("id") or ""), source_url=url,
            ))
        links.append(url)
        if len(data) > max_records:
            raise AcquisitionError("USGS observations exceed bounded pilot cap")
        href = next((x.get("href") for x in response.get("links", [])
                     if x.get("rel") == "next" and x.get("href")), None)
        if not href:
            return data, links
        url = urljoin(url, href)
        if not url.startswith("https://api.waterdata.usgs.gov/"):
            raise AcquisitionError("unexpected USGS pagination host")
    raise AcquisitionError("USGS observation page cap reached; shorten window")


def wqp_observations(site, characteristic, start, end, concept,
                     max_records=15000):
    if not site or not characteristic:
        raise ValueError("WQP requires site and exact source characteristic")
    begin = date.fromisoformat(start).strftime("%m-%d-%Y")
    finish = date.fromisoformat(end).strftime("%m-%d-%Y")
    url = url_with_params(WQP_RESULT, {
        "siteid": site, "characteristicName": characteristic,
        "startDateLo": begin, "startDateHi": finish,
        "mimeType": "csv", "zip": "no", "sorted": "no",
    })
    source = get_csv(url)
    if len(source) > max_records:
        raise AcquisitionError("WQP results exceed bounded pilot cap")
    if source and not {"MonitoringLocationIdentifier", "ActivityStartDate",
                       "CharacteristicName"}.issubset(source[0]):
        raise AcquisitionError("WQP result field schema mismatch")
    data = []
    for item in source:
        if (item.get("MonitoringLocationIdentifier") != site or
                item.get("CharacteristicName") != characteristic):
            raise AcquisitionError("WQP returned unexpected site/characteristic")
        day = _date(item.get("ActivityStartDate"))
        if not (date.fromisoformat(start) <= date.fromisoformat(day) <= date.fromisoformat(end)):
            raise AcquisitionError("WQP returned sample outside requested date window")
        raw = item.get("ResultMeasureValue")
        data.append(_row(
            dataset_id="epa_wqp", site_id=site, concept=concept,
            parameter_name=characteristic, measurement_type="discrete_sample",
            timestamp_utc="", sample_date=day,
            time_basis="source_local_date_not_utc",
            value=_numeric(raw),
            original_value=str(raw if raw is not None else ""),
            unit=str(item.get("ResultMeasure/MeasureUnitCode") or ""),
            approval_status=str(item.get("ResultStatusIdentifier") or ""),
            qualifier=str(item.get("ResultValueTypeName") or ""),
            detection_condition=str(item.get("ResultDetectionConditionText") or ""),
            activity_id=str(item.get("ActivityIdentifier") or ""),
            result_id=str(item.get("ResultIdentifier") or ""),
            fraction=str(item.get("ResultSampleFractionText") or ""),
            sample_depth_value=str(item.get("ActivityDepthHeightMeasure/MeasureValue") or ""),
            sample_depth_unit=str(item.get("ActivityDepthHeightMeasure/MeasureUnitCode") or ""),
            method=str(item.get("ResultAnalyticalMethod/MethodIdentifier") or ""),
            source_url=url,
        ))
    return data, [url]


def coops_observations(site, start, end, datum="MLLW"):
    """NOAA six-minute observed levels; request at most 28 days per station."""
    from scripts.fetch_coops import request_observations
    if (date.fromisoformat(end) - date.fromisoformat(start)).days > 27:
        raise ValueError("NOAA six-minute pilot must span at most 28 calendar days")
    rows, url = request_observations(
        site, start.replace("-", ""), end.replace("-", ""), datum)
    data = [_row(
        dataset_id="noaa_coops", site_id=site, series_id=site+"|water_level",
        concept="water_level", measurement_type="observed_six_minute",
        timestamp_utc=record["timestamp_utc"],
        sample_date=record["timestamp_utc"][:10],
        time_basis="explicit_utc_datetime",
        value=_numeric(record["water_level_m"]),
        original_value=str(record["water_level_m"]),
        unit="m", qualifier=str(record.get("quality_flag") or ""),
        vertical_datum=datum, source_url=url) for record in rows]
    return data, [url]
