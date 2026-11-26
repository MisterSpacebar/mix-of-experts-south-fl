"""Milestone 7 observational readiness and same-site history selection tests."""
import json,math,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from southfl.readiness import audit
from southfl.history_selection import select_panels
from southfl.observations import _row
from southfl.net import write_csv
from scripts.audit_model_readiness import run as audit_run

def sensor(site="USGS-1",concept="salinity",stamp="2026-10-01T00:00:00Z",
           value="4.5",series="ts-a",**kwargs):
    return _row(dataset_id="usgs_water",site_id=site,concept=concept,
                series_id=series,sample_date=stamp[:10],timestamp_utc=stamp,
                value=value,original_value=value,time_basis="explicit_utc_datetime",
                unit="ppt",**kwargs)

def metadata(site,code,concept,series):
    return dict(dataset_id="usgs_water",site_id=site,series_id=series,
                parameter_code=code,parameter_name=concept,concept=concept,
                unit="ft",vertical_datum="",primary_status="Primary",
                sublocation_identifier="",begin_utc="2020-01-01T00:00:00Z",
                end_utc="2026-11-24T00:00:00Z",
                evidence="time_series_first_last_metadata")

class QA(unittest.TestCase):
    def test_observed_only_and_pair_dates(self):
        rows=[
            sensor(concept="salinity",series="s",stamp="2026-10-01T12:00:00Z"),
            sensor(concept="water_temperature",series="t",
                   stamp="2026-10-01T12:00:00Z"),
            sensor(concept="salinity",series="s",stamp="2026-10-02T12:00:00Z"),
        ]
        series,pairs=audit(rows)
        self.assertEqual(len(series),2)
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]["shared_observed_dates"],1)
        self.assertEqual(series[0]["readiness_note"],
                         "too_few_observed_days_for_temporal_model")

    def test_censored_and_duplicate_observation_times(self):
        row=sensor()
        alternate=dict(row,original_value="5.7",value="5.7")
        censored=dict(row,series_id="ts-b",value="",original_value="<1",
                      detection_condition="Not Detected")
        series,_=audit([row,alternate,censored])
        a=next(x for x in series if x["series_id"]=="ts-a")
        b=next(x for x in series if x["series_id"]=="ts-b")
        self.assertEqual(a["n_conflicting_times"],1)
        self.assertEqual(b["n_numeric"],0)
        self.assertEqual(b["n_censored"],1)

    def test_local_sample_date_kept_not_utc(self):
        r=_row(dataset_id="epa_wqp",site_id="W-1",concept="ph",
               time_basis="source_local_date_not_utc",sample_date="2026-10-01",
               value="7.2",unit="pH",activity_id="sample-1")
        series,pairs=audit([r])
        self.assertEqual(series[0]["n_dates"],1)
        self.assertEqual(pairs,[])

    def test_bad_utc_stamp_rejected(self):
        row=sensor()
        row["timestamp_utc"]="not-a-date"
        with self.assertRaisesRegex(ValueError,"timestamp"):
            audit([row])

    def test_writes_immutable_audit_outputs(self):
        from southfl.observations import COLS
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"observations.csv"
            write_csv(src,[sensor()],COLS)
            dest=Path(d)/"qa"
            r=audit_run(src,dest)
            self.assertEqual(r["n_observation_rows"],1)
            self.assertFalse(r["trainable"])
            self.assertTrue((dest/"readiness_manifest.json").exists())
            with self.assertRaisesRegex(ValueError,"not empty"):
                audit_run(src,dest)

class HistorySelection(unittest.TestCase):
    def test_same_site_3_different_concepts_and_region_diversity(self):
        rows=[]
        for s in ["USGS-1","USGS-2"]:
            rows.extend([metadata(s,"00060","discharge",s+"-flow"),
                         metadata(s,"00010","water_temperature",s+"-temp"),
                         metadata(s,"00480","salinity",s+"-salt")])
        stations=[dict(dataset_id="usgs_water",site_id="USGS-1",
                       regions="caloosahatchee"),
                  dict(dataset_id="usgs_water",site_id="USGS-2",
                       regions="lake_okeechobee")]
        selected=select_panels(rows,stations,"2026-10-31",days=90,
                               max_panels=2,max_concepts=3)
        self.assertEqual(len(selected),6)
        self.assertEqual(len({r["panel_id"] for r in selected}),2)
        self.assertEqual(len({r["region"] for r in selected}),2)
        self.assertEqual({r["selection_status"] for r in selected},
                         {"metadata_candidate_validate_real_observations"})

    def test_exclusion_before_ranking_and_screening_region_cap(self):
        rows=[]
        sites=[]
        for site,region in [("USGS-1","big_cypress"),
                            ("USGS-2","big_cypress"),
                            ("USGS-3","florida_bay")]:
            rows.extend([
                metadata(site,"00060","discharge",site+"-flow"),
                metadata(site,"00010","water_temperature",site+"-temp"),
                metadata(site,"00480","salinity",site+"-salt"),
            ])
            sites.append(dict(dataset_id="usgs_water",site_id=site,
                              regions=region))
        chosen=select_panels(rows,sites,"2026-10-31",
                             max_panels=3,max_concepts=3,
                             exclude_sites={"USGS-1"},max_per_region=1)
        self.assertEqual(len(chosen),6)
        self.assertEqual({x["site_id"] for x in chosen},
                         {"USGS-2","USGS-3"})
        self.assertEqual({x["region"] for x in chosen},
                         {"big_cypress","florida_bay"})
        with self.assertRaisesRegex(ValueError,"max_per_region"):
            select_panels(rows,sites,"2026-10-31",max_per_region=0)

    def test_targeted_region_recruitment_does_not_infer_connectivity(self):
        rows=[]
        stations=[]
        for sid,regions in [
            ("USGS-A","big_cypress;southwest_everglades_coast"),
            ("USGS-B","big_cypress"),
            ("USGS-C","central_south_biscayne"),
        ]:
            rows.extend([
                metadata(sid,"00060","discharge",sid+"-flow"),
                metadata(sid,"00480","salinity",sid+"-salinity"),
                metadata(sid,"00010","water_temperature",sid+"-temperature"),
            ])
            stations.append(dict(dataset_id="usgs_water",site_id=sid,
                                 regions=regions))
        selected=select_panels(rows,stations,"2026-10-31",
            max_panels=3,region_filter={"big_cypress"})
        self.assertEqual({x["site_id"] for x in selected},
                         {"USGS-A","USGS-B"})
        self.assertEqual({x["region"] for x in selected},{"big_cypress"})
        with self.assertRaisesRegex(ValueError,"unknown discovery region"):
            select_panels(rows,stations,"2026-10-31",
                          region_filter={"imaginary_bay"})

    def test_insufficient_multivariate_series_return_empty(self):
        r=[metadata("USGS-1","00060","discharge","ts")]
        s=[dict(dataset_id="usgs_water",site_id="USGS-1",
                regions="everglades_interior")]
        self.assertEqual(select_panels(r,s,"2026-10-31"),[])

    def test_stale_series_cannot_be_selected(self):
        r=[metadata("USGS-1",code,concept,str(i)) for i,(code,concept)
           in enumerate([("00060","discharge"),("00010","water_temperature"),
                         ("00480","salinity")])]
        r[1]["end_utc"]="2024-01-01T00:00:00Z"
        s=[dict(dataset_id="usgs_water",site_id="USGS-1",
                regions="everglades_interior")]
        self.assertEqual(select_panels(r,s,"2026-10-31"),[])

if __name__=="__main__":
    unittest.main()
