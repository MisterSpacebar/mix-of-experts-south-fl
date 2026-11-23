"""Validate and summarize the source registry (standard library only)."""
import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "datasets.json"
REQUIRED = {"id", "subsystem", "agency", "dataset", "url", "access",
            "granularity", "cadence_candidate", "geography",
            "candidate_variables", "priority", "caution"}
SUBSYSTEMS = {"hydrology", "water_quality", "oceanography", "ecology", "socioeconomic"}


def validate(path=CATALOG):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    datasets = obj["datasets"]
    ids = set()
    for i, record in enumerate(datasets):
        missing = REQUIRED - record.keys()
        if missing:
            raise ValueError(f"dataset {i}: missing {sorted(missing)}")
        if record["id"] in ids:
            raise ValueError(f"duplicate ID: {record['id']}")
        ids.add(record["id"])
        if record["subsystem"] not in SUBSYSTEMS:
            raise ValueError(f"unknown subsystem: {record['subsystem']}")
        if not record["url"].startswith("https://"):
            raise ValueError(f"expected HTTPS URL: {record['id']}")
        if not isinstance(record["candidate_variables"], list) or not record["candidate_variables"]:
            raise ValueError(f"missing candidate variables: {record['id']}")
        if record["priority"] not in {"P0", "P1", "P2"}:
            raise ValueError(f"invalid priority: {record['id']}")
    return datasets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print dataset summary as JSON")
    args = parser.parse_args()
    datasets = validate()
    counts = dict(sorted(Counter(x["subsystem"] for x in datasets).items()))
    if args.json:
        print(json.dumps({"dataset_count": len(datasets), "by_subsystem": counts}, indent=2))
    else:
        print(f"Validated {len(datasets)} candidate datasets")
        for group, count in counts.items():
            print(f"  {group}: {count}")


if __name__ == "__main__":
    main()
