"""Conservative concept mapping for parameter *metadata*, not observations.

Raw analyte/parameter names are retained. Ambiguous nutrient fractions are
NOT silently promoted to total nitrogen, dissolved inorganic nitrogen, etc.
"""

USGS_PARAMETERS = {
    "00010": "water_temperature",
    "00020": "air_temperature",
    "00045": "precipitation",
    "00060": "discharge",
    "00065": "water_level",
    "00095": "specific_conductance",
    "00300": "dissolved_oxygen",
    "00400": "ph",
    "00480": "salinity",
    "00600": "nitrogen_total",
    "00631": "nitrate_nitrite",
    "00665": "phosphorus_total",
    "63680": "turbidity",
}


def usgs_concept(code, name=""):
    """Prefer the known five-character parameter code; never drop raw name."""
    return USGS_PARAMETERS.get(str(code).zfill(5), wqp_concept(name))


def wqp_concept(name):
    """Best-effort category label. Keep original characteristic for science."""
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
    if "gage height" in text or "water level" in text or "water surface elevation" in text:
        return "water_level"
    if "discharge" in text or "streamflow" in text:
        return "discharge"
    if "rainfall" in text or "precipitation" in text:
        return "precipitation"
    return "unmapped"


PRIORITY = {
    "dissolved_oxygen": 1, "water_temperature": 1, "salinity": 1,
    "water_level": 1, "discharge": 1, "specific_conductance": 1,
    "nitrogen_total": 2, "phosphorus_total": 2, "nitrate_nitrite": 2,
    "nitrogen_unspecified_fraction": 2, "phosphorus_unspecified_fraction": 2,
    "chlorophyll_a": 2, "turbidity": 2, "turbidity_or_sediment": 2,
    "precipitation": 2, "air_temperature": 2, "ph": 2,
    "meteorology_package": 2, "unmapped": 99,
}
