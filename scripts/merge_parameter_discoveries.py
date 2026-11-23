"""Consolidate a repaired CO-OPS-only run with a previous partial inventory.

Strictly handles the Milestone 3 case: a full run with ONLY its CO-OPS
subtype failed, and a clean CO-OPS-only replacement using the SAME stations.
Other failed subtypes or incomplete CO-OPS site sets are not silently repaired.

python scripts/merge_parameter_discoveries.py \
    --base data/inventory/parameters_v1 \
    --supplement data/inventory/parameters_coops_v2 \
    --stations data/inventory/batch_v2/stations.csv \
    --out data/inventory/parameters_v2
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.discover_parameters import (SUMMARY_COLUMNS, CONFLICT_COLUMNS,
                                         concept_summary, unique_periods)
from southfl.audit import read_csv, validate_stations
from southfl.net import write_csv
from southfl.periods import PERIOD_COLUMNS

COOPS_KEY = ("coops", "domain", "waterlevel_station")


def _read_manifest(directory):
    return json.loads((Path(directory) / "parameter_manifest.json").read_text(encoding="utf-8"))


def _key(a):
    return (a["source"], a["region"], a["subtype"])


def merge(base, supplement, station_path, out):
    base, supplement, station_path, out = map(Path, (base, supplement, station_path, out))
    # Never overwrite either source data or earlier consolidated outputs.
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"destination is nonempty: {out}")
    if out.resolve() in (base.resolve(), supplement.resolve()):
        raise ValueError("output directory must differ from both inputs")
    original, replacement = _read_manifest(base), _read_manifest(supplement)
    if original.get("n_conflicting_metadata_records") != 0 or (
            replacement.get("n_conflicting_metadata_records") != 0):
        raise ValueError("cannot merge input metadata with unresolved conflicts")
    if original.get("n_failed_requests") != 1:
        raise ValueError("base must have exactly one failed CO-OPS subtype")
    attempts = original.get("attempts", [])
    failed = [a for a in attempts if a.get("status") != "success"]
    if len(failed) != 1 or _key(failed[0]) != COOPS_KEY:
        raise ValueError("base failure must be CO-OPS station metadata only")
    rep_attempts = replacement.get("attempts", [])
    if (replacement.get("sources") != ["coops"] or
            replacement.get("n_failed_requests") != 0 or
            len(rep_attempts) != 1 or _key(rep_attempts[0]) != COOPS_KEY or
            rep_attempts[0].get("status") != "success"):
        raise ValueError("supplement must be a fully successful CO-OPS-only run")
    stations = read_csv(station_path)
    validate_stations(stations)
    expected = {r["site_id"] for r in stations if r["dataset_id"] == "noaa_coops"}
    if not expected:
        raise ValueError("station inventory contains no CO-OPS stations")
    original_rows = read_csv(base / "parameter_periods.csv")
    new_rows = read_csv(supplement / "parameter_periods.csv")
    if any(r["dataset_id"] == "noaa_coops" for r in original_rows):
        raise ValueError("base already contains CO-OPS rows: manual review needed")
    if any(r["dataset_id"] != "noaa_coops" for r in new_rows):
        raise ValueError("supplement contains non-CO-OPS records")
    actual = {r["site_id"] for r in new_rows}
    if actual != expected or len(new_rows) != len(expected):
        raise ValueError(f"CO-OPS supplement incomplete: expected {len(expected)} "
                         f"sites, got {len(actual)} unique/{len(new_rows)} records")
    for r in new_rows:
        if r["evidence"] != "station_class_only" or r["begin_utc"] or r["end_utc"]:
            raise ValueError("CO-OPS replacement must remain metadata-only")
    all_rows, conflicts = unique_periods(original_rows + new_rows)
    if conflicts:
        raise ValueError("new metadata conflicts; refusing to write merged outputs")
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "parameter_periods.csv", all_rows, PERIOD_COLUMNS)
    write_csv(out / "concept_summary.csv", concept_summary(all_rows, stations), SUMMARY_COLUMNS)
    write_csv(out / "parameter_metadata_conflicts.csv", [], CONFLICT_COLUMNS)
    revised = [rep_attempts[0] if _key(a) == COOPS_KEY else a for a in attempts]
    manifest = dict(original)
    manifest.update(
        retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
        merged_from={"base": str(base), "supplement": str(supplement),
                     "station_inventory": str(station_path)},
        attempts=revised, n_failed_requests=0, n_failed_station_requests=0,
        n_raw_metadata_rows=original.get("n_raw_metadata_rows", len(original_rows))
                            + replacement.get("n_raw_metadata_rows", len(new_rows)),
        n_parameter_periods=len(all_rows), n_conflicting_metadata_records=0,
        observation_coverage_verified=False,
        observations_downloaded=False,
        note="Source-specific metadata consolidation; NO measurement completeness "
             "or training-readiness claim. NOAA station class only.",
    )
    (out / "parameter_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--supplement", type=Path, required=True)
    p.add_argument("--stations", type=Path, default=Path("data/inventory/batch_v2/stations.csv"))
    p.add_argument("--out", type=Path, default=Path("data/inventory/parameters_v2"))
    a = p.parse_args()
    report = merge(a.base, a.supplement, a.stations, a.out)
    print(f"Consolidated {report['n_parameter_periods']} metadata records -> {a.out}")
    print("All queried subtypes successful; observation coverage is NOT verified.")


if __name__ == "__main__":
    main()
