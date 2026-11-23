"""Inventory, collision and observed-only daily sample coverage summaries."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from .net import write_csv
from .sources import STATION_COLUMNS

AUDIT_COLUMNS = ["dataset_id", "site_id", "variable", "year", "n_records",
                 "n_distinct_dates", "first_observed_utc", "last_observed_utc",
                 "coverage_basis", "coverage_fraction", "status"]
DUPLICATE_COLUMNS = ["site_id_a", "dataset_id_a", "site_id_b", "dataset_id_b",
                     "distance_m", "collision_type"]


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def validate_stations(rows):
    keys = set()
    for row in rows:
        if not row.get("dataset_id") or not row.get("site_id"):
            raise ValueError("station missing dataset_id/site_id")
        key = (row["dataset_id"], row["site_id"])
        if key in keys:
            raise ValueError(f"duplicate station key {key}")
        keys.add(key)
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("invalid WGS84 coordinates")
    return len(keys)


def coordinate_collisions(rows, threshold_m=75):
    """Flag neighboring sites from *different datasets* for manual review.

    A spatial hash avoids quadratic all-pairs comparisons when the inventory
    reaches tens of thousands of stations. The final meter-distance test uses
    the same local spherical approximation as the original implementation.
    """
    from math import cos, floor, radians, sqrt
    if threshold_m <= 0 or threshold_m > 500:
        raise ValueError("spatial review threshold must be 0-500 meters")
    cell = threshold_m / 111_195
    # At South Florida latitudes (about 24-28 N), 2 adjacent longitude
    # cells are sufficient for distances <= threshold_m.
    buckets = {}
    out = []
    for b in rows:
        lat2, lon2 = float(b["latitude"]), float(b["longitude"])
        x, y = floor(lon2 / cell), floor(lat2 / cell)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-1, 0, 1):
                for a in buckets.get((x + dx, y + dy), []):
                    if a["dataset_id"] == b["dataset_id"]:
                        continue
                    lat1, lon1 = float(a["latitude"]), float(a["longitude"])
                    mid = radians((lat1 + lat2) / 2)
                    distance = sqrt(((lat1-lat2)*111_195)**2 +
                                    ((lon1-lon2)*111_195*cos(mid))**2)
                    if distance <= threshold_m:
                        out.append(dict(
                            site_id_a=a["site_id"], dataset_id_a=a["dataset_id"],
                            site_id_b=b["site_id"], dataset_id_b=b["dataset_id"],
                            distance_m=round(distance, 1),
                            collision_type="spatial_proximity_review_only"))
        buckets.setdefault((x, y), []).append(b)
    return out

def audit_observations(rows):
    """Count ACTUAL observed records by year; never infer hourly coverage from counts.

    Expected columns: dataset_id,site_id,variable,timestamp_utc,value.
    Distinct observation days are reported, but the denominator is undefined
    until a deployment window and expected schedule are known.
    """
    groups = defaultdict(list)
    for row in rows:
        if str(row.get("value", "")).strip() == "":
            continue
        ts = str(row.get("timestamp_utc", ""))
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid observation timestamp: {ts}") from exc
        if dt.tzinfo is None:
            raise ValueError("observation timestamp must have UTC offset")
        dt = dt.astimezone(timezone.utc)
        key = (row["dataset_id"], row["site_id"], row["variable"], dt.year)
        groups[key].append(dt)
    output = []
    for (dataset, site, var, year), stamps in sorted(groups.items()):
        output.append(dict(dataset_id=dataset, site_id=site, variable=var,
                           year=year, n_records=len(stamps),
                           n_distinct_dates=len({d.date() for d in stamps}),
                           first_observed_utc=min(stamps).isoformat(),
                           last_observed_utc=max(stamps).isoformat(),
                           coverage_basis="observed_records_only",
                           coverage_fraction="", status="schedule_unknown"))
    return output


def catalog_inventory(rows, out_dir):
    validate_stations(rows)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "stations.csv", rows, STATION_COLUMNS)
    write_csv(out / "co_location_candidates.csv", coordinate_collisions(rows),
              DUPLICATE_COLUMNS)
    counts = Counter((r["dataset_id"], region) for r in rows
                     for region in (r["regions"].split(";") if r["regions"] else ["unassigned"]))
    write_csv(out / "station_counts_by_region.csv",
              [dict(dataset_id=k[0], region=k[1], n_stations=v)
               for k, v in sorted(counts.items())],
              ["dataset_id", "region", "n_stations"])
