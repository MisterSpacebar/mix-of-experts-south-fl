# South Florida Coastal Ecosystem — Mixture-of-Experts FCM

A source-first foundation for a hierarchical, regionalized fuzzy cognitive map (FCM) mixture of experts across Biscayne Bay, Florida Bay, the Florida Keys, and adjacent watersheds and offshore reefs.

## Current milestone: dataset discovery

**No agency observations have been ingested, no station coverage audit has been completed, and no FCM has been fitted.** The registry lists *candidate* data products and is not a statement that all variables are available for a given location or period.

- [Dataset inventory](catalog/datasets.json): 18 candidate dataset products across hydrology, water quality, oceanography, ecology and socioeconomic services.
- [Acquisition and QA plan](docs/DATASETS.md): which specific products to select, regional caveats, duplicate handling, observation schema and staged priorities.
- [Catalog validation](scripts/catalog.py): standard-library command-line validation of the structured source registry.
- [NOAA CO-OPS example](scripts/fetch_coops.py): opt-in live extraction of observed water levels to local untracked CSV files.

## Quick start

Requires Python 3.10+ and no third-party dependencies for this milestone.

```bash
python scripts/catalog.py
python -m unittest discover -s tests -v
python scripts/fetch_coops.py --station 8724580 --begin 20260101 --end 20260107
```

CO-OPS requests use GMT and metric units, save the requested datum, and retain the original request URL. Choose station IDs and dates with verified data coverage; API failures are reported rather than fabricated.

## Modeling architecture (planned)

1. Fit independently validated dataset-level experts after station and variable coverage audits.
2. Fuse compatible experts into hydrology/water-quality, oceanography, biological/ecological and socioeconomic subsystem representations.
3. Couple regions and disciplines through signed, lagged, hypothesis-driven interface concepts and time-availability-safe expert gating.
4. Validate model behavior with chronological and spatial holdouts, expert ablations, and non-FCM baselines.

Keep county-level fisheries landings, modeled Hazus consequences, sparse coral surveys and continuous water-level measurements on their appropriate clocks. EPA WQX and FDEP WIN can expose the same records: they must not be treated as independent observations.
