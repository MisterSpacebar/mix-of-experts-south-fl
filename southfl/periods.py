"""Period-of-record discovery adapters. No measurement values are downloaded.

The normalized rows are evidence about *availability*, not proof of continuous
coverage; long time-series gaps and survey intermittency are not estimated.
"""
from datetime import datetime, timezone
import re
from urllib.parse import urljoin
from .net import AcquisitionError, get_bytes, get_csv, get_json, url_with_params
from .parameters import usgs_concept, wqp_concept

PERIOD_COLUMNS = [
    "dataset_id", "site_id", "series_id", "parameter_code", "parameter_name",
    "concept", "unit", "series_type", "statistic_id", "sublocation_identifier",
    "primary_status", "data_gap_interval", "begin_utc", "end_utc", "year",
    "n_results", "n_activities", "evidence", "quality_note", "source_url",
    "region_query", "in_station_inventory",
]
USGS_URL = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/items"
WQP_URL = "https://waterqualitydata.us/data/summary/monitoringLocation/search"
COOPS_ROOT = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations"
NDBC_INDEX = "https://www.ndbc.noaa.gov/data/historical/stdmet/"
WQP_TYPES = ("Nutrient", "Physical")


def _row(dataset, site, series, code="", name="", concept="unmapped", unit="",
         series_type="", statistic_id="", sublocation="", primary="",
         gap_interval="", begin="", end="", year="", results="", activities="",
         evidence="", note="", url="", region="", inventory=""):
    return dict(dataset_id=dataset, site_id=str(site), series_id=str(series),
                parameter_code=str(code), parameter_name=str(name),
                concept=str(concept), unit=str(unit), series_type=str(series_type),
                statistic_id=str(statistic_id or ""),
                sublocation_identifier=str(sublocation or ""),
                primary_status=str(primary if primary is not None else ""),
                data_gap_interval=str(gap_interval or ""),
                begin_utc=str(begin or ""), end_utc=str(end or ""), year=str(year or ""),
                n_results=str(results if results is not None else ""),
                n_activities=str(activities if activities is not None else ""),
                evidence=evidence, quality_note=note, source_url=url,
                region_query=region, in_station_inventory=inventory)


def _known(site_id, allowed):
    return "yes" if site_id in allowed else "no"


def _url_only_api(url):
    return url.startswith("https://api.waterdata.usgs.gov/")


def usgs_periods(bbox, allowed, region="", limit=1000, max_pages=60):
    """USGS OGC time-series metadata using geographic pagination.

    Filter by dataset and known canonical station ID. We retain one row per
    source time series (including statistic and location subtype in the ID).
    """
    params = {"bbox": ",".join(map(str, bbox)), "limit": limit, "f": "json"}
    next_url = url_with_params(USGS_URL, params)
    rows, visited = [], set()
    for page in range(max_pages):
        if next_url in visited:
            raise AcquisitionError("USGS metadata pagination cycle")
        visited.add(next_url)
        payload = get_json(next_url)
        if not isinstance(payload.get("features"), list):
            raise AcquisitionError("USGS time-series metadata response missing features")
        for feature in payload["features"]:
            p = feature.get("properties") or {}
            site = str(p.get("monitoring_location_id") or "").strip()
            if not site or site not in allowed:
                continue
            code = str(p.get("parameter_code") or "").zfill(5)
            name = str(p.get("parameter_name") or p.get("parameter_description") or "")
            ts_id = str(p.get("time_series_id") or feature.get("id") or "").strip()
            if not ts_id:
                raise AcquisitionError("USGS time-series metadata missing series id")
            rows.append(_row(
                "usgs_water", site, ts_id, code=code, name=name,
                concept=usgs_concept(code, name), unit=p.get("unit_of_measure") or "",
                series_type=str(p.get("computation_identifier") or "unspecified"),
                statistic_id=p.get("statistic_id"),
                sublocation=p.get("sublocation_identifier"),
                primary=p.get("primary"),
                gap_interval=p.get("data_gap_interval"),
                # OGC v1 renamed UTC fields to begin/end; v0 used begin_utc/end_utc.
                begin=p.get("begin") or p.get("begin_utc"),
                end=p.get("end") or p.get("end_utc"),
                evidence="time_series_first_last_metadata",
                note="Time series can contain substantial gaps; metadata is not completeness",
                url=next_url, region=region, inventory="yes"))
        href = next((link.get("href") for link in payload.get("links", [])
                     if link.get("rel") == "next" and link.get("href")), None)
        if not href:
            return rows
        next_url = urljoin(next_url, href)
        if not _url_only_api(next_url):
            raise AcquisitionError("USGS metadata pagination uses unexpected host")
    raise AcquisitionError("USGS metadata exceeded page cap; use smaller boxes")


def wqp_periods(bbox, allowed, region="", characteristic_type="Nutrient",
                years="5"):
    """EPA Water Quality Portal annual summary (not raw chemistry results)."""
    if characteristic_type not in WQP_TYPES:
        raise ValueError("WQP type must be Nutrient or Physical")
    if str(years) not in ("1", "5", "all"):
        raise ValueError("WQP years must be 1, 5, or all")
    url = url_with_params(WQP_URL, {
        "bBox": ",".join(map(str, bbox)), "characteristicType": characteristic_type,
        "mimeType": "csv", "zip": "no", "dataProfile": "periodOfRecord",
        "summaryYears": str(years),
    })
    records = get_csv(url)
    if records and not {"MonitoringLocationIdentifier", "CharacteristicName",
                        "YearSummarized", "ResultCount", "ActivityCount"}.issubset(records[0]):
        raise AcquisitionError("WQP periodOfRecord schema mismatch; inspect API response")
    rows = []
    for p in records:
        site = str(p.get("MonitoringLocationIdentifier") or "").strip()
        if not site or site not in allowed:
            continue
        raw_name = str(p.get("CharacteristicName") or "").strip()
        if not raw_name:
            raise AcquisitionError("WQP period summary missing characteristic name")
        year = str(p.get("YearSummarized") or "").strip()
        if not re.fullmatch(r"(19|20)\d\d", year):
            raise AcquisitionError(f"WQP returned invalid YearSummarized: {year!r}")
        for field in ("ResultCount", "ActivityCount"):
            if not str(p.get(field, "")).strip().isdigit():
                raise AcquisitionError(f"WQP invalid {field} for {site}: {p.get(field)!r}")
        provider = str(p.get("Provider") or "unspecified")
        organization = str(p.get("OrganizationIdentifier") or "")
        # Each characteristic/year/provider is a distinct summary slice.
        key = "|".join([provider, organization, site, raw_name, year])
        rows.append(_row(
            "epa_wqp", site, key, name=raw_name, concept=wqp_concept(raw_name),
            series_type=characteristic_type, year=year, results=p["ResultCount"],
            activities=p["ActivityCount"], evidence="annual_result_and_activity_counts",
            note="Counts are annual; no day-level coverage, fraction, depth or lab detection limits",
            url=url, region=region, inventory="yes"))
    return rows


def coops_periods(site_ids, region="domain"):
    """Water-level station product CANDIDATES; no observed first/last dates."""
    rows = []
    for site in sorted(site_ids):
        if not site.isdigit():
            raise AcquisitionError(f"unexpected NOAA water-level station id: {site!r}")
        url = f"{COOPS_ROOT}/{site}.json?expand=details,products"
        p = get_json(url)
        if not isinstance(p, dict) or str(p.get("id") or "") != site:
            raise AcquisitionError(f"CO-OPS station metadata mismatch for {site}")
        details = p.get("details") or {}
        # 'established'/'removed' are installation dates, NOT observed data availability.
        stamp = "; ".join(f"{key}={details[key]}" for key in ("established", "removed")
                          if details.get(key))
        rows.append(_row(
            "noaa_coops", site, site + "|water_level_candidate",
            name="Observed water level (candidate)", concept="water_level",
            series_type="water_level_station", evidence="station_class_only",
            note="Station dates are NOT observation periods. " + stamp,
            url=url, region=region, inventory="yes"))
    return rows


def ndbc_periods(site_ids, region="domain"):
    """List standard-met historical FILE years, not per-parameter coverage.

    Parse the NDBC public directory listing without fetching any .gz files.
    NDBC currently exposes archives as <station>h<year>.txt.gz. A file
    does not guarantee that any one sensor field has usable data.
    """
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hrefs = []
        def handle_starttag(self, tag, attrs):
            if tag.lower() == "a":
                self.hrefs.extend([v for k, v in attrs if k.lower() == "href" and v])
    parser = Links()
    parser.feed(get_bytes(NDBC_INDEX).decode("utf-8", "replace"))
    rows = []
    candidates = {s.upper(): s for s in site_ids}
    for path in parser.hrefs:
        filename = path.rsplit("/", 1)[-1]
        match = re.fullmatch(r"([A-Za-z0-9]+)h((?:19|20)\d\d)\.txt\.gz", filename)
        if not match:
            continue
        station, year = match.groups()
        if station.upper() not in candidates:
            continue
        sid = candidates[station.upper()]
        rows.append(_row(
            "noaa_ndbc", sid, sid + "|stdmet|" + year,
            name="Standard meteorological historical archive",
            concept="meteorology_package", series_type="annual_archive",
            year=year, evidence="historical_file_exists",
            note="Archive existence does not prove per-variable measurements or completeness",
            url=urljoin(NDBC_INDEX, filename), region=region, inventory="yes"))
    return rows
