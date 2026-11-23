"""Observed-only sample counts for heterogeneous continuous and discrete data."""
from collections import defaultdict
from datetime import date
from .net import write_csv

COVERAGE_COLUMNS = [
    "dataset_id", "site_id", "concept", "measurement_type", "time_basis",
    "planned_start", "planned_end", "n_rows", "n_numeric",
    "n_nonnumeric_or_censored", "n_distinct_sample_dates",
    "first_sample_date", "last_sample_date", "n_units", "units",
    "n_qualified", "n_provisional_or_working", "n_detection_conditions",
    "possible_duplicate_result_ids", "observed_completeness",
    "screening_status",
]


def coverage(rows, tasks):
    expected = {(t["dataset_id"], t["site_id"], t["concept"]): t for t in tasks}
    grouped = defaultdict(list)
    for record in rows:
        key = record["dataset_id"], record["site_id"], record["concept"]
        if key not in expected:
            raise ValueError(f"observation lacks matching planned task: {key}")
        grouped[key].append(record)
    summaries = []
    for key, task in sorted(expected.items()):
        records = grouped[key]
        dates = [r["sample_date"] for r in records if r.get("sample_date")]
        units = sorted({r["unit"] for r in records if r.get("unit")})
        statuses = (";".join([r.get("approval_status", ""), r.get("qualifier", "")])
                    for r in records)
        # We intentionally do not compute an observed completeness fraction
        # without the source's expected observation schedule / survey design.
        duplicated = 0
        seen = set()
        for r in records:
            rid = r.get("result_id", "")
            if not rid:
                continue
            marker = key + (rid,)
            if marker in seen:
                duplicated += 1
            seen.add(marker)
        summaries.append({
            "dataset_id": key[0], "site_id": key[1], "concept": key[2],
            "measurement_type": ";".join(sorted({r["measurement_type"] for r in records})),
            "time_basis": ";".join(sorted({r["time_basis"] for r in records})),
            "planned_start": task["start_date"], "planned_end": task["end_date"],
            "n_rows": len(records), "n_numeric": sum(bool(r.get("value")) for r in records),
            "n_nonnumeric_or_censored": sum(not bool(r.get("value")) for r in records),
            "n_distinct_sample_dates": len(set(dates)),
            "first_sample_date": min(dates) if dates else "",
            "last_sample_date": max(dates) if dates else "",
            "n_units": len(units), "units": ";".join(units),
            "n_qualified": sum(bool(r.get("qualifier")) for r in records),
            "n_provisional_or_working": sum(any(x in (
                r.get("approval_status", "") or "").lower()
                for x in ("provisional", "working")) for r in records),
            "n_detection_conditions": sum(bool(r.get("detection_condition")) for r in records),
            "possible_duplicate_result_ids": duplicated,
            "observed_completeness": "",  # no schedule, never inferred
            "screening_status": ("no_observations_in_requested_window" if not records else
                                 "mixed_units_requires_review" if len(units) > 1 else
                                 "observed_samples_need_qc"),
        })
    return summaries
