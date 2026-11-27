# Dataset — full_station

**Evidence state:** `station_transfer_evidence_available`.
**Regional integrated expert: NOT TRAINED.**

- Within-station fitted scope artifacts: 3.
- Distinct station/concept-set signatures: 3.
- Evaluated donor→target station pairs: 6.
- Evaluated per-concept transfer comparisons: 24.
- Directed edges with station evidence: 16.
- Weak edges (one or more station magnitudes below 0.08): 9.
- Unverified cross-station stage-datum comparisons: 6.
- Bootstrap intervals excluding original error point estimates: 3.

## Evidence and visualizations

- [Transfer MAE ratios (log scale)](visuals/transfer_vs_persistence.png)
- [Edge strength and direction screening](visuals/edge_magnitude_and_sign.png)
- [Donor transfer diagnostics](transfer_diagnostics.csv)
- [Edge evidence grades](edge_evidence.csv)
- [Bootstrap uncertainty audit](bootstrap_audit.csv)
- [Prior station-replication findings](../../../../replication_evidence_v1/levels/dataset/FINDINGS.md)

## Trained station models and source findings

- **USGS-255327081275900**: [FCM network](../../../../layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/visuals/network.svg) · [Model findings](../../../../layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/FINDINGS.md) · [Data provenance](../../../../layers_replication_v1/levels/dataset/panel_01_USGS_255327081275900/DATA.md)
- **USGS-255534081324000**: [FCM network](../../../../layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/visuals/network.svg) · [Model findings](../../../../layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/FINDINGS.md) · [Data provenance](../../../../layers_replication_v1/levels/dataset/panel_02_USGS_255534081324000/DATA.md)
- **USGS-0229070854**: [FCM network](../../../../layers_replication_v1/levels/dataset/panel_04_USGS_0229070854/visuals/network.svg) · [Model findings](../../../../layers_replication_v1/levels/dataset/panel_04_USGS_0229070854/FINDINGS.md) · [Data provenance](../../../../layers_replication_v1/levels/dataset/panel_04_USGS_0229070854/DATA.md)

The unit check confirms reported unit labels, not verified hydrological connectivity or sensor reference frames. Missing stage datums are flagged rather than silently treated as physically interchangeable.
Edge magnitudes are learned coefficients, not causal strengths. Source-specific forecasts and the original files are unchanged.
