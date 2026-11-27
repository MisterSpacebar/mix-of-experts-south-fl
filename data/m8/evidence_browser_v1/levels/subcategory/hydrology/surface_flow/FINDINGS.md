# Subcategory — hydrology/surface_flow

**Evidence state:** `redundant_concept_scope_not_independent`.
**Regional integrated expert: NOT TRAINED.**

- Within-station fitted scope artifacts: 3.
- Distinct station/concept-set signatures: 3.
- Evaluated donor→target station pairs: 0.
- Evaluated per-concept transfer comparisons: 0.
- Directed edges with station evidence: 0.
- Weak edges (one or more station magnitudes below 0.08): 0.
- Unverified cross-station stage-datum comparisons: 0.
- Bootstrap intervals excluding original error point estimates: 0.

## Evidence and visualizations

- [Transfer MAE ratios (log scale)](visuals/transfer_vs_persistence.png)
- [Edge strength and direction screening](visuals/edge_magnitude_and_sign.png)
- [Donor transfer diagnostics](transfer_diagnostics.csv)
- [Edge evidence grades](edge_evidence.csv)
- [Bootstrap uncertainty audit](bootstrap_audit.csv)

**Same concept set as a category fit:** the existing subcategory fit is a separate artifact, not independent observational evidence. The replication evaluator correctly omits duplicate scope comparisons.

## Trained station models and source findings

- **USGS-255327081275900**: [FCM network](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_01_USGS_255327081275900/visuals/network.svg) · [Model findings](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_01_USGS_255327081275900/FINDINGS.md) · [Data provenance](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_01_USGS_255327081275900/DATA.md) · redundant with `levels/category/hydrology/panel_01_USGS_255327081275900`
- **USGS-255534081324000**: [FCM network](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_02_USGS_255534081324000/visuals/network.svg) · [Model findings](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_02_USGS_255534081324000/FINDINGS.md) · [Data provenance](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_02_USGS_255534081324000/DATA.md) · redundant with `levels/category/hydrology/panel_02_USGS_255534081324000`
- **USGS-0229070854**: [FCM network](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_04_USGS_0229070854/visuals/network.svg) · [Model findings](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_04_USGS_0229070854/FINDINGS.md) · [Data provenance](../../../../../layers_replication_v1/levels/subcategory/hydrology/surface_flow/panel_04_USGS_0229070854/DATA.md) · redundant with `levels/category/hydrology/panel_04_USGS_0229070854`

The unit check confirms reported unit labels, not verified hydrological connectivity or sensor reference frames. Missing stage datums are flagged rather than silently treated as physically interchangeable.
Edge magnitudes are learned coefficients, not causal strengths. Source-specific forecasts and the original files are unchanged.
