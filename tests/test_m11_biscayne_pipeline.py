import tempfile
import unittest
from pathlib import Path
from southfl.regional_pipeline import choose,Stages,request_count
from southfl.m10_forcing import forcing_settings,assemble
from scripts.run_m11_biscayne import DEFAULT,serial_bundle,deserialize_bundle


class PipelineTests(unittest.TestCase):
    def test_recruitment_deduplicates_overlap_and_prefers_near_bottom(self):
        stations=[dict(site_id="USGS-12345678",dataset_id="usgs_water",latitude="25.79",longitude="-80.2"),
                  dict(site_id="USGS-12345679",dataset_id="usgs_water",latitude="25.79",longitude="-80.2")]
        periods=[]
        for s in stations:
            for c,code,u in (("salinity","00480","ppt"),("water_temperature","00010","degC")):
                periods.append(dict(dataset_id="usgs_water",site_id=s["site_id"],concept=c,parameter_code=code,
                  unit=u,series_id=s["site_id"]+code,statistic_id="00011",sublocation_identifier="Near Bottom",
                  begin_utc="2025-01-01",end_utc="2026-11-01",evidence="time_series_first_last_metadata"))
        plan,_=choose(stations,periods+periods,DEFAULT["regions"],DEFAULT["start"],DEFAULT["end"],set(),1)
        self.assertEqual(len(plan),4)
        self.assertEqual(len({r["site_id"] for r in plan}),2)
        self.assertEqual(len({r["region"] for r in plan}),2)
        self.assertEqual(request_count(plan),108)

    def test_stage_resume_does_not_repeat_completed_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"run"
            a=Stages(root,{"a":1},False)
            def create(p):
                p.mkdir(parents=True); (p/"data").write_text("x")
                return True
            p=a.run("one",create)
            b=Stages(root,{"a":1},True)
            self.assertEqual(b.run("one",lambda _:self.fail("repeated")),p)
            (p/"data").write_text("changed")
            with self.assertRaisesRegex(ValueError,"hash changed"):
                b.verify_all()
            with self.assertRaisesRegex(ValueError,"configuration changed"):
                Stages(root,{"a":2},True)

    def test_failed_stage_preserves_attempt_and_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"run"
            a=Stages(root,{},False)
            def fail(p):
                p.mkdir(parents=True); (p/"failure").write_text("429")
                raise RuntimeError("throttle")
            with self.assertRaises(RuntimeError):
                a.run("one",fail)
            b=Stages(root,{},True)
            def success(p):
                p.mkdir(parents=True); (p/"ok").write_text("ok")
                return True
            p=b.run("one",success)
            self.assertEqual(p.name,"attempt_02")
            self.assertTrue((p.parent/"attempt_01"/"failure").exists())

    def test_biscayne_forcing_dates(self):
        w,t,start,end,first,last=forcing_settings(DEFAULT)
        self.assertEqual((w,t),("USW00012839","8723214"))
        rows=assemble({}, {},first,last)
        self.assertEqual(len(rows),364)
        self.assertEqual(rows[0]["weather_source_date"],"2025-10-31")
        self.assertEqual(rows[-1]["water_level_source_date"],"2026-10-30")

    def test_bundle_roundtrip(self):
        b=dict(cohort=Path("c"),base=Path("b"),layers=Path("l"),combined=Path("m"),forcing=Path("f"),
               local_only=True,forcing_config=DEFAULT,cohort_config=dict(snapshots=[(Path("d"),Path("h"),Path("i"))],
               coordinates=Path("s"),min_sites=4))
        self.assertEqual(deserialize_bundle(serial_bundle(b)),b)

    def test_parameterized_cohort_replays_frozen_m10(self):
        from scripts.train_m10_regional_fcm import COHORT,SNAPSHOTS,load_cohort
        # New bundle code must reproduce the real existing cohort, without
        # network or assuming the M11 geography is populated.
        m,splits,_=load_cohort(COHORT,False,dict(snapshots=SNAPSHOTS,
            coordinates=COHORT/"station_cohort.csv",min_sites=4))
        self.assertEqual(len(splits),4)
        self.assertEqual(sum(len(x["test"]) for x in splits.values()),144)

    def test_local_only_bundle_retains_station_experts(self):
        from scripts.train_m10_regional_fcm import COHORT,SNAPSHOTS
        from scripts.build_m10_hierarchical_atlas import context,replay
        bundle=dict(cohort=COHORT,base=COHORT,combined=COHORT,forcing=COHORT,
                    layers=Path("data/m10/layers_expanded_v1"),local_only=True,
                    cohort_config=dict(snapshots=SNAPSHOTS,coordinates=COHORT/"station_cohort.csv",min_sites=4),
                    forcing_config=None)
        router,entries,manifest,*_=context(bundle=bundle)
        rows,edges,residual,weights,nmix=replay(router,entries,manifest,bundle)
        self.assertEqual(len(rows),2293)
        self.assertEqual(len(edges),185)
        self.assertEqual(nmix,0)
        self.assertFalse(router.folds)
        self.assertFalse(residual)
        self.assertFalse(weights)
