"""Regression tests for USGS v1 metadata identifiers, short preflight and 429 auth."""
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from southfl.net import AcquisitionError,write_csv
from southfl.periods import (_usgs_series_id,usgs_periods,
                             usgs_site_parameter_periods,_row as period_row)
from southfl.observations import (_row as observed_row,usgs_observations)
from southfl.usgs_reconcile import resolve_one
from southfl.history_selection import PLAN_COLS
from scripts.reconcile_fcm_series import run as reconcile_run

def task(series="geojson-feature-id"):
    return dict(panel_id="panel_01",region="big_cypress",
        dataset_id="usgs_water",site_id="USGS-12345",
        concept="discharge",parameter_code="00060",
        series_id=series,unit="ft3/s",vertical_datum="",
        start_date="2026-07-04",end_date="2026-10-31",
        mode="continuous",metadata_start="2010-01-01",
        metadata_end="2026-11-24",
        selection_status="metadata_candidate_validate_real_observations")

def source(series_id="canonical-001",unit="ft3/s",datum=""):
    return period_row("usgs_water","USGS-12345",series_id,
        code="00060",name="Discharge",concept="discharge",
        unit=unit,datum=datum,begin="2010-01-01T00:00:00Z",
        end="2026-11-24T00:00:00Z",
        evidence="time_series_first_last_metadata",
        url="https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/items")

def obs(series_id="canonical-001"):
    return observed_row(dataset_id="usgs_water",site_id="USGS-12345",
        series_id=series_id,concept="discharge",parameter_code="00060",
        sample_date="2026-10-30",timestamp_utc="2026-10-30T12:00:00Z",
        time_basis="explicit_utc_datetime",value="37",original_value="37",
        unit="ft3/s",vertical_datum="")

class MetadataIdTests(unittest.TestCase):
    def test_properties_id_not_unrelated_geojson_feature_id(self):
        feature={"id":"geojson-feature-id","properties":{
            "id":"canonical-001","monitoring_location_id":"USGS-12345",
            "parameter_code":"00060","parameter_name":"Discharge",
            "unit_of_measure":"ft3/s",
            "begin":"2010-01-01T00:00:00Z",
            "end":"2026-11-24T00:00:00Z"}}
        self.assertEqual(_usgs_series_id(feature),"canonical-001")
        with patch("southfl.periods.get_json",return_value={
            "features":[feature],"links":[]}):
            rows=usgs_site_parameter_periods("USGS-12345","00060")
        self.assertEqual([x["series_id"] for x in rows],["canonical-001"])

    def test_contradictory_declared_metadata_ids_rejected(self):
        feature={"properties":{"id":"canonical-001","time_series_id":"other"}}
        with self.assertRaisesRegex(AcquisitionError,"contradictory"):
            _usgs_series_id(feature)

    def test_general_period_discovery_uses_documented_id(self):
        feature={"id":"irrelevant-feature-id","properties":{
            "id":"canonical-001","monitoring_location_id":"USGS-12345",
            "parameter_code":"00060","begin":"2020-01-01",
            "end":"2026-11-24"}}
        with patch("southfl.periods.get_json",return_value={
            "features":[feature],"links":[]}):
            r=usgs_periods((-82,25,-81,26),{"USGS-12345"})
        self.assertEqual(r[0]["series_id"],"canonical-001")

    def test_targeted_metadata_never_swallows_other_site(self):
        with patch("southfl.periods.get_json",return_value={"features":[{
            "properties":{"id":"id","monitoring_location_id":"USGS-OTHER",
                          "parameter_code":"00060"}}],"links":[]}):
            with self.assertRaisesRegex(AcquisitionError,"wrong site"):
                usgs_site_parameter_periods("USGS-12345","00060")

class PreflightTests(unittest.TestCase):
    def test_one_matching_current_id_and_real_observation_can_replace_old(self):
        def metadata(site,code): return [source("canonical-001")]
        def observed(site,code,start,end,concept,**kwargs):
            return [obs("canonical-001")],["https://api.waterdata.usgs.gov/"]
        selected,audit=resolve_one(task(),metadata,observed)
        self.assertEqual(selected["series_id"],"canonical-001")
        self.assertEqual(audit["old_series_id"],"geojson-feature-id")
        self.assertIn("verified_by_live",audit["decision"])
        self.assertEqual(audit["n_probe_observations"],1)

    def test_ambiguous_two_active_series_cannot_auto_pick(self):
        def metadata(site,code):return [source("a"),source("b")]
        def observed(site,code,start,end,concept,**kwargs):
            return [obs("a"),obs("b")],[]
        with self.assertRaisesRegex(AcquisitionError,"ambiguous"):
            resolve_one(task(),metadata,observed)

    def test_unknown_new_id_not_in_official_metadata_is_rejected(self):
        def metadata(site,code):return [source("a")]
        def observed(site,code,start,end,concept,**kwargs):
            return [obs("not-in-metadata")],[]
        with self.assertRaisesRegex(AcquisitionError,"no observed match"):
            resolve_one(task(),metadata,observed)

    def test_unit_datum_mismatch_never_silently_substituted(self):
        def metadata(site,code):return [source("a",unit="m3/s")]
        def observed(site,code,start,end,concept,**kwargs):
            return [obs("a")],[]
        with self.assertRaisesRegex(AcquisitionError,"no current metadata"):
            resolve_one(task(),metadata,observed)

    def test_old_id_preferred_when_multiple_valid_series(self):
        def metadata(site,code):return [source("a"),source("b")]
        def observed(site,code,start,end,concept,**kwargs):
            return [obs("a"),obs("b")],[]
        selected,audit=resolve_one(task("b"),metadata,observed)
        self.assertEqual(selected["series_id"],"b")

    def test_dry_run_no_requests_or_files(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"plan.csv"
            write_csv(path,[task()],PLAN_COLS)
            out=Path(d)/"run"
            with patch("scripts.reconcile_fcm_series.resolve_one") as remote:
                result=reconcile_run(path,out)
            remote.assert_not_called()
            self.assertEqual(result["status"],"dry_run")
            self.assertFalse(out.exists())

    def test_verified_plan_records_input_lineage(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"plan.csv"
            write_csv(path,[task()],PLAN_COLS)
            out=Path(d)/"run"
            def selected(t,probe_days):
                corrected=dict(t,series_id="canonical-001")
                audit=dict(panel_id=t["panel_id"],site_id=t["site_id"],
                           parameter_code=t["parameter_code"],concept=t["concept"],
                           old_series_id=t["series_id"],
                           resolved_series_id="canonical-001",
                           status="verified",decision="verified")
                return corrected,audit
            with patch("scripts.reconcile_fcm_series.resolve_one",side_effect=selected):
                manifest=reconcile_run(path,out,execute=True,min_delay=0)
            self.assertEqual(manifest["n_changed_series_ids"],1)
            self.assertEqual(manifest["n_verified_complete_panels"],1)
            self.assertTrue(manifest["verified_plan_sha256"])
            self.assertIn("canonical-001",(out/"history_plan.csv").read_text())

class KeyAndRateLimitTests(unittest.TestCase):
    def test_usgs_key_is_header_not_url(self):
        from southfl.net import get_bytes
        class Response:
            url="https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items"
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def read(self,size):return b'{"ok":true}'
        class Opener:
            def open(self,request,timeout):
                self.request=request
                return Response()
        opener=Opener()
        with patch.dict("os.environ",{"USGS_API_KEY":"SECRET_TEST_KEY"}):
            with patch("urllib.request.build_opener",return_value=opener):
                data=get_bytes("https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items?f=json")
        self.assertIn(b"ok",data)
        self.assertEqual(opener.request.get_header("X-api-key"),"SECRET_TEST_KEY")
        self.assertNotIn("SECRET_TEST_KEY",opener.request.full_url)

    def test_usgs_429_backoff_and_no_secret_in_exception(self):
        from southfl.net import get_bytes
        class Opener:
            def open(self,request,timeout):
                raise urllib.error.HTTPError(request.full_url,429,
                    "Too Many Requests",{"Retry-After":"1"},None)
        with patch.dict("os.environ",{"USGS_API_KEY":"SECRET_TEST_KEY"}):
            with patch("urllib.request.build_opener",return_value=Opener()):
                with patch("southfl.net.time.sleep") as sleeping:
                    with self.assertRaisesRegex(AcquisitionError,"429") as caught:
                        get_bytes("https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items")
        self.assertNotIn("SECRET_TEST_KEY",str(caught.exception))
        self.assertEqual(sleeping.call_count,2)

if __name__=="__main__":
    unittest.main()
