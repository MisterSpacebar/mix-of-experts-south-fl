"""Audit pilot or historical observations without fitting a model.

Outputs immutable series_readiness.csv and same_site_concept_pairs.csv, plus
a manifest recording the input hash. No interpolation or false uptime rates.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.readiness import SERIES_COLS,PAIR_COLS,audit


def run(source,out):
    source,out=Path(source),Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory is not empty")
    rows=read_csv(source)
    series,pairs=audit(rows)
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"series_readiness.csv",series,SERIES_COLS)
    write_csv(out/"same_site_concept_pairs.csv",pairs,PAIR_COLS)
    report={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "input":str(source),"input_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "n_observation_rows":len(rows),"n_source_series_groups":len(series),
        "n_same_site_pairs":len(pairs),
        "n_conflicting_observation_times":sum(int(x["n_conflicting_times"]) for x in series),
        "n_numeric_records":sum(int(x["n_numeric"]) for x in series),
        "basis": "observed records/dates only; no inferred instrument uptime",
        "trainable":False,
    }
    (out/"readiness_manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--observations",type=Path,
                   default=Path("data/pilot/runs/first/observations.csv"))
    p.add_argument("--out",type=Path,default=Path("data/m7/pilot_readiness_v1"))
    a=p.parse_args()
    x=run(a.observations,a.out)
    print(f"{x['n_source_series_groups']} source-series groups, "
          f"{x['n_same_site_pairs']} same-site pairs, "
          f"{x['n_conflicting_observation_times']} timestamp conflicts")
    if x["n_conflicting_observation_times"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
