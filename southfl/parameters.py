"""Conservative environmental concept taxonomy and USGS vertical references.

A concept classifies the physical quantity; a vertical_datum is a separate
attribute. Matching concepts are NOT license to combine measurements with
different elevations, unit systems, sublocations, or gage reference surfaces.

USGS parameter definitions: https://api.waterdata.usgs.gov/ogcapi/v1/collections/parameter-codes/items
Groundwater elevations: https://waterservices.usgs.gov/docs/groundwater-levels/groundwater-levels-details/
"""

USGS_PARAMETERS = {
    "00010": "water_temperature",
    "00020": "air_temperature",
    "00045": "precipitation",
    "00060": "discharge",
    "00065": "gage_height",
    "00095": "specific_conductance",
    "00300": "dissolved_oxygen",
    "00400": "ph",
    "00480": "salinity",
    "00600": "nitrogen_total",
    "00631": "nitrate_nitrite",
    "00665": "phosphorus_total",
    "62610": "groundwater_elevation",       # groundwater level above NGVD29
    "62611": "groundwater_elevation",       # groundwater level above NAVD88
    "63158": "stream_stage_elevation",     # stream level above NGVD29
    "63160": "stream_stage_elevation",     # stream level above NAVD88
    "72019": "groundwater_depth_below_land_surface",
    "72255": "water_velocity",              # mean water velocity
    "63680": "turbidity",
}

# For these exact USGS codes, the vertical reference is part of the parameter
# definition; it must remain visible as a separate field in metadata and
# extracted observations. A match on 'groundwater_elevation' alone is not a
# valid time-series merge across NAVD88 and NGVD29.
USGS_CODE_DATUM = {
    "62610": "NGVD29",
    "62611": "NAVD88",
    "63158": "NGVD29",
    "63160": "NAVD88",
}


def _code(value):
    value = str(value or "").strip()
    return value.zfill(5) if value.isdigit() else value


def usgs_concept(code, name=""):
    """Use a verified USGS parameter code first; retain raw name separately."""
    return USGS_PARAMETERS.get(_code(code), wqp_concept(name))


def usgs_vertical_datum(code, source_datum=""):
    """Return documented reference or preserve a source-provided reference.

    No guessed NAVD88/NGVD29 for gage height 00065, depth below ground,
    water velocity or general tidal/coastal water levels. Conflicting
    source-provided datum versus a code-defined datum raises explicitly.
    """
    raw = str(source_datum or "").strip()
    known = USGS_CODE_DATUM.get(_code(code), "")
    if known and raw and raw.upper().replace(" ", "") != known:
        raise ValueError(f"USGS parameter {_code(code)} expects {known}, got {raw!r}")
    return known or raw


def harmonize_period_record(record):
    """Non-mutating migration for existing metadata CSVs of earlier milestones.

    Only known USGS parameter codes are reclassified; other providers'
    concepts remain unchanged. Old records lacking vertical_datum receive
    an empty value, or a documented USGS code-derived reference.
    """
    row = dict(record)
    row.setdefault("vertical_datum", "")
    if row.get("dataset_id") == "usgs_water":
        code = row.get("parameter_code", "")
        row["concept"] = usgs_concept(code, row.get("parameter_name", ""))
        row["vertical_datum"] = usgs_vertical_datum(
            code, row.get("vertical_datum", ""))
    return row


def wqp_concept(name):
    """Best-effort category label; retain original characteristic for science."""
    text = " ".join(str(name or "").casefold().replace("_", " ").split())
    if not text:
        return "unmapped"
    if "dissolved oxygen" in text or text == "oxygen, dissolved":
        return "dissolved_oxygen"
    if "salinity" in text:
        return "salinity"
    if "specific conductance" in text or "specific conductivity" in text:
        return "specific_conductance"
    if "temperature, water" in text or "water temperature" in text:
        return "water_temperature"
    if "temperature, air" in text or "air temperature" in text:
        return "air_temperature"
    if text == "ph" or text.startswith("ph,"):
        return "ph"
    if "chlorophyll a" in text or "chlorophyll-a" in text:
        return "chlorophyll_a"
    if "turbidity" in text or "suspended sediment" in text:
        return "turbidity_or_sediment"
    if "nitrate" in text and "nitrite" in text:
        return "nitrate_nitrite"
    if "nitrogen" in text:
        return "nitrogen_unspecified_fraction"
    if "phosphorus" in text or "phosphate" in text:
        return "phosphorus_unspecified_fraction"
    if "gage height" in text:
        return "gage_height"
    if "water level" in text or "water surface elevation" in text:
        return "water_level"
    if "discharge" in text or "streamflow" in text:
        return "discharge"
    if "rainfall" in text or "precipitation" in text:
        return "precipitation"
    return "unmapped"


PRIORITY = {
    "dissolved_oxygen": 1, "water_temperature": 1, "salinity": 1,
    "water_level": 1, "gage_height": 1, "stream_stage_elevation": 1,
    "groundwater_elevation": 1, "discharge": 1,
    "specific_conductance": 1,
    "nitrogen_total": 2, "phosphorus_total": 2, "nitrate_nitrite": 2,
    "nitrogen_unspecified_fraction": 2, "phosphorus_unspecified_fraction": 2,
    "chlorophyll_a": 2, "turbidity": 2, "turbidity_or_sediment": 2,
    "precipitation": 2, "air_temperature": 2, "ph": 2,
    "water_velocity": 2, "groundwater_depth_below_land_surface": 2,
    "meteorology_package": 2, "unmapped": 99,
}
