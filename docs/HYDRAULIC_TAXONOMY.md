# Hydraulic concept taxonomy and datum preservation

This update is a **metadata classification** step, not an FCM fitting step.
It follows the verified Milestone 6 cross-snapshot merge with 131,797 records,
354 audited USGS timestamp advances and zero genuine metadata conflicts.

## Source-code-specific physical concepts

USGS codes are authoritative for the following assignments:

| USGS code | Measurement | Canonical concept | Vertical datum |
|---|---|---|---|
| `00065` | Gage height relative to a local station reference | `gage_height` | Not inferred |
| `62610` | Groundwater elevation above NGVD29 | `groundwater_elevation` | `NGVD29` |
| `62611` | Groundwater elevation above NAVD88 | `groundwater_elevation` | `NAVD88` |
| `63158` | Stream stage elevation above NGVD29 | `stream_stage_elevation` | `NGVD29` |
| `63160` | Stream stage elevation above NAVD88 | `stream_stage_elevation` | `NAVD88` |
| `72255` | Mean water velocity | `water_velocity` | Not applicable |
| `72019` | Groundwater depth below local land surface | `groundwater_depth_below_land_surface` | Not a geodetic datum |

NOAA CO-OPS `water_level` remains a separate observation concept; its
observed-level product has its own explicitly requested vertical datum (for
example, MLLW). **No datum is guessed for USGS gage height (00065)**. The
site-relative gage origin must be verified at the source.

Confirmed from the uploaded overlap audit: 354 live-series end-date
advances include 115 `62610`, 44 `62611`, 16 `63160`, 1 `63158`, and
10 `72255` series previously classed `unmapped`. The remaining 168
advances were already under other concepts. These are source *series
records*, not independent monitoring stations or training examples.

The vertical reference is stored in `parameter_periods.csv` as a separate
`vertical_datum` field, **not** appended to the concept name. Updated
`concept_summary.csv` groups candidate sites separately by concept **and**
vertical datum. The source's code, raw name, unit, sublocation and
source URL all remain available.

## Important scientific restrictions

- Do not combine NGVD29 and NAVD88 elevations without location-specific,
  verified transformations; these datums cannot be treated as a single
  global offset.
- Do not combine `groundwater_elevation`, `stream_stage_elevation`,
  `gage_height`, `groundwater_depth_below_land_surface`,
  `water_velocity`, and coastal `water_level` simply because they
  respond to hydrology.
- Preserve station sublocation and statistic IDs. Canal levels measured
  upstream and downstream of a structure may reflect different head
  conditions and directional gradients.
- Stage is a relative elevation; mean velocity is in length/time and
  cannot substitute for discharge without channel geometry/area.
- Source units (feet/meters; ft/s; cubic feet/s) are **not** converted
  in this update. Keep raw units and QA status throughout.
- No high-frequency imputation, vertical transformation, or observed
  completeness is implied by this taxonomy.

## Apply the corrected mapping to the existing verified snapshot

This step uses local CSV files only; no NOAA/USGS/EPA requests. On the branch:

```powershell
git fetch origin
git switch feat/usgs-hydraulic-datum-concepts
python -m unittest discover -s tests -v

python scripts/harmonize_parameter_inventory.py --input data/inventory/parameters_combined_v4 --stations data/inventory/combined_v3/stations.csv --out data/inventory/parameters_harmonized_v1
```

This requires **Milestone 6 PR #6** to be merged first if working from
`main`. This new PR is *stacked* on the Milestone 6 branch while that PR is
open. Once PR #6 is merged, retarget this PR to `main` before merging.

Outputs (all remain ignored under `data/`):

- `parameter_periods.csv`: 131,797 expected, with concept mapping and
  vertical_datum populated from verified USGS codes.
- `concept_summary.csv`: recomputed, with datum-specific groups.
- `parameter_taxonomy_changes.csv`: records counts and distinct stations
  for each source-code concept/datum adjustment.
- `parameter_manifest.json`: input/output SHA-256 hashes, lineage and
  counts of changed series; still sets `observation_coverage_verified=false`.
- `time_series_end_advances.csv` and `parameter_metadata_conflicts.csv`
  copied from the complete source snapshot, unchanged.

The input `parameters_combined_v4` and previously generated
`parameters_combined_v3` remain untouched. The output refuses to
overwrite an existing nonempty directory.

**Do not assume the number of changed rows in the full inventory from the
354 overlap cases**: those cases are only the live overlapping series; the
full inventory includes many other groundwater and water-level records.

## Subsequent modeling QA

1. Audit monitoring-location vertical references and installation histories.
2. Build per-series observed sample completeness, depth/method/QA review,
   and active deployment windows.
3. Require matching geodetic datum and unit conversion **before**
   comparing groundwater elevations or stream surface elevations across sites.
4. Identify surface-water and groundwater linkage by physically justified
   network structure, not just geographic co-location.
5. Calibrate FCMs using chronologically held-out real observations, and
   keep upstream/downstream measurements as separate state features.

Official USGS references:
- [Parameter codes and metadata](https://api.waterdata.usgs.gov/ogcapi/v1/collections/parameter-codes/items)
- [Groundwater-level parameter codes](https://waterservices.usgs.gov/docs/groundwater-levels/groundwater-levels-details/)
- [Continuous/daily stream-gage reference](https://waterservices.usgs.gov/docs/dv-service/daily-values-service-details/)
