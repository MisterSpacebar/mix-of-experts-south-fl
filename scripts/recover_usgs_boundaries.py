"""Recover real UTC request-endpoint observations without changing old runs.

Dry-run default. Requires exact source identity preflight on execution.
Only old 14-day endpoints are requested; other gaps remain observed gaps.
"""
import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.historical import fetch_series, windows
from southfl.history_selection import PLAN_COLS
from southfl.net import AcquisitionError, write_csv
from southfl.observations import COLS
from southfl.readiness import parse_timestamp
from southfl.temporal_integrity import verify_historical_hash, window_coverage

COMPARE = ("original_value", "value", "unit", "vertical_datum",
           "approval_status", "qualifier", "detection_condition")
AUDIT_COLS = ["site_id", "series_id", "concept", "date", "before",
              "returned", "added", "after", "status", "error"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(row):
    ts = parse_timestamp(row["timestamp_utc"])
    if ts is None or ts.date().isoformat() != row["sample_date"]:
        raise ValueError("invalid UTC observation")
    return row["site_id"], row["series_id"], ts.isoformat()


def validate_row(row, task):
    if any(row[k] != task[k] for k in
           ("dataset_id", "site_id", "series_id", "parameter_code",
            "concept", "unit", "vertical_datum")):
        raise ValueError("source observation identity/unit/datum mismatch")
    if (row["time_basis"] != "explicit_utc_datetime" or
            not task["start_date"] <= row["sample_date"] <= task["end_date"]):
        raise ValueError("source observation outside original UTC plan")
    return key(row)


def merge_rows(existing, incoming, task, day):
    """Retain originals; refuse changed values/flags at overlapping instants."""
    added = 0
    for row in incoming:
        ident = validate_row(row, task)
        if row["sample_date"] != day:
            raise ValueError("repair response outside requested boundary day")
        old = existing.get(ident)
        if old is not None:
            if any(old[k] != row[k] for k in COMPARE):
                raise ValueError("overlapping source record changed; use reviewed full redownload")
        else:
            existing[ident] = row
            added += 1
    return added


def run(history, out, identity=None, execute=False, max_requests=80, delay=2):
    history, out = Path(history), Path(out)
    if not 1 <= max_requests <= 200 or not 0 <= delay <= 30:
        raise ValueError("invalid request cap or delay")
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty recovery output required")
    original_manifest = history/"history_manifest.json"
    source = json.loads(original_manifest.read_text(encoding="utf-8"))
    if source.get("n_failed_tasks") != 0 or source.get("incomplete_panels"):
        raise ValueError("repair requires a successful original history run")
    if source.get("continuous_interval_policy"):
        raise ValueError("history already uses an explicit interval policy")
    original_plan = history/"history_plan_used.csv"
    raw = history/"observations.csv"
    lineage = {"plan": verify_historical_hash(original_plan, source["plan_sha256"]),
               "observations": verify_historical_hash(raw, source["observations_sha256"])}
    tasks = read_csv(original_plan)
    if not tasks or len(tasks) != source["n_tasks"]:
        raise ValueError("original task count mismatch")
    if any(not set(PLAN_COLS).issubset(t) or t["dataset_id"] != "usgs_water"
           or t["mode"] != "continuous" for t in tasks):
        raise ValueError("invalid original history plan")
    by_id = {(t["site_id"], t["series_id"]): t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("duplicate source series")
    jobs = [(t, end) for t in tasks
            for _, end in windows(t["start_date"], t["end_date"])]
    if len(jobs) > max_requests:
        raise ValueError("boundary repair exceeds request cap")
    result = {"original_history": str(history), "original_manifest_sha256": sha(original_manifest),
              "original_lineage": lineage, "n_boundary_series_requests": len(jobs),
              "n_tasks": len(tasks), "regional_fcms_trained": 0}
    if not execute:
        return dict(result, status="dry_run")
    if identity is None:
        raise ValueError("fresh exact source identity preflight required")
    identity = Path(identity)
    identity_manifest = identity/"identity_manifest.json"
    verified = json.loads(identity_manifest.read_text(encoding="utf-8"))
    verified_plan = identity/"history_plan.csv"
    if (verified.get("source_identity_verified") is not True or
            verified.get("n_failed_or_unattempted_tasks") != 0 or
            verified.get("n_changed_series_ids") != 0 or
            verified.get("n_verified_tasks") != len(tasks)):
        raise ValueError("fresh preflight must verify every unchanged source ID")
    result["fresh_identity_manifest_sha256"] = sha(identity_manifest)
    result["fresh_identity_plan_lineage"] = verify_historical_hash(
        verified_plan, verified["verified_plan_sha256"])
    if read_csv(verified_plan) != tasks:
        raise ValueError("fresh verified plan differs from original task identities/window")
    existing = {}
    counts = Counter()
    original_rows = read_csv(raw)
    if len(original_rows) != source["n_observations"]:
        raise ValueError("original observation count mismatch")
    for row in original_rows:
        task = by_id.get((row["site_id"], row["series_id"]))
        if task is None:
            raise ValueError("unexpected series in original raw snapshot")
        ident = validate_row(row, task)
        if ident in existing:
            raise ValueError("duplicate original source timestamp")
        existing[ident] = row
        counts[(row["site_id"], row["series_id"], row["sample_date"])] += 1
    del original_rows
    out.mkdir(parents=True, exist_ok=True)
    audit, added_total = [], 0
    for idx, (task, day) in enumerate(jobs):
        k = (task["site_id"], task["series_id"], day)
        before = counts[k]
        entry = dict(site_id=k[0], series_id=k[1], concept=task["concept"],
                     date=day, before=before, returned=0, added=0, after=before,
                     status="success", error="")
        try:
            if idx and delay:
                time.sleep(delay)
            records, urls, other, _ = fetch_series(
                dict(task, start_date=day, end_date=day))
            if other:
                raise ValueError("unexpected alternate series during repair")
            entry["returned"] = len(records)
            added = merge_rows(existing, records, task, day)
            entry.update(added=added, after=before+added)
            counts[k] += added
            added_total += added
        except (AcquisitionError, ValueError, KeyError, TypeError) as exc:
            entry.update(status="failed", error=str(exc))
            audit.append(entry)
            write_csv(out/"boundary_recovery_audit.csv", audit, AUDIT_COLS)
            result.update(status="failed_no_corrected_snapshot", n_completed=len(audit)-1,
                          error=str(exc))
            (out/"recovery_manifest.json").write_text(json.dumps(result, indent=2)+"\n",
                                                     encoding="utf-8")
            raise
        audit.append(entry)
    write_csv(out/"boundary_recovery_audit.csv", audit, AUDIT_COLS)
    combined = [existing[k] for k in sorted(existing)]
    write_csv(out/"observations.csv", combined, COLS)
    write_csv(out/"history_plan_used.csv", tasks, PLAN_COLS)
    requests = []
    for task in tasks:
        selected = [r for r in combined if (r["site_id"], r["series_id"]) ==
                    (task["site_id"], task["series_id"])]
        requests.append(dict(panel_id=task["panel_id"], site_id=task["site_id"],
                             series_id=task["series_id"], concept=task["concept"],
                             status="success", n_records=len(selected),
                             window_coverage=window_coverage(task, selected)))
    result.update(status="boundary_recovery_complete", n_completed=len(audit),
                  n_original_observations=source["n_observations"],
                  n_added_observations=added_total, n_observations=len(combined),
                  n_empty_boundary_responses=sum(r["returned"] == 0 for r in audit))
    report = dict(result, generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  plan_sha256=sha(out/"history_plan_used.csv"),
                  observations_sha256=sha(out/"observations.csv"),
                  n_failed_tasks=0, incomplete_panels=[],
                  n_panels=len({t["panel_id"] for t in tasks}),
                  by_concept=dict(Counter(r["concept"] for r in combined)),
                  requests=requests, observation_coverage_verified=False,
                  trained_models=0, continuous_interval_policy="boundary_recovery_v1")
    (out/"history_manifest.json").write_text(json.dumps(report, indent=2)+"\n",
                                             encoding="utf-8")
    (out/"recovery_manifest.json").write_text(json.dumps(result, indent=2)+"\n",
                                              encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--history", type=Path, required=True)
    p.add_argument("--identity", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-requests", type=int, default=80)
    p.add_argument("--delay", type=float, default=2)
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.history, a.out, a.identity, a.execute,
                         a.max_requests, a.delay), indent=2))


if __name__ == "__main__":
    main()
