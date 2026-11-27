"""M10.2: corrected observed station cohort and chronological spatial split audit.

A screening rectangle and compatible reported sensor position are not
hydrological connectivity. No pooled models are trained by this script.
"""
import argparse
import hashlib
import itertools
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.m9_regions import parse_semicolon_map, longest_streak, haversine_km
from southfl.regions import REGIONS, regions_for
from southfl.temporal_integrity import verify_historical_hash
from southfl.fcm_model import build_pairs

ROOT = Path("data/m10")
DEFAULT_SNAPSHOTS = [
    (ROOT/"daily_01_recovered", ROOT/"history_01_recovered", ROOT/"identity_recovery_01"),
    (ROOT/"daily_02", ROOT/"history_02", ROOT/"identity_02"),
    (ROOT/"daily_m8_recovered", ROOT/"history_m8_recovered", ROOT/"identity_m8_recovery"),
]
ASSIGNMENTS = Path("data/m9/regional_readiness_v1_with_coords/station_assignments.csv")
SHORTLIST = Path("data/m9/recruitment_big_cypress_v1/metadata_recruitment_shortlist.csv")
CONCEPTS = ["salinity", "water_temperature"]
UNITS = {"salinity": "ppt", "water_temperature": "degC"}
CODES = {"salinity": "00480", "water_temperature": "00010"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def json_at(p):
    return json.loads(p.read_text(encoding="utf-8"))


def coordinates(paths):
    points = {}
    for path in paths:
        for row in read_csv(path):
            site = row["site_id"]
            if not re.fullmatch(r"USGS-[0-9]{8,15}", site):
                raise ValueError("noncanonical coordinate station")
            if not row.get("latitude") or not row.get("longitude"):
                continue
            point = float(row["latitude"]), float(row["longitude"])
            if not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
                raise ValueError("invalid coordinates")
            if site in points and points[site][0] != point:
                raise ValueError("conflicting source coordinates")
            points[site] = (point, str(path), row.get("site_name", ""))
    return points


def dates_summary(days):
    days = set(days)
    return (len(days), sum(d-timedelta(days=1) in days for d in days),
            longest_streak(days))


def load_snapshot(daily, history, identity, verify_raw=False):
    daily, history, identity = map(Path, (daily, history, identity))
    pm, hm, im = [json_at(p) for p in (daily/"panels_manifest.json",
                                      history/"history_manifest.json",
                                      identity/"identity_manifest.json")]
    if (hm.get("continuous_interval_policy") not in
            ("explicit_utc_half_open_v1", "boundary_recovery_v1") or
            hm.get("n_failed_tasks") != 0 or hm.get("incomplete_panels") or
            pm.get("incomplete_panels") or
            pm["observations_sha256"] != hm["observations_sha256"]):
        raise ValueError("requires complete corrected history and matching panel lineage")
    if (im.get("source_identity_verified") is not True or
            im.get("n_failed_or_unattempted_tasks") != 0):
        raise ValueError("requires verified complete identity preflight")
    if hm["continuous_interval_policy"] == "boundary_recovery_v1":
        verify_historical_hash(identity/"identity_manifest.json",
                               hm["fresh_identity_manifest_sha256"])
    lineage = {
        "history_manifest": sha(history/"history_manifest.json"),
        "panels_manifest": sha(daily/"panels_manifest.json"),
        "identity_manifest": sha(identity/"identity_manifest.json"),
        "identity_audit": sha(identity/"series_identity_audit.csv"),
        "panel_readiness": sha(daily/"panel_readiness.csv"),
        "raw_sha256_recorded": hm["observations_sha256"],
        "raw_bytes_verified": False,
    }
    verify_historical_hash(history/"history_plan_used.csv", hm["plan_sha256"])
    verify_historical_hash(identity/"history_plan.csv", im["verified_plan_sha256"])
    plan = read_csv(history/"history_plan_used.csv")
    if plan != read_csv(identity/"history_plan.csv") or len(plan) != hm["n_tasks"]:
        raise ValueError("history and certified identity plan differ")
    if verify_raw:
        lineage["raw_verification"] = verify_historical_hash(
            history/"observations.csv", hm["observations_sha256"])
        lineage["raw_bytes_verified"] = True
    tasks = {}
    for t in plan:
        k = t["site_id"], t["concept"]
        if k in tasks or t["dataset_id"] != "usgs_water" or t["mode"] != "continuous":
            raise ValueError("duplicate or unsupported source task")
        tasks[k] = t
    audits = {}
    for a in read_csv(identity/"series_identity_audit.csv"):
        k = a["site_id"], a["concept"]
        t = tasks.get(k)
        if (k in audits or t is None or a["status"] != "verified" or
                a["resolved_series_id"] != t["series_id"] or
                a["panel_id"] != t["panel_id"] or
                a["parameter_code"] != t["parameter_code"] or
                a["metadata_unit"] != t["unit"] or
                a["metadata_vertical_datum"] != t["vertical_datum"]):
            raise ValueError("identity audit contradicts history task")
        audits[k] = a
    if audits.keys() != tasks.keys():
        raise ValueError("identity audit does not cover all tasks")
    coverage = {}
    for r in hm["requests"]:
        k = r["site_id"], r["concept"]
        t = tasks.get(k)
        if (k in coverage or t is None or r["status"] != "success" or
                r["series_id"] != t["series_id"] or r["panel_id"] != t["panel_id"]):
            raise ValueError("unexpected acquisition coverage identity")
        days = {}
        for w in r["window_coverage"]:
            for d in w["days"]:
                day = d["date"]
                if day in days or not t["start_date"] <= day <= t["end_date"]:
                    raise ValueError("invalid or duplicate coverage day")
                days[day] = (int(d["n_distinct_instants"]), float(d["span_hours"]))
        expected = (date.fromisoformat(t["end_date"])-date.fromisoformat(t["start_date"])).days+1
        if len(days) != expected or sum(n for n, _ in days.values()) != r["n_records"]:
            raise ValueError("coverage totals differ from acquisition records")
        coverage[k] = days
    if coverage.keys() != tasks.keys():
        raise ValueError("missing acquisition coverage")
    if sum(sum(n for n, _ in days.values()) for days in coverage.values()) != hm["n_observations"]:
        raise ValueError("history observation count mismatch")
    result = []
    seen_sites = set()
    for p in read_csv(daily/"panel_readiness.csv"):
        sid, pid = p["site_id"], p["panel_id"]
        if sid in seen_sites or not re.fullmatch(r"[A-Za-z0-9_]+", pid):
            raise ValueError("duplicate site or unsafe panel ID")
        seen_sites.add(sid)
        cs = p["concepts"].split(";")
        if len(cs) != len(set(cs)) or set(cs) != {c for s,c in tasks if s == sid}:
            raise ValueError("panel concept set does not match source plan")
        series = parse_semicolon_map(p["source_series_ids"])
        units = parse_semicolon_map(p["concept_units"])
        datums = parse_semicolon_map(p["concept_datums"])
        for c in cs:
            t = tasks[sid,c]
            if (series[c], units[c], datums[c], pid, p["region"]) != (
                    t["series_id"], t["unit"], t["vertical_datum"], t["panel_id"], t["region"]):
                raise ValueError("panel source lineage mismatch")
        path = daily/(pid+".csv")
        rows = read_csv(path)
        dates = set()
        for row in rows:
            d = date.fromisoformat(row["date"])
            if row["site_id"] != sid or row["panel_id"] != pid or d in dates:
                raise ValueError("daily identity/date mismatch")
            dates.add(d)
            for c in cs:
                from math import isfinite
                n, span = coverage[sid,c][row["date"]]
                samples = int(row["n_"+c])
                if (not isfinite(float(row[c])) or
                        not pm["min_samples_per_source_day"] <= samples <= n or
                        span < pm["min_utc_day_span_hours"]):
                    raise ValueError("daily row contradicts raw coverage or QA")
        n, pairs, longest = dates_summary(dates)
        if (n, pairs) != (int(p["n_complete_days"]), int(p["n_consecutive_daily_pairs"])):
            raise ValueError("daily dates disagree with readiness")
        compatible = all(c in cs and units[c] == UNITS[c] and
                         audits[sid,c]["parameter_code"] == CODES[c] and
                         audits[sid,c]["metadata_statistic_id"] == "00011" and
                         audits[sid,c]["metadata_sublocation"].strip().casefold() == "near bottom"
                         for c in CONCEPTS)
        result.append(dict(site_id=sid, panel_id=pid, primary_region=p["region"],
                           daily_path=str(path), daily_sha256=sha(path),
                           complete_days=n, consecutive_pairs=pairs,
                           longest_days=longest, water_quality_compatible=compatible,
                           sensor_positions=";".join(c+"="+audits[sid,c]["metadata_sublocation"]
                                                     for c in cs),
                           concepts=";".join(cs), stage_datum=datums.get("gage_height",""),
                           _dates=dates, _rows=rows))
    if seen_sites != {s for s,c in tasks} or len(result) != pm["n_panels"]:
        raise ValueError("panel set differs from history")
    return result, lineage


def run(snapshots, out, assignments=ASSIGNMENTS, shortlist=SHORTLIST,
        region="big_cypress", start="2026-05-29", end="2026-11-21",
        min_sites=3, min_pairs=79, verify_raw=False):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty output required")
    if region not in REGIONS or min_sites < 3 or min_pairs < 79:
        raise ValueError("invalid cohort screening parameters")
    left, right = date.fromisoformat(start), date.fromisoformat(end)
    if (right-left).days < 79:
        raise ValueError("window too short")
    # Calendar cutoffs fixed before looking at outcomes or overlap.
    span = (right-left).days
    train_end = left+timedelta(days=int(span*.6))
    val_end = left+timedelta(days=int(span*.8))
    def period(d):
        return "train" if d <= train_end else "validation" if d <= val_end else "test"
    coords = coordinates([assignments, shortlist])
    stations, lineage = {}, {}
    for daily, history, identity in snapshots:
        rows, audit = load_snapshot(daily, history, identity, verify_raw)
        lineage[str(daily)] = audit
        for r in rows:
            sid = r["site_id"]
            if sid in stations:
                raise ValueError("duplicate independent station across snapshots")
            r["_dates"] = {d for d in r["_dates"] if left <= d <= right}
            point = coords.get(sid)
            r["coordinate_source"] = point[1] if point else ""
            r["site_name"] = point[2] if point else ""
            r["latitude"], r["longitude"] = point[0] if point else ("","")
            inside = bool(point and region in regions_for(*point[0]))
            r["inside_screening_rectangle"] = inside
            r["cohort_status"] = ("eligible_metadata_screen" if inside and r["water_quality_compatible"]
                                  else "outside_or_unlocated" if not inside
                                  else "sensor_or_concept_incompatible")
            stations[sid] = r
    eligible = sorted(s for s,r in stations.items() if r["cohort_status"] == "eligible_metadata_screen")
    for sid,r in stations.items():
        r["common_window_days"], r["common_window_pairs"], r["common_window_longest_days"] = dates_summary(r["_dates"])
    pairs = []
    for a,b in itertools.combinations(sorted(stations),2):
        x,y = stations[a],stations[b]
        n,k,longest = dates_summary(x["_dates"] & y["_dates"])
        dist = haversine_km((x["latitude"],x["longitude"]),(y["latitude"],y["longitude"])) if x["coordinate_source"] and y["coordinate_source"] else ""
        pairs.append(dict(site_a=a,site_b=b,shared_days=n,shared_pairs=k,
                          longest_shared_days=longest,distance_km=dist,
                          both_in_cohort=a in eligible and b in eligible,
                          connectivity_verified=False))
    shared = set.intersection(*(stations[s]["_dates"] for s in eligible)) if eligible else set()
    n,k,longest = dates_summary(shared)
    # Pooled station-local transitions do not require all stations observed
    # on the same date. Distinguish these counts from aligned spatial input.
    counts = {}
    for sid in eligible:
        rows = [r for r in stations[sid]["_rows"] if date.fromisoformat(r["date"]) in stations[sid]["_dates"]]
        by = defaultdict(int)
        for day,_,_ in build_pairs(rows, CONCEPTS):
            by[period(date.fromisoformat(day))] += 1
        counts[sid] = dict(train=by["train"],validation=by["validation"],test=by["test"])
    folds = []
    for held in eligible:
        donors = [s for s in eligible if s != held]
        viable = (len(donors)>=min_sites-1 and
                  all(counts[s]["train"]>=35 and counts[s]["validation"]>=15 for s in donors)
                  and sum(counts[held].values())>=min_pairs and counts[held]["test"]>=15)
        folds.append(dict(heldout_site=held,donor_sites=";".join(donors),
                          donor_train_pairs=sum(counts[s]["train"] for s in donors),
                          donor_validation_pairs=sum(counts[s]["validation"] for s in donors),
                          target_test_pairs=counts[held]["test"],
                          temporal_screen_pass=viable,
                          status="candidate_not_fitted" if viable else "insufficient_fold_coverage"))
    ready = (len(eligible)>=min_sites and k>=min_pairs and bool(folds) and
             all(f["temporal_screen_pass"] for f in folds))
    out.mkdir(parents=True,exist_ok=True)
    station_rows = [dict((k,v) for k,v in r.items() if not k.startswith("_"))
                    for r in stations.values()]
    write_csv(out/"station_cohort.csv",station_rows,list(station_rows[0]))
    write_csv(out/"pair_alignment.csv",pairs,["site_a","site_b","shared_days","shared_pairs","longest_shared_days","distance_km","both_in_cohort","connectivity_verified"])
    write_csv(out/"spatial_fold_plan.csv",folds,["heldout_site","donor_sites","donor_train_pairs","donor_validation_pairs","target_test_pairs","temporal_screen_pass","status"])
    write_csv(out/"site_split_counts.csv",[dict(site_id=s,**v) for s,v in counts.items()],["site_id","train","validation","test"])
    report = dict(region_screen=region, start=start,end=end,
                  train_target_date_end=train_end.isoformat(),validation_target_date_end=val_end.isoformat(),
                  n_observed_sites=len(stations),eligible_sites=eligible,
                  common_days=n,common_transitions=k,longest_common_stretch=longest,
                  temporal_metadata_screen_pass=ready,
                  n_spatial_folds=len(folds),concepts=CONCEPTS,
                  hydrological_connectivity_verified=False,exact_sensor_depth_verified=False,
                  raw_bytes_verified=verify_raw,regional_fcms_trained=0,
                  snapshots=lineage,coordinate_sources={str(p):sha(Path(p)) for p in (assignments,shortlist)},
                  note="Near Bottom matching and discovery rectangle membership are screening evidence only; complete full-panel days are used conservatively.")
    (out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    (out/"INDEX.md").write_text(
        "# M10 — corrected regional cohort readiness\n\n"
        f"{len(stations)} observed sites; {len(eligible)} compatible geographic screening candidates.\n\n"
        f"Shared complete days: {n}; aligned transitions: {k}; longest stretch: {longest}.\n\n"
        f"Temporal/metadata screen: {'PASS' if ready else 'BLOCKED'}. No regional FCM fitted.\n\n"
        "- [Station evidence](station_cohort.csv)\n- [Pairwise overlap](pair_alignment.csv)\n"
        "- [Chronological split counts](site_split_counts.csv)\n- [Held-out station fold plan](spatial_fold_plan.csv)\n"
        "- [Lineage and limitations](manifest.json)\n\n"
        "Target test stations must not enter donor training, scaling or validation. "
        "The cutoffs use target UTC dates; no gaps are interpolated. "
        "Matching reported Near Bottom categories does not verify exact depth or transport.\n",
        encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot",action="append",nargs=3,metavar=("DAILY","HISTORY","IDENTITY"),type=Path,
                   help="Additional corrected station snapshot; baseline three roots always included")
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--assignments",type=Path,default=ASSIGNMENTS)
    p.add_argument("--shortlist",type=Path,default=SHORTLIST)
    p.add_argument("--region",default="big_cypress")
    p.add_argument("--start",default="2026-05-29")
    p.add_argument("--end",default="2026-11-21")
    p.add_argument("--verify-raw",action="store_true",help="Also verify each original raw CSV SHA-256")
    a=p.parse_args()
    print(json.dumps(run(DEFAULT_SNAPSHOTS+(a.snapshot or []),a.out,a.assignments,
                         a.shortlist,a.region,a.start,a.end,verify_raw=a.verify_raw),indent=2))


if __name__=="__main__":
    main()
