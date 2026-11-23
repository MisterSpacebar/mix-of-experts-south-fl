"""Agency station-discovery adapters; metadata only.

Source-specific schema changes cause explicit errors. These endpoints are
queried live when requested; returned station locations are not observations.
"""
from datetime import datetime, timezone
from urllib.parse import urljoin
from .net import AcquisitionError, get_json, get_csv, get_xml, url_with_params
from .regions import DOMAIN, inside

STATION_COLUMNS = ["dataset_id", "provider", "site_id", "site_name", "latitude",
                   "longitude", "regions", "source_url", "retrieved_at_utc",
                   "location_type", "coverage_status"]
MAX_PAGES = 30


def _time():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def station(dataset_id, provider, sid, name, lat, lon, source, kind="unknown"):
    try:
        lat, lon = float(lat), float(lon)
    except (ValueError, TypeError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    from .regions import regions_for
    return dict(dataset_id=dataset_id, provider=provider, site_id=str(sid),
                site_name=str(name or sid), latitude=lat, longitude=lon,
                regions=";".join(regions_for(lat, lon)), source_url=source,
                retrieved_at_utc=_time(), location_type=kind,
                coverage_status="metadata_only")


def _unique(rows):
    by_id = {}
    for row in rows:
        if row is None:
            continue
        key = (row["dataset_id"], row["site_id"])
        if key in by_id and (row["latitude"], row["longitude"]) != (
                by_id[key]["latitude"], by_id[key]["longitude"]):
            raise AcquisitionError(f"conflicting coordinates for {key}")
        by_id[key] = row
    return sorted(by_id.values(), key=lambda r: (r["dataset_id"], r["site_id"]))


def coops(bbox=DOMAIN):
    """NOAA CO-OPS MDAPI station metadata: water-level station candidate set."""
    base = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    url = url_with_params(base, {"type": "waterlevels", "units": "metric"})
    data = get_json(url)
    if not isinstance(data.get("stations"), list):
        raise AcquisitionError("CO-OPS response lacks stations")
    rows = []
    for s in data["stations"]:
        row = station("noaa_coops", "NOAA CO-OPS", s.get("id"), s.get("name"),
                      s.get("lat"), s.get("lng"), url, "water-level station")
        if row and inside(row["latitude"], row["longitude"], bbox):
            rows.append(row)
    return _unique(rows)


def ndbc(bbox=DOMAIN):
    """NDBC active station metadata only; historical stations need a separate pass."""
    url = "https://www.ndbc.noaa.gov/activestations.xml"
    root = get_xml(url)
    rows = []
    for s in root.iter("station"):
        sid = s.attrib.get("id")
        row = station("noaa_ndbc", "NOAA NDBC", sid, s.attrib.get("name", sid),
                      s.attrib.get("lat"), s.attrib.get("lon"), url,
                      "active buoy or coastal station")
        if row and inside(row["latitude"], row["longitude"], bbox):
            rows.append(row)
    if not rows:
        raise AcquisitionError("NDBC returned no stations in the discovery bounds")
    return _unique(rows)


def usgs(bbox=DOMAIN, page_size=1000, max_pages=MAX_PAGES):
    """USGS Water Data OGC monitoring-locations, paginated.

    Broad domain queries may exceed page limits: raise rather than silently
    report partial coverage.
    """
    base = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/monitoring-locations/items"
    next_url = url_with_params(base, {
        "bbox": ",".join(str(v) for v in bbox), "limit": page_size, "f": "json"})
    rows, visited = [], set()
    for _ in range(max_pages):
        if next_url in visited:
            raise AcquisitionError("USGS pagination cycle")
        visited.add(next_url)
        data = get_json(next_url)
        if "features" not in data:
            raise AcquisitionError("USGS OGC response missing features")
        for feature in data["features"]:
            p = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") or []
            if len(coords) < 2:
                continue
            sid = p.get("monitoring_location_number") or p.get("id") or feature.get("id")
            name = p.get("monitoring_location_name") or p.get("site_name") or sid
            row = station("usgs_water", "USGS", sid, name, coords[1], coords[0],
                          base, "monitoring location")
            if row and inside(row["latitude"], row["longitude"], bbox):
                rows.append(row)
        links = data.get("links") or []
        next_url = next((urljoin(base, l["href"]) for l in links
                         if l.get("rel") == "next" and l.get("href")), None)
        if not next_url:
            return _unique(rows)
        if not next_url.startswith("https://api.waterdata.usgs.gov/"):
            raise AcquisitionError("USGS pagination redirected to an unexpected host")
    raise AcquisitionError("USGS pagination exceeded max_pages: split into smaller boxes")


def wqp(bbox=DOMAIN):
    """Water Quality Portal station CSV from current station search service.

    Endpoint returns monitoring-site metadata, not result availability.
    WQP can duplicate FDEP WIN records.
    """
    base = "https://www.waterqualitydata.us/data/Station/search"
    url = url_with_params(base, {
        "bBox": ",".join(str(v) for v in bbox),
        "mimeType": "csv", "zip": "no"})
    data = get_csv(url)
    rows = []
    for s in data:
        sid = s.get("MonitoringLocationIdentifier")
        row = station("epa_wqp", "Water Quality Portal", sid,
                      s.get("MonitoringLocationName"),
                      s.get("LatitudeMeasure"), s.get("LongitudeMeasure"),
                      url, "water-quality monitoring location")
        if row and sid and inside(row["latitude"], row["longitude"], bbox):
            rows.append(row)
    return _unique(rows)


ADAPTERS = {"coops": coops, "ndbc": ndbc, "usgs": usgs, "wqp": wqp}
