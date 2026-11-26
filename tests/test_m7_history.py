"""Milestone 7 bounded historical retrieval and panel construction tests."""
import json,tempfile,unittest
from pathlib import Path
from datetime import date,timedelta,datetime
from unittest.mock import patch
from southfl.historical import windows,fetch_series
from southfl.observations import _row,COLS
from southfl.net import AcquisitionError,write_csv
from southfl.panels import build_daily_panels
from southfl.history_selection import PLAN_COLS
from scripts.fetch_fcm_history import run as fetch_run
from scripts.build_fcm_panels import run as panels_run

def task(site="USGS-1",concept="salinity",code="00480",series="ts-1"):
    return dict(panel_id="panel_01",region="florida_bay",dataset_id="usgs_water",
                site_id=site,concept=concept,parameter_code=code,
                series_id=series,unit="ppt",vertical_datum="",
                start_date="2026-10-01",end_date="2026-10-14",mode="continuous",
                metadata_start="2020-01-01",metadata_end="2026-11-22",
                selection_status="metadata_candidate_validate_real_observations")

def obs(day="2026-10-01",hour=0,concept="salinity",series="ts-1",
        value="4.0",unit="ppt",**kw):
    return _row(dataset_id="usgs_water",site_id="USGS-1",
                concept=concept,parameter_code="00480",series_id=series,
                time_basis="explicit_utc_datetime",
                timestamp_utc=f"{day}T{hour:02d}:00:00Z",
                sample_date=day,value=value,original_value=value,
                unit=unit,**kw)

class History(unittest.TestCase):
    def test_chunk_boundaries_no_duplicate_dates(self):
        spans=list(windows("2026-10-01","2026-10-31",14))
        self.assertEqual(spans,[("2026-10-01","2026-10-14"),
                                ("2026-10-15","2026-10-28"),
                                ("2026-10-29","2026-10-31")])

    def test_exact_source_id_filter_and_duplicate_removal(self):
        good=obs()
        other=obs(series="other")
        def fake(site,code,start,end,concept,mode):
            return [good,dict(good),other],["https://example.com/query"]
        rows,urls,unmatched,dups=fetch_series(task(),fetcher=fake)
        self.assertEqual(len(rows),1)
        self.assertEqual(unmatched,1)
        self.assertEqual(dups,1)

    def test_mixed_unit_fails_closed(self):
        def fake(site,code,start,end,concept,mode):
            return [obs(unit="m")],[]
        with self.assertRaisesRegex(AcquisitionError,"unit changed"):
            fetch_series(task(),fetcher=fake)

    def test_conflicting_same_timestamp_fails_closed(self):
        def fake(site,code,start,end,concept,mode):
            return [obs(),obs(value="5.0")],[]
        with self.assertRaisesRegex(AcquisitionError,"conflicting values"):
            fetch_series(task(),fetcher=fake)

    def test_download_is_dry_by_default_and_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"plan.csv"
            write_csv(path,[task()],PLAN_COLS)
            dest=Path(folder)/"run"
            with patch("scripts.fetch_fcm_history.fetch_series") as fetcher:
                result=fetch_run(path,dest)
            fetcher.assert_not_called()
            self.assertEqual(result["status"],"dry_run")
            self.assertFalse(dest.exists())

    def test_failed_task_marked_incomplete_no_fabrication(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"plan.csv"
            write_csv(path,[task()],PLAN_COLS)
            dest=Path(folder)/"run"
            with patch("scripts.fetch_fcm_history.fetch_series",
                       side_effect=AcquisitionError("api down")):
                report=fetch_run(path,dest,execute=True)
            self.assertEqual(report["n_failed_tasks"],1)
            self.assertEqual(report["incomplete_panels"],["panel_01"])
            self.assertEqual(report["n_observations"],0)
            self.assertTrue((dest/"history_manifest.json").exists())

class Panels(unittest.TestCase):
    def test_dense_daily_means_only_no_fill(self):
        a=task()
        b=dict(a,concept="water_temperature",parameter_code="00010",
               series_id="ts-2",unit="degC")
        source=[]
        for d in ("2026-10-01","2026-10-02"):
            for h in range(0,24,3):
                source.append(obs(day=d,hour=h,value="4.0"))
                source.append(_row(dataset_id="usgs_water",site_id="USGS-1",
                    concept="water_temperature",parameter_code="00010",
                    series_id="ts-2",timestamp_utc=f"{d}T{h:02d}:00:00Z",
                    sample_date=d,time_basis="explicit_utc_datetime",
                    value="25",original_value="25",unit="degC"))
        panels,summary=build_daily_panels(source,[a,b])
        self.assertEqual(len(panels["panel_01"][1]),2)
        self.assertEqual(summary[0]["n_consecutive_daily_pairs"],1)
        self.assertEqual(panels["panel_01"][1][0]["salinity"],4)
        self.assertEqual(panels["panel_01"][1][0]["n_salinity"],8)

    def test_daily_date_missing_one_concept_is_dropped(self):
        a=task()
        b=dict(a,concept="water_temperature",parameter_code="00010",
               series_id="ts-2",unit="degC")
        source=[obs(hour=h) for h in range(0,24,3)]
        panels,summary=build_daily_panels(source,[a,b])
        self.assertEqual(panels["panel_01"][1],[])
        self.assertEqual(summary[0]["n_dropped_partial_days"],1)

    def test_reject_censored_and_provisional_option(self):
        a=task()
        source=[obs(hour=h) for h in range(0,24,3)]
        source[0]["detection_condition"]="Below detection"
        source[1]["approval_status"]="Provisional"
        _,summ=build_daily_panels(source,[a],exclude_provisional=True)
        self.assertEqual(summ[0]["n_excluded_source_values"],2)

    def test_no_multi_site_panel(self):
        a=task()
        b=dict(a,site_id="USGS-2",concept="water_temperature")
        with self.assertRaisesRegex(ValueError,"one canonical USGS site"):
            build_daily_panels([], [a,b])

    def test_manifest_hash_verified_before_panel_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            hist=Path(folder)/"hist"
            hist.mkdir()
            write_csv(hist/"history_plan_used.csv",[task()],PLAN_COLS)
            write_csv(hist/"observations.csv",[obs()],COLS)
            (hist/"history_manifest.json").write_text(json.dumps({
                "observations_sha256":"not_the_hash",
                "incomplete_panels":[]}))
            with self.assertRaisesRegex(ValueError,"hash differs"):
                panels_run(hist,Path(folder)/"panels")

if __name__=="__main__":
    unittest.main()
