"""Fetch observed NOAA CO-OPS water levels into a provenance-aware CSV.

Example:
python scripts/fetch_coops.py --station 8724580 --begin 20260101 --end 20260107
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
COLUMNS = ["source", "station", "timestamp_utc", "water_level_m", "datum",
           "quality_flag", "query_url"]


def validate_date(value):
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYYMMDD") from exc
    return value


def request_observations(station, begin, end, datum="MLLW"):
    if not station.isdigit():
        raise ValueError("station must be a numeric NOAA CO-OPS station ID")
    if end < begin:
        raise ValueError("end must not precede begin")
    params = {
        "product": "water_level",
        "application": "south_florida_fcm",
        "begin_date": begin,
        "end_date": end,
        "datum": datum,
        "station": station,
        "time_zone": "gmt",
        "units": "metric",
        "format": "json",
    }
    url = BASE + "?" + urlencode(params)
    with urlopen(url, timeout=45) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(f"CO-OPS error: {payload['error']}")
    if "data" not in payload:
        raise RuntimeError("CO-OPS response missing data")
    rows = []
    for item in payload["data"]:
        try:
            dt = datetime.strptime(item["t"], "%Y-%m-%d %H:%M")
            value = float(item["v"])
        except (ValueError, TypeError, KeyError):
            continue
        rows.append({
            "source": "noaa_coops",
            "station": station,
            "timestamp_utc": dt.strftime("%Y-%m-%dT%H:%M:00Z"),
            "water_level_m": value,
            "datum": datum,
            "quality_flag": item.get("f", ""),
            "query_url": url,
        })
    return rows, url


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--station", required=True, help="numeric NOAA station ID")
    p.add_argument("--begin", required=True, type=validate_date)
    p.add_argument("--end", required=True, type=validate_date)
    p.add_argument("--datum", default="MLLW")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    rows, url = request_observations(args.station, args.begin, args.end, args.datum)
    path = args.out or Path("data/raw/noaa_coops") / f"{args.station}_{args.begin}_{args.end}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} observations to {path}")
    print(f"Source: {url}")


if __name__ == "__main__":
    main()
