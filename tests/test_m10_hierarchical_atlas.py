"""Real-artifact replay and fail-closed research routing."""
import copy
import tempfile
import unittest
from pathlib import Path

from scripts.build_m10_hierarchical_atlas import context,run
from southfl.hierarchical_experts import validate_gate,station_predict
from southfl.audit import read_csv

EAST="USGS-255327081275900"
BLACK="USGS-0229070854"


class HierarchicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.router,*_=context()

    def test_gate_rejects_invalid_and_target_local_zero_shot(self):
        for w in ([[.5,.5,.5],[1,0,0]],[[0,0,1],[1,0,0]]):
            with self.assertRaises(ValueError):
                validate_gate(w,False)

    def test_hierarchy_routes_by_scope_not_test_skill(self):
        r=self.router
        a=r.infer(EAST,"2026-11-01","salinity","category")
        b=r.infer(EAST,"2026-11-01","discharge","subcategory")
        self.assertIn(":category:water_quality:",a["selected_expert"])
        self.assertIn(":subcategory:hydrology:surface_flow",b["selected_expert"])
        self.assertEqual(a["unit"],"ppt")
        self.assertEqual(r.infer(BLACK,"2026-11-01","salinity","adapted")["selected_expert"],
                         "persistence:"+BLACK)
        self.assertEqual(r.infer(EAST,"2026-11-01","discharge","zero_shot")["fallback_reason"],
                         "no_compatible_regional_holdout_expert")
        self.assertEqual(r.infer(EAST,"2026-11-01","salinity","zero_shot",region="florida_bay")["selected_expert"],
                         "persistence:"+EAST)

    def test_mixture_fallback_and_no_target_actual_dependency(self):
        r=self.router
        a=r.infer(EAST,"2026-11-21","salinity","adapted","weather_water_level")
        self.assertEqual(a["scope_used"],"unforced")
        self.assertEqual(a["fallback_reason"],"forcing_missing_or_unfitted")
        clone=copy.copy(r)
        clone.stations=copy.deepcopy(r.stations)
        clone.stations[EAST]["states"].pop("2026-11-21")
        self.assertEqual(a,clone.infer(EAST,"2026-11-21","salinity","adapted","weather_water_level"))
        clone.stations[EAST]["states"].pop("2026-11-20")
        with self.assertRaisesRegex(ValueError,"abstain"):
            clone.infer(EAST,"2026-11-21","salinity","adapted")

    def test_holdout_only_and_explicit_expert_identity(self):
        r=self.router
        self.assertEqual(r.infer(EAST,"2026-10-01","salinity","station")["fallback_reason"],
                         "outside_station_holdout")
        with self.assertRaises(ValueError):
            r.infer("unknown","2026-11-01","salinity")
        with self.assertRaises(ValueError):
            r.infer(EAST,"2026-11-01","salinity","expert",
                    expert_id="station:"+BLACK+":dataset::")

    def test_real_atlas_replays_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"atlas"
            report=run(out)
            self.assertEqual(report["n_observed_stations"],8)
            self.assertEqual(report["registry_counts"]["station_fcm"],25)
            self.assertEqual(report["n_duplicate_scope_aliases"],4)
            self.assertEqual(report["n_regional_holdout_folds"],4)
            self.assertEqual(report["n_mixture_replay_targets"],1728)
            self.assertEqual(report["n_mixture_weight_rows"],48)
            self.assertEqual(report["n_region_category_cells"],70)
            self.assertEqual(report["deployed_experts"],0)
            self.assertTrue(report["replay_matches_original"])
            metrics=read_csv(out/"route_metrics.csv")
            r=next(x for x in metrics if x["site_id"]=="all_sites" and x["concept"]=="salinity"
                   and x["policy"]=="adapted" and x["scope"]=="weather_water_level")
            self.assertAlmostEqual(float(r["mae"]),1.468573541350926)
            self.assertEqual(int(r["n_forcing_fallback"]),80)
            self.assertTrue((out/"atlas.html").is_file())
            with self.assertRaisesRegex(ValueError,"new/empty"):
                run(out)
