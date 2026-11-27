"""M10.1: ranked, synchronized, metadata-only acquisition batches.

Never download or train here. Use the existing live identity preflight.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.history_selection import PLAN_COLS
from southfl.historical import windows

ROOT = Path("data/m9/recruitment_big_cypress_v1")
BASELINE = Path("data/m9/cross_axis_atlas_v1/manifest.json")
REFERENCE = Path("data/m7/identity_probe_01/history_plan.csv")
STAGE = {"gage_height", "stream_stage_elevation", "groundwater_elevation"}


def read(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def group(rows):
    groups = defaultdict(list)
    panel_sites = {}
    for r in rows:
        if not set(PLAN_COLS).issubset(r):
            raise ValueError("missing history plan fields")
        sid, pid = r["site_id"], r["panel_id"]
        if not re.fullmatch(r"USGS-[0-9]{8,15}", sid) or not re.fullmatch(r"[A-Za-z0-9_]+", pid):
            raise ValueError("noncanonical station or unsafe panel ID")
        if panel_sites.setdefault(pid, sid) != sid:
            raise ValueError("panel spans sites")
        if r["dataset_id"] != "usgs_water" or r["mode"] != "continuous":
            raise ValueError("requires continuous USGS plans")
        if not r["series_id"] or not re.fullmatch(r"[0-9]{5}", r["parameter_code"]):
            raise ValueError("missing source identity")
        groups[sid].append(r)
    for tasks in groups.values():
        if (len({r["panel_id"] for r in tasks}) != 1 or
                len({r["concept"] for r in tasks}) != len(tasks) or
                len({r["series_id"] for r in tasks}) != len(tasks)):
            raise ValueError("duplicate concept, series, or panel per site")
    return groups


def run(plan, shortlist, reference, baseline, out, start="2026-05-29",
        end="2026-11-21", max_new=5, max_km=15, max_requests=80):
    plan, shortlist, reference, baseline, out = map(
        Path, (plan, shortlist, reference, baseline, out))
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty output required")
    left, right = date.fromisoformat(start), date.fromisoformat(end)
    if not 60 <= (right-left).days+1 <= 366:
        raise ValueError("window must be 60..366 days")
    if not 1 <= max_new <= 8 or not 0 < max_km <= 250 or not 1 <= max_requests <= 200:
        raise ValueError("invalid acquisition limits")
    candidates, refs = group(read(plan)), group(read(reference))
    if candidates.keys() & refs.keys() or len(refs) != 1:
        raise ValueError("reference must be one distinct existing station")
    seen, ranks, queue, excluded = set(), set(), [], []
    for r in sorted(read(shortlist), key=lambda r: int(r["rank"])):
        sid, rank = r["site_id"], int(r["rank"])
        if sid in seen or rank in ranks or rank < 1:
            raise ValueError("duplicate or invalid shortlist rank/site")
        seen.add(sid)
        ranks.add(rank)
        if sid not in candidates:
            continue
        if r["selected_into_history_plan"].lower() != "true":
            raise ValueError("shortlist/history plan selection mismatch")
        if r["target_discovery_region"] != candidates[sid][0]["region"]:
            raise ValueError("shortlist/history plan region mismatch")
        distance = float(r["nearest_distance_km"])
        if not 0 <= distance < float("inf"):
            raise ValueError("invalid distance")
        if distance > max_km or len(queue) >= max_new:
            excluded.append({"site_id": sid, "reason": "distance_or_rank_cap"})
            continue
        queue.append((sid, str(rank), "new_station", candidates[sid]))
    if candidates.keys() - seen or not queue:
        raise ValueError("missing shortlist evidence or no eligible stations")
    # First acquire Faka-Union (rank 1 on the real snapshot), then extend
    # the shorter historical reference, then acquire the remaining ranks.
    sid, tasks = next(iter(refs.items()))
    queue.insert(1, (sid, "", "reference_extension", tasks))
    prepared, index = [], []
    for n, (sid, rank, role, tasks) in enumerate(queue, 1):
        batch = f"batch_{n:02d}"
        rows = []
        for r in tasks:
            if date.fromisoformat(r["metadata_start"][:10]) > left or date.fromisoformat(r["metadata_end"][:10]) < right:
                raise ValueError(f"{sid}: requested window outside recorded metadata")
            rows.append(dict(r, start_date=start, end_date=end,
                             selection_status="metadata_candidate_validate_real_observations"))
        calls = len(rows)*len(list(windows(start, end)))
        if calls > max_requests:
            raise ValueError(f"{sid}: exceeds per-station history request cap")
        prepared.append((batch, rows))
        index.append(dict(batch_id=batch, site_id=sid, shortlist_rank=rank,
                          role=role, n_series=len(rows), n_history_windows=calls,
                          unverified_stage_concepts=";".join(
                              r["concept"] for r in rows
                              if r["concept"] in STAGE and not r["vertical_datum"]),
                          status="awaiting_fresh_identity_preflight"))
    baseline_data = json.loads(baseline.read_text(encoding="utf-8"))
    if baseline_data["n_fitted_region_fcms"] != 0:
        raise ValueError("expected untrained M9 baseline")
    # All validations precede writing; no old artifacts are modified.
    out.mkdir(parents=True, exist_ok=True)
    for batch, rows in prepared:
        write(out/batch/"history_plan.csv", rows, PLAN_COLS)
    write(out/"batch_index.csv", index, list(index[0]))
    write(out/"excluded_sites.csv", excluded, ["site_id", "reason"])
    manifest = dict(
        inputs={str(p): sha(p) for p in (plan, shortlist, reference, baseline)},
        start=start, end=end, n_new_station_candidates=len(queue)-1,
        n_reference_extensions=1, n_batches=len(queue),
        n_candidate_series=sum(r["n_series"] for r in index),
        n_history_windows=sum(r["n_history_windows"] for r in index),
        batch_plan_sha256={b: sha(out/b/"history_plan.csv") for b, _ in prepared},
        baseline_station_fcms=baseline_data["n_fitted_full_station_fcms"],
        identity_verified=False, observations_downloaded=False,
        connectivity_verified=False, regional_fcms_trained=0)
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n",
                                     encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, default=ROOT/"history_plan.csv")
    p.add_argument("--shortlist", type=Path, default=ROOT/"metadata_recruitment_shortlist.csv")
    p.add_argument("--reference", type=Path, default=REFERENCE)
    p.add_argument("--baseline", type=Path, default=BASELINE)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", default="2026-05-29")
    p.add_argument("--end", default="2026-11-21")
    p.add_argument("--max-new", type=int, default=5)
    p.add_argument("--max-km", type=float, default=15)
    p.add_argument("--max-requests", type=int, default=80)
    a = p.parse_args()
    result = run(a.plan, a.shortlist, a.reference, a.baseline, a.out,
                 a.start, a.end, a.max_new, a.max_km, a.max_requests)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
