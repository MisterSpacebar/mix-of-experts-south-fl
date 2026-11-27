# Milestone 9.1 — bounded geographic station recruitment

**Metadata-only plan. No live observations or regional FCMs.**

Target discovery rectangle: big_cypress. Period-of-record window: 2026-05-29 to 2026-11-24.
Existing modeled source-located stations are excluded: 3.
Nearby period-metadata candidates: 6.
Selected new station panels: 6.

## Audit/next steps

- [Ranked local candidates](metadata_recruitment_shortlist.csv)
- [Bounded acquisition-ready metadata plan](history_plan.csv)
- [Excluded legacy/alternate station namespace entries](inventory_identifier_exclusions.csv)

1. Review location, reported units, metadata period dates and hydrological plausibility of each selected station.
2. Split the history_plan.csv into bounded whole-station requests with scripts/plan_m8_batches.py.
3. Run scripts/reconcile_fcm_series.py --execute on each batch and inspect ID/source audit before data retrieval.
4. Use scripts/fetch_fcm_history.py --execute with bounded pacing, then scripts/build_fcm_panels.py for observed-only QA.
5. Re-run the M8 station-specific model trainer and this M9 spatial screening before any proposed multistation model.

Straight-line proximity and coarse discovery envelopes are not watershed boundaries, flow pathways or evidence of transfer.
The metadata beginning and ending dates DO NOT certify that observations actually exist for all dates in between.
