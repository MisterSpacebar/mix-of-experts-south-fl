# M10.4 — hierarchical research expert registry and evidence atlas

## Local run (offline)

```powershell
git checkout main
git pull origin main
python -m unittest discover -s tests -v
python scripts/build_m10_hierarchical_atlas.py --verify-raw --out data/m10/hierarchical_atlas_v1
Get-Content data/m10/hierarchical_atlas_v1/INDEX.md
Start-Process data/m10/hierarchical_atlas_v1/atlas.html
```

No new acquisition or fitting. The original M7–M10 outputs remain immutable.
The registry uses the existing cohort source verification, original M10.3
output hashes and forcing source reconstruction. Local fit files have no
previous per-file hash manifest: record current hashes and verify model
matrix/edge agreement and every exported held-out FCM prediction against
the original panel. This is replay verification, not independent refitting.

## Inference

```powershell
python scripts/build_m10_hierarchical_atlas.py --query USGS-255327081275900 2026-11-01 salinity --policy adapted --scope weather_water_level
python scripts/build_m10_hierarchical_atlas.py --query USGS-255327081275900 2026-11-01 discharge --policy category
```

The query uses the archived previous UTC day's observation, native unit
and source station. It returns the category/subcategory, selected expert,
component values, weights, and fallback reason. The target day's actual
is not read by the router. The query is **retrospective**, not live.
No arbitrary input vectors, unknown stations, extrapolated dates or
unverified sensor transfer. Missing previous-day state results in
abstention, not interpolation. Query without --verify-raw relies on
existing verified raw provenance plus current panel and forcing checks.

Policies: persistence (default), station (full local model), category,
subcategory, explicit expert ID (station FCM), zero_shot and adapted
(the fixed regional mixtures). Mixture forcing scope must be explicitly
chosen: unforced, weather, weather_water_level. No policy selection by
test performance. No cross-station/region averaging. A missing local
scope, incompatible region or non-holdout date falls back to persistence.
Missing forcing falls back to the same unforced mixture. Unavailable
previous state abstains. For regional mixtures the scope is the actual
Big Cypress screening cohort, including Pumpkin River whose primary
region is Southwest Everglades Coast. Exact sensor depth and hydraulic
connectivity are not verified.

## Evidence atlas

The offline HTML atlas links registry, region × category coverage,
station coefficients, regional residual coefficients, mixture weights,
route-level predictions and metrics. Registry preserves 25 station-local
fits (7 full, 18 specialist) and 13 unfitted candidates; four specialist
scope aliases are explicitly marked. It registers persistence and the
actual residual/mixture fold artifacts, not a deployed model.
Registry mixture fit_sites denotes gate validation sites; component
records show the fitting sites. Alias rows are callable individually but
not counted as independent evidence. Unrepresented regions/categories
remain visible as gaps. Primary region counts and overlapping discovery
screens are separate.

All 6 regional mixture policies (2 modes × 3 scopes) replay their exact
original predictions on all 288 targets (1,728 route records).
Station-local experts replay their own held-out targets; their test
periods differ, so their errors are not compared or blended with the
regional experiments on mismatched dates. The HTML is a static evidence
browser, not a deployed service or learned cross-subsystem gate.

M10.4 creates no overall FCM, transport coupling, new model fits or
prospective validation. The retained M10.3 salinity result is exploratory.
Next: independent Biscayne Bay cohort and season, with a frozen
experimental protocol; no further optimization on the same test season.

```powershell
git add data/m10/hierarchical_atlas_v1
git commit -m "M10.4: consolidate expert registry and hierarchical evidence atlas"
git push origin main
```
