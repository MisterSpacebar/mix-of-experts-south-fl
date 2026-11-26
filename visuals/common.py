"""Small shared I/O helpers for the visuals package.

Deliberately standalone from southfl.net so this package can be used to
post-process preview outputs without importing acquisition/network code.
"""
from __future__ import annotations

import csv
from pathlib import Path


def read_csv(path):
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ensure_clean_dir(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"output directory must be new/empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path
