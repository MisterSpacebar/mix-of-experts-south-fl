# Milestone 9.2 — connect environmental categories and geography without inventing a regional FCM

## Why the previous views look disconnected

The project actually contains three different dimensions of evidence:

1. **Within-station multivariate FCM edges.** Every fitted four-variable
   station model contains directed one-day-ahead predictive coefficients
   from each measured concept to every measured concept. For example,
   discharge(t) → salinity(t+1) crosses the hydrology/water-quality
   taxonomy boundary. The older category-only and subcategory-only SVG
   projections omit such cross-boundary arrows by construction; the
   *full station model* and its separate cross-category projection retain
   them.
2. **Geographic screening and measured overlaps.** Each observed
   station is source-located, but the M9.1 pair graph only draws one
   dashed East River–Pumpkin River candidate link. It means **common
   discovery envelope / proximity**, not estuary flow, causal influence
   or a learned interstation FCM weight.
3. **Actual cross-site observations.** The two source-located west-coast
   stations share 89 complete observed UTC days and 70 truly aligned
   one-day transitions. Simultaneous changes across sites can be
   described exploratorily without pretending to fit a regional FCM.
   A common tide, rainfall event or another unmodeled forcing can
   produce these correlations at multiple stations.

A real geographical FCM, regional subcategory expert or overall
mixture-of-experts gate still has **NOT BEEN TRAINED**. No disconnected
rectangle should be drawn as a fitted edge merely because it appears
in a hierarchy diagram.

## New unified evidence atlas

The M9.2 atlas **joins these three sources as distinct evidence
layers** in one set of browsable reports and figures.

The global SVG puts each station's actual concept-level FCM into a
source-labeled card, with environmental categories grouped by color.
**Solid, signed, directed arrows** are actual independently fitted
lag-one source coefficients. Display cutoff `--min-edge 0.08`
only hides SVG arrows; it does not alter or discard the original
weights. Full-precision source models and original per-station SVGs
are linked.

**Dashed, undirected gray links between station cards** are strictly
geographic candidate screening. They have no FCM coefficients or
assumed water-flow directions. Cards are organized for readability,
**not positioned as a spatial map**. Their location names and
source-selected discovery regions are labeled.

Separate image/chart outputs show:
- How many observed site FCMs with hydrology/water-quality/etc. exist
  within each of the **14 overlapping discovery rectangles** (not a
  count of regional experts).
- Paired comparisons of the **two separately fitted source-station
  edge matrices**, without averaging coefficients into a false
  region-level matrix.
- An observational **concurrent daily-change correlation matrix**
  for the sole geographic candidate pair: actual day-to-day
  differences measured at two stations on the same adjacent UTC days.

This last view includes the three cross-site datum-eligible concepts
(discharge, salinity, water temperature). Both stations must have
measurements on day t-1 AND day t; there is no interpolation. It
tests all nine combinations of three concepts at Site A against
three concepts at Site B, and writes the actual Pearson r and
aligned count. Gage height is **excluded** while its common vertical
reference is unverified. No significance tests, transport arrows,
out-of-sample claims or region-model weights are inferred from r.

## Run from the committed three-site snapshot (no network requests)

```powershell
git fetch origin
git switch feat/m9-cross-axis-evidence-atlas
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v

python scripts/build_m9_cross_axis_atlas.py --models data/m8/layers_replication_v1 --panels data/m7/daily_panels_verified_01 --panels data/m8/replication_daily_01 --assignments data/m9/regional_readiness_v1_with_coords/station_assignments.csv --screen data/m9/spatial_candidate_screen_v1 --out data/m9/cross_axis_atlas_v1 --min-edge 0.08 --min-aligned 20
```

Open `data/m9/cross_axis_atlas_v1/INDEX.md`.

The CLI requires a new/empty output directory, verifies the original
daily panel hash and station/model identities, and recomputes each
saved M9.1 pair's date-overlap counts and geographic screen classification.
It also verifies each rounded full-station `edge_weights.csv` entry
against the **same trained FCM's original matrix**; tampered, missing or
duplicated directed edges fail closed.

Expected counts based on the frozen 3-station source:
- 3 separately trained full station FCMs
- 48 original directional fitted coefficients across all three stations
  (4×4 each), including both self-memory and cross-concept links
- 14 visible cross-category directed links at the 0.08 SVG display cutoff:
  5 at East River (all negative), 4 at Pumpkin River (1 positive,
  3 negative), and 5 at Black Creek (4 positive, 1 negative). These
  are individually fitted predictive coefficients; the differing
  signs illustrate why they cannot be pooled naively
- 3 original unique source station pairs, 1 geographic-screen candidate
- 9 exploratory matched daily-change concept combinations for the
  geographically screened East River / Pumpkin River pair, each using
  exactly 70 paired observed one-day transitions
- **0 trained regional FCMs, regional expert gates or cross-station
  directed FCM edges**

A source-data spot-check of these 70 aligned *concurrent* changes finds
same-variable Pearson r ≈ **+0.679** for discharge, **+0.537** for
salinity, and **+0.875** for water temperature between East River and
Pumpkin River. These are descriptive co-fluctuations (especially
plausible under common weather/tidal forcing), **not evidence of a
directed connection or transferable prediction**. Different-variable
associations and the exact underlying counts are exported in the CSV.

## Output organization

```text
data/m9/cross_axis_atlas_v1/
  INDEX.md
  manifest.json
  trained_station_edges_by_subsystem.csv         # all 48 original source trained coefficients
  within_station_category_bridges.csv           # per-station category direction summaries
  cross_station_fcm_edge_contrasts.csv           # same source/target coefficient, different site
  screened_cross_site_daily_change_associations.csv
  region_category_coverage.csv
  visuals/
    geography_category_evidence_atlas.svg       # THE integrated overview
    region_category_coverage.png
  pairs/
    USGS-255327081275900__USGS-255534081324000/
      FINDINGS.md
      edge_weight_contrast.csv
      observed_change_covariation.csv
      visuals/
        station_fcm_contrast.png
        aligned_change_correlations.png
    ...                                          # all three independent pairs
  regions/
    big_cypress/FINDINGS.md                     # links both trained station diagrams
    southwest_everglades_coast/FINDINGS.md
    central_south_biscayne/FINDINGS.md
    ...                                          # 14 screening regions
  categories/
    hydrology/FINDINGS.md                      # source links & cross-category edges
    water_quality/FINDINGS.md
    oceanography/FINDINGS.md                    # no trained station category evidence
    ecology/FINDINGS.md
    socioeconomic/FINDINGS.md
```

The full observed FCM nodes and links are a **predictive relationship
view**, not an ecological connectivity graph. FCM weights are
standardized by individual site training histories; their signs and
magnitudes may differ with distribution, test period and variables.
The new site-to-site comparison intentionally does *not* average or
normalize those matrices into an unsupported regional FCM.

## What to do next scientifically

The atlas is an evidence **integration** improvement, not evidence
that higher-level causal links have been identified.

Priorities remain:
1. Recruit several additional independently observed stations in
   Central/South Biscayne and an appropriate west-coast hydrological
   region using the existing M9.1 metadata-only plan and USGS series
   verification.
2. Add actual dissolved-oxygen, nutrient, rainfall/tidal forcing and
   ecological observation streams where harmonizable and observed.
   These have variable sampling frequencies and need separate models
   or scientifically justified temporal aggregation—not empty nodes
   or synthetic edges.
3. Verify physical catchment/estuary connectivity and stage reference
   frames for candidate spatial groups, then evaluate real
   multistation lagged predictors with fully held-out station(s) and
   strong persistence/no-transfer baselines.
4. Only if predictive and spatial tests succeed, fit and render a
   true regional FCM and consider Mixture-of-Experts gating.

Do not use observed daily-change Pearson coefficients as FCM
parameters. They are exploratory co-fluctuation only and can be
driven by a shared external process even when stations are
hydrologically independent.
