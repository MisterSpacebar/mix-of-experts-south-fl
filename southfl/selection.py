"""Stratified, metadata-only selection of *candidate* observation downloads.

No training-readiness claim. Explicit time windows are chosen from known
source period hints where possible; no claim that these windows contain data.
"""
from collections import defaultdict
from datetime import date, timedelta

PLAN_COLUMNS = ["dataset_id", "site_id", "region", "concept", "parameter_code",
                "parameter_name", "start_date", "end_date", "usgs_mode",
                "evidence", "last_date_hint", "selection_status"]


def plan(periods, stations, end_date, max_total=18, per_region=3,
         per_source=7, usgs_mode="continuous", days_usgs=14, days_wqp=365,
         days_coops=14):
    end = date.fromisoformat(end_date)
    if max_total < 1 or max_total > 50 or per_region < 1 or per_source < 1:
        raise ValueError("max_total 1-50, per_region and per_source >= 1 required")
    if usgs_mode not in ("continuous", "daily"):
        raise ValueError("USGS mode must be continuous or daily")
    if not (1 <= days_usgs <= (45 if usgs_mode == "daily" else 21)):
        raise ValueError("USGS pilot must use a small bounded window")
    if not (1 <= days_wqp <= 366 and 1 <= days_coops <= 28):
        raise ValueError("WQP max 366 days; CO-OPS max 28 days")
    allowed = {"usgs_water": "usgs", "epa_wqp": "wqp", "noaa_coops": "coops"}
    # Rank familiar physical variables and chemistry, while preserving
    # site/characteristic identity and allowing ecological additions later.
    concept_order = {
        "dissolved_oxygen": 0, "salinity": 1, "water_temperature": 2,
        "water_level": 3, "discharge": 4, "specific_conductance": 5,
        "chlorophyll_a": 6, "nitrogen_total": 7, "phosphorus_total": 8,
        "nitrate_nitrite": 9, "nitrogen_unspecified_fraction": 10,
        "phosphorus_unspecified_fraction": 11, "turbidity": 12, "ph": 13,
    }
    by_site = {(s["dataset_id"], s["site_id"]): s for s in stations}
    candidates = {}
    for row in periods:
        dataset = row["dataset_id"]
        concept = row["concept"]
        if dataset not in allowed or concept not in concept_order:
            continue
        key = dataset, row["site_id"]
        if key not in by_site:
            continue
        if dataset == "usgs_water" and (not row["parameter_code"].isdigit() or
                                        len(row["parameter_code"]) != 5):
            continue
        if dataset == "epa_wqp" and not row["parameter_name"]:
            continue
        if dataset == "usgs_water":
            hint = (row["end_utc"] or "")[:10]
            days = days_usgs
        elif dataset == "epa_wqp":
            hint = (row["year"] + "-12-31") if row["year"] else ""
            days = days_wqp
        else:
            hint = ""
            days = days_coops
        try:
            candidate_end = min(end, date.fromisoformat(hint)) if hint else end
        except ValueError:
            continue
        # Exclude pre-2020 datasets for the first *pilot*, not from the catalog.
        if candidate_end.year < 2020:
            continue
        beginning = candidate_end - timedelta(days=days - 1)
        if dataset == "usgs_water" and row.get("begin_utc"):
            try:
                beginning = max(beginning, date.fromisoformat(row["begin_utc"][:10]))
            except ValueError:
                continue
        if beginning > candidate_end:
            continue
        site = by_site[key]
        regions = [x for x in site.get("regions", "").split(";") if x]
        if not regions:
            continue
        # Every candidate retains a source-defined concept and raw name.
        for region in regions:
            candidate = dict(
                dataset_id=dataset, site_id=row["site_id"], region=region,
                concept=concept, parameter_code=row["parameter_code"],
                parameter_name=row["parameter_name"],
                start_date=beginning.isoformat(), end_date=candidate_end.isoformat(),
                usgs_mode=usgs_mode if dataset == "usgs_water" else "",
                evidence=row["evidence"], last_date_hint=hint,
                selection_status="candidate_not_verified",
            )
            signature = (dataset, row["site_id"], region, concept)
            old = candidates.get(signature)
            score = (candidate_end.isoformat(), row["series_id"])
            if old is None or score > old[0]:
                candidates[signature] = score, candidate
    # Region balancing: one top-ranked candidate per region each pass, then
    # repeat. Prefer distinct sources, stations and concept types.
    grouped = defaultdict(list)
    for _, candidate in candidates.values():
        grouped[candidate["region"]].append(candidate)
    for region, items in grouped.items():
        items.sort(key=lambda a: (
            concept_order[a["concept"]], -int(a["end_date"].replace("-", "")),
            a["dataset_id"], a["site_id"], a["parameter_name"]))
    chosen, source_count, region_count, visited = [], defaultdict(int), defaultdict(int), set()
    regions = sorted(grouped)
    while len(chosen) < max_total:
        progress = False
        for region in regions:
            if region_count[region] >= per_region:
                continue
            queue = grouped[region]
            while queue:
                c = queue.pop(0)
                stable = (c["dataset_id"], c["site_id"], c["concept"])
                if stable in visited or source_count[c["dataset_id"]] >= per_source:
                    continue
                chosen.append(c)
                visited.add(stable)
                source_count[c["dataset_id"]] += 1
                region_count[region] += 1
                progress = True
                break
            if len(chosen) >= max_total:
                break
        if not progress:
            break
    return chosen
